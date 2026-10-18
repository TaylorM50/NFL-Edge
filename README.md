# NFL Edge 2.0 — weekly analytics starter

A responsive NFL dashboard plus a data refresh pipeline. The dashboard reads `data/stats.json`. The repository includes a weekly GitHub Actions workflow that attempts to rebuild the snapshot from nflverse play-by-play and commit it to the repo. A Netlify site connected to that repository can publish the updated snapshot on each commit.

## Easiest way to get a public URL (no GitHub needed for the first demo)
1. Download and unzip this package.
2. On a computer, open https://app.netlify.com/drop.
3. Drag the **`nfl_edge_2` folder** (or a folder containing `index.html`, `data/`, and `netlify.toml`) into the drop zone. Do not upload only `index.html`; the `data` folder is required.
4. Netlify will provide a public `*.netlify.app` URL. Keep the folder locally so you can redeploy updates.
5. The starter JSON currently contains clearly labeled illustrative demo data until you run the data pipeline successfully.

Official Netlify instructions: https://docs.netlify.com/start/quickstarts/netlify-drop-quickstart/

## To turn on automatic weekly data updates
A static hosting service does not itself run Python on a schedule. The included workflow runs weekly in GitHub Actions and regenerates `data/stats.json`. For Netlify to publish each refresh automatically:
1. Put this folder in a Git repository and connect that repository to Netlify (Netlify's Git integration automatically deploys new commits).
2. In the repository, go to Actions and run **Refresh NFL Edge data** once using **Run workflow**.
3. The workflow is scheduled for Tuesdays at 10:17 UTC. It can also be run manually.
4. Check the Actions run log. If the data provider changes schema or its release is not yet available, the run may fail; the existing JSON remains in place.
5. After a successful run, the workflow commits the updated `data/stats.json`. The Netlify Git integration should then redeploy the site.

If GitHub is giving you trouble, you can use Netlify Drop for a simple public demo now, then set up automation later. To get unattended weekly data refreshes, some repository or scheduled backend is needed; drag-and-drop hosting alone cannot run the Python pipeline.

## Run the pipeline locally
Requires Python 3.11+ and a working internet connection:
```bash
python -m pip install -r requirements.txt
python scripts/update_stats.py
```
It writes `data/stats.json`.

## Metrics and honest limitations
- **EPA/play:** mean EPA on scrimmage pass/run plays grouped by offense.
- **Success rate:** mean nflverse success indicator on those plays.
- **Explosive pass rate:** share of pass plays with a completion gaining 20+ yards.
- **Turnovers:** interception and fumble-lost flags summed on offensive play rows.
- **Pressure proxy:** recorded QB hit/sack on pass plays; not equivalent to charting-grade pressure rate.
- **Defensive EPA allowed:** mean opponent play EPA when the team is the defense.
- **Player production:** aggregates player yardage and TD fields in PBP; validate against official box scores before treating as authoritative.
- **Risk-worthy throws:** deliberately not fabricated; requires charting data not available in the basic nflverse play-by-play release.
- **Predictions:** this starter does not claim calibrated game probabilities. A trustworthy model needs historical train/test splits, opponent adjustments, injuries/availability, and calibration evaluation.
- Current-season data may not be released yet; the script tries the current year, then previous year.

## Notes
This is an independent project, not affiliated with the NFL. Review the data source's terms before commercial use. The team abbreviations are plain text, not official logos.
