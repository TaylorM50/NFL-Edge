#!/usr/bin/env python3
"""Build a compact NFL Edge JSON snapshot from nflverse play-by-play."""
from __future__ import annotations
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "stats.json"
SEASON = int(os.environ.get("NFL_SEASON", datetime.now(timezone.utc).year))
BASE = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"

def safe_num(series):
    return pd.to_numeric(series, errors="coerce").fillna(0)

def main():
    last_error = None
    pbp = None
    used_season = SEASON
    # Try current season, then the prior season for offseason/late-release situations.
    for season in (SEASON, SEASON - 1):
        try:
            url = BASE.format(season=season)
            print(f"Loading nflverse play-by-play for {season}: {url}", flush=True)
            frame = pd.read_parquet(url)
            if frame.empty:
                raise ValueError("empty play-by-play dataset")
            pbp, used_season = frame, season
            break
        except Exception as exc:
            last_error = exc
            print(f"Could not load {season}: {exc}", flush=True)
    if pbp is None:
        raise RuntimeError(f"Unable to load current or previous season: {last_error}")

    needed = ["season", "week", "posteam", "defteam", "play_type", "epa", "success",
              "yards_gained", "pass_attempt", "complete_pass", "qb_hit", "sack",
              "interception", "fumble_lost", "passer_player_name", "rusher_player_name",
              "receiver_player_name", "passing_yards", "rushing_yards", "receiving_yards",
              "passing_tds", "rushing_tds", "receiving_tds", "passer_player_id",
              "rusher_player_id", "receiver_player_id", "passer_position", "rusher_position",
              "receiver_position", "air_yards"]
    for c in needed:
        if c not in pbp.columns:
            pbp[c] = None

    # Keep the requested season; use the actual latest available season if current year has no rows.
    pbp["season"] = pd.to_numeric(pbp["season"], errors="coerce")
    season_df = pbp[pbp["season"] == used_season].copy()
    if season_df.empty:
        raise ValueError(f"No rows for selected season {used_season}")
    season_df["week_num"] = pd.to_numeric(season_df["week"], errors="coerce")
    # Exclude non-offensive and non-scrimmage rows for offense metrics.
    plays = season_df[season_df["play_type"].isin(["pass", "run", "rush"])].copy()
    plays["epa_num"] = safe_num(plays["epa"])
    plays["success_num"] = safe_num(plays["success"])
    plays["yards_num"] = safe_num(plays["yards_gained"])
    plays["is_pass"] = plays["play_type"].eq("pass")
    plays["is_rush"] = plays["play_type"].isin(["run", "rush"])
    plays["pass_attempt_num"] = safe_num(plays["pass_attempt"])
    plays["complete_num"] = safe_num(plays["complete_pass"])
    plays["qb_hit_num"] = safe_num(plays["qb_hit"])
    plays["sack_num"] = safe_num(plays["sack"])
    plays["turnover_num"] = safe_num(plays["interception"]) + safe_num(plays["fumble_lost"])
    plays["explosive_pass"] = plays["is_pass"] & plays["complete_num"].gt(0) & plays["yards_num"].ge(20)

    # Use the last week containing regular-season/playoff play rows as the data window.
    max_week = int(plays["week_num"].max()) if plays["week_num"].notna().any() else None
    # The file is season-to-date; don't filter down to just the latest week.
    team_records = []
    offense = plays[plays["posteam"].notna() & plays["posteam"].ne("")].groupby("posteam")
    defense = plays[plays["defteam"].notna() & plays["defteam"].ne("")].groupby("defteam")
    team_codes = sorted(set(offense.size().index.astype(str)) | set(defense.size().index.astype(str)))
    for code in team_codes:
        off = offense.get_group(code) if code in offense.groups else plays.iloc[0:0]
        deff = defense.get_group(code) if code in defense.groups else plays.iloc[0:0]
        passplays = off[off["is_pass"]]
        nplays = len(off)
        team_records.append({
            "team": code,
            "plays": int(nplays),
            "epa_per_play": round(float(off["epa_num"].mean()), 4) if nplays else None,
            "success_rate": round(float(off["success_num"].mean()), 4) if nplays else None,
            "pass_epa": round(float(passplays["epa_num"].mean()), 4) if len(passplays) else None,
            "rush_epa": round(float(off.loc[off["is_rush"], "epa_num"].mean()), 4) if off["is_rush"].any() else None,
            "explosive_pass_rate": round(float(passplays["explosive_pass"].mean()), 4) if len(passplays) else None,
            "turnovers": int(off["turnover_num"].sum()),
            "pressure_proxy": round(float((passplays["qb_hit_num"] + passplays["sack_num"]).clip(upper=1).mean()), 4) if len(passplays) else None,
            "off_yards": int(off["yards_num"].sum()),
            "def_epa_allowed": round(float(deff["epa_num"].mean()), 4) if len(deff) else None,
        })

    # Aggregate available player fields; player stats reflect PBP-recorded yardage, not box-score validation.
    player_rows = {}
    def add_player(name_col, id_col, pos_col, team_col, yards_col, td_col, category):
        for _, row in season_df.iterrows():
            name = row.get(name_col)
            team = row.get(team_col)
            if pd.isna(name) or not str(name).strip() or pd.isna(team) or not str(team).strip():
                continue
            pid = row.get(id_col)
            key = (str(pid) if pd.notna(pid) and str(pid).strip() else str(name), str(team))
            rec = player_rows.setdefault(key, {"name": str(name), "team": str(team), "position": str(row.get(pos_col) or ""), "pass_yards": 0, "rush_yards": 0, "rec_yards": 0, "tds": 0, "total_epa": 0.0, "total_yards": 0})
            y = pd.to_numeric(pd.Series([row.get(yards_col)]), errors="coerce").fillna(0).iloc[0]
            td = pd.to_numeric(pd.Series([row.get(td_col)]), errors="coerce").fillna(0).iloc[0]
            rec[category] += float(y)
            rec["tds"] += int(td)
            rec["total_yards"] = rec["pass_yards"] + rec["rush_yards"] + rec["rec_yards"]
    add_player("passer_player_name","passer_player_id","passer_position","posteam","passing_yards","passing_tds","pass_yards")
    add_player("rusher_player_name","rusher_player_id","rusher_position","posteam","rushing_yards","rushing_tds","rush_yards")
    add_player("receiver_player_name","receiver_player_id","receiver_position","posteam","receiving_yards","receiving_tds","rec_yards")
    # The same player may appear multiple times per game in PBP; aggregate EPA only on their relevant rows.
    for _, row in season_df.iterrows():
        for name_col, id_col, team_col in [("passer_player_name","passer_player_id","posteam"),("rusher_player_name","rusher_player_id","posteam"),("receiver_player_name","receiver_player_id","posteam")]:
            name, team = row.get(name_col), row.get(team_col)
            if pd.isna(name) or pd.isna(team) or not str(name).strip() or not str(team).strip(): continue
            pid=row.get(id_col); key=(str(pid) if pd.notna(pid) and str(pid).strip() else str(name),str(team))
            if key in player_rows:
                epa=pd.to_numeric(pd.Series([row.get("epa")]),errors="coerce").fillna(0).iloc[0]
                player_rows[key]["total_epa"] += float(epa)
    players=[]
    for rec in player_rows.values():
        for k in ("pass_yards","rush_yards","rec_yards","total_yards"): rec[k]=int(round(rec[k]))
        rec["total_epa"]=round(rec["total_epa"],3)
        players.append(rec)
    players.sort(key=lambda x:x["total_yards"],reverse=True)

    out = {
        "season": used_season,
        "week": max_week,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "nflverse play-by-play release",
        "is_demo": False,
        "teams": team_records,
        "players": players[:1500],
        "meta": {
            "dataset_url": BASE.format(season=used_season),
            "play_definition": "Pass and run/rush rows with available EPA",
            "success_rate_definition": "Mean nflverse success indicator",
            "explosive_pass_definition": "Completed pass with 20+ yards gained",
            "pressure_proxy_definition": "QB hit or sack recorded on pass play; proxy, not charting-grade pressure",
            "risk_worthy_throws": "Not included; requires charting data not supplied by this feed",
            "warning": "Player values aggregated from play-by-play fields and should be validated against official box scores."
        }
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"Wrote {OUT}: {len(team_records)} teams, {len(players)} player records, season {used_season}, week {max_week}")
if __name__ == "__main__":
    main()
