# NEXUS ORBITAL
### Asteroid Mining Mission Intelligence

> The intersection of Earth and space resources using real NASA data, orbital mechanics, and mission planning in your browser.

A premium web platform for tracking near-Earth asteroids, estimating their mining value, and computing optimal spacecraft trajectories, all of which is visualized on a live 3D globe.

---

## Features

### Data & Analysis
- **365-Day NEO Tracking** — Live asteroid data from NASA NeoWs covering the next year of close approaches
- **Mining Value Intelligence** — Cross-referenced Asterank valuations with fuzzy name matching; diameter-based fallback ensures every asteroid has an estimate
- **Orbital Elements** — Keplerian parameters from JPL Small-Body Database for the 20 closest NEOs
- **Search, Sort & Filter** — Live name search, sortable columns, distance/value filters, pagination

### 3D Visualization
- **Interactive 3D Globe** — CesiumJS Earth with launchpad markers and real asteroid positions in space
- **Glowing Trajectory Arcs** — Bezier arc rendered from launch site to asteroid, color-coded by profitability (green/amber/red)
- **Draggable Split Layout** — Resize globe and data panel with drag handle; preset layouts (60/40, 50/50, 40/60, full globe, full data)

### Mission Planning
- **Mission Trajectory Planner** — Lambert's problem solver (poliastro + vis-viva fallback) for optimal departure window and flight path
- **Rocket Matching Engine** — Delta-v requirements matched against Falcon 9/Heavy, SLS, Ariane 6, Proton, and more
- **ROI Analysis** — Full cost model with sensitivity sliders; ranked by profit
- **Mission Comparison** — Side-by-side table for up to 5 mission options

### Mission Dashboard (8 tabs)
- **Overview** — Mission patch, key stats, timeline, asteroid and mission profile
- **Rocket** — Full specifications + interactive Three.js 3D rocket model with auto-rotate, human scale reference, and 10-second launch countdown sequence
- **Launch Site** — Dark satellite map (CARTO tiles) with coordinate popup, strategic advantages, and notable historical missions
- **Trajectory** — Heliocentric orbit canvas with animated spacecraft, Δv budget bar, transfer orbit elements, porkchop plot (launch opportunity map)
- **Cost Analysis** — Profit/ROI hero banner, waterfall chart, donut chart, interactive sensitivity sliders
- **Timeline** — Gantt chart across all mission phases, key milestones list
- **Risk Assessment** — Risk matrix quadrant, overall risk gauge, 8 individual risk cards with severity ratings
- **Resources** — Data exports (JSON, CSV, iCal), share URL, copy text summary, external links, glossary

### Productivity
- **My Missions** — Save, duplicate, and delete missions; persistent across browser sessions (localStorage)
- **First-Visit Hint** — Welcome toast for new users
- **Data Freshness** — Timestamp + one-click cache refresh
- **Keyboard Shortcuts** — F (search), T (clear trajectory), 1–5 (view trajectory by rank), Ctrl+[/] (resize panel), ? (shortcuts)
- **Deployment Ready** — Procfile, gunicorn, runtime.txt, .env.example included

---

## Screenshots

> *Full-screen dark space UI with globe, mission cards, and trajectory arc visualization*

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 · Flask · Flask-CORS |
| Orbital Mechanics | poliastro 0.7 · astropy 7.2 · NumPy · SciPy |
| 3D View | Plotly.js 2.27.0 (WebGL) |
| Fonts | Inter (Google Fonts) |
| Data Sources | NASA NeoWs · JPL SBDB · Asterank |
| Deployment | gunicorn · Render / Railway / Fly.io |

---

## Run locally (macOS, Linux, or Windows)

This is a **Python Flask web app**. Start the Python server, then open its URL in your browser. Double-clicking `app.py` or opening `templates/index.html` directly will not launch the app correctly. No Node.js/npm build is needed.

### 1. Get the project

Either clone the repository:

```bash
git clone https://github.com/AaravTandon582/Nexus-Orbital.git
cd Nexus-Orbital
```

Or choose **Code → Download ZIP** on GitHub, extract the entire ZIP, and open a terminal inside the extracted `Nexus-Orbital-master-temp` folder (the current default branch is `master-temp`). The folder name can differ if you downloaded another branch. You should see `app.py`, `requirements.txt`, and `templates/` in that folder. Do not run from inside the ZIP or from the `templates` folder.

### 2. Install dependencies with Python 3.11

Use **64-bit Python 3.11** for the pinned dependencies in this repository. A clean installation was verified with Python 3.11.15 on macOS; other Python versions are not covered by that check. Install Python 3.11 before continuing if the version command below is unavailable.

**macOS / Linux:**

```bash
python3.11 --version
python3.11 -m venv venv
./venv/bin/python -m pip install --upgrade pip
./venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

**Windows PowerShell:**

```powershell
py -3.11 --version
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

These commands use the virtual environment's Python directly, so activation and PowerShell execution-policy changes are unnecessary. If you already have a `venv` created with another Python version, rename that folder before creating the Python 3.11 environment. Only copy `.env.example` on first setup; do not overwrite an existing `.env` containing your key.

### 3. Configure your NASA API key

Get a free key from [NASA Open APIs](https://api.nasa.gov/). Open `.env` in a text editor and replace the placeholder:

```env
NASA_API_KEY=replace_with_your_real_nasa_api_key
PORT=8080
FLASK_DEBUG=false
```

Save it as exactly `.env` in the same folder as `app.py`, not `.env.txt`. The app loads it automatically. Keep your key private; `.env` is excluded from Git.

A valid NASA key is needed for reliable asteroid data. Leaving the placeholder unchanged causes NASA requests to fail. The built-in `DEMO_KEY` fallback is rate-limited and is unsuitable for this app's year-long feed. The page can start before data is available.

**A Cesium Ion token is not required for the current UI.** The current 3D view uses Plotly from a CDN. `CESIUM_ION_TOKEN` is a legacy backend setting and can remain blank. Internet access is needed for NASA/JPL/Asterank data and the browser's external scripts; use a browser with WebGL enabled.

### 4. Start the server

Run from the project folder:

**macOS / Linux:**

```bash
./venv/bin/python app.py
```

**Windows PowerShell:**

```powershell
.\venv\Scripts\python.exe app.py
```

Keep the terminal open and visit **http://127.0.0.1:8080**. The browser does not open automatically. Use the port printed by Flask if you changed `PORT`. Stop the server with **Ctrl+C**. To launch again later, open a terminal in the same project folder and repeat this step; you do not need to reinstall dependencies or recopy `.env`.

The page should appear while asteroid data loads in the background. The first data fetch can take a minute or longer depending on the upstream services. Wait for `[startup] Asteroid cache ready.` in the terminal. That message means the fetch completed; an empty table can still indicate a key or network problem. Results are cached for six hours.

### Launch troubleshooting

| Symptom | What to do |
|---------|------------|
| `python3.11` or `py` is not found | Install 64-bit Python 3.11, then reopen your terminal. On Windows, enable the Python launcher in the installer. |
| `can't open file 'app.py'` or `requirements.txt` not found | Change into the extracted/cloned project folder containing both files. |
| `ModuleNotFoundError: flask`, `dotenv`, or another dependency | Finish the dependency installation in step 2, then launch with the same `venv` Python shown above. |
| `No matching distribution`, `Requires-Python`, or a package build failure | Check the Python version and use a fresh Python 3.11 environment. Do not continue after a failed install; the runtime orbital fallback cannot repair pip installation errors. |
| Browser says connection refused | Keep the server terminal open, check for a traceback, and use the exact port in Flask's startup output. Opening the HTML file directly will not work. |
| Server starts on 5000 instead of 8080 | Older copies of `.env.example` used `PORT=5000`. Set `PORT=8080` in your existing `.env`, restart, and open `http://127.0.0.1:8080`. |
| `Address already in use` / port access error | Set `PORT=8081` in `.env`, restart, and open `http://127.0.0.1:8081`. |
| `.env` edits seem ignored | Restart the server and check for `.env.txt`. Existing terminal environment variables take precedence over `.env`; remove or update any previously exported `PORT` or `NASA_API_KEY`. |
| Page loads but asteroid table is empty | Check your NASA key and terminal warnings for authorization, rate-limit, or network errors. After fixing the key, restart and use the UI's cache refresh button. |
| Data stays empty after fixing the key | Stop the server and delete only `asteroid_cache.json` and `asteroid_full_cache.json` from the project folder if present, then restart. Failed fetches can leave an empty cache. |
| Blank 3D view | Check browser WebGL support and access to `cdn.plot.ly` and `cdn.jsdelivr.net`; a Cesium token will not fix the current Plotly view. |
| `poliastro/astropy unavailable ... using fallback math` | This is an informational message: the existing mission planner uses approximate orbital math when the optional imports are unavailable. |
| Gunicorn fails on Windows | Use the local `python.exe app.py` command above. Gunicorn is for the Unix hosting setup in [DEPLOYMENT.md](DEPLOYMENT.md). |

---

## How to Use NEXUS ORBITAL

1. **Browse NEOs** — The table loads automatically with asteroids within 0.05 AU. Use search, filters, and column sorting to find targets.
2. **Select a target** — Click any row to select an asteroid. Its data populates the Mission Planner below.
3. **Plan a mission** — Set departure window dates and max flight time, then click **Compute Optimal Missions**.
4. **Review results** — Up to 5 ranked mission options appear with Δv, cost, profit, and ROI.
5. **View trajectory** — Click **View Trajectory** on any mission card to render the arc on the globe.
6. **Compare missions** — Check missions and click **Compare Selected** for a side-by-side breakdown.

**Keyboard shortcuts:** `F` = focus search · `T` = clear trajectory · `1-5` = view trajectory by rank · `?` = shortcuts panel

---

## How It Works

### Data Pipeline
```
NASA NeoWs (365-day feed) ──┐
                            ├─→ Merge & Cache (JSON, 6h TTL)
Asterank valuations ────────┤
                            └─→ Enrich top-20 with JPL orbital elements
```

### Orbital Mechanics
- Keplerian propagation from orbital elements (mean anomaly → true anomaly via Newton's method)
- Transfer orbits via Lambert's problem (poliastro/izzo solver, vis-viva Hohmann fallback)
- Coarse grid scan (departure date × time-of-flight) minimizes Δv; winner refined with Lambert
- Globe trajectory arcs: quadratic Bezier from launch site ECEF → asteroid ECEF, bowing outward

### Cost Model
```
Mission Cost = Rocket Launch Cost
             + Spacecraft Cost (mass × $50,000/kg)
             + Operations Cost (flight_days/30 × $1M/month)
```

### Limitations
- Positions computed in heliocentric ecliptic frame, displayed in Cesium ECEF — visually plausible but not frame-accurate
- Mining value estimates are speculative (composition data sparse)
- Not suitable for actual mission planning

---

## Project Structure

```
Nexus-Orbital/
├── app.py               Routes, API endpoints, mission cache
├── asteroid_data.py     NASA NeoWs · JPL SBDB · Asterank · fuzzy name matching
├── launchpad_data.py    Launch Library 2 + curated rocket database
├── mission_planner.py   Lambert solver · position propagation · ROI analysis
├── templates/
│   ├── index.html       Full NEXUS ORBITAL UI (globe + panel + all features)
│   └── error.html       Custom 404/500 pages
├── requirements.txt
├── Procfile             gunicorn config
├── runtime.txt          Python 3.11.9
├── .env.example         Local environment template (port 8080)
└── DEPLOYMENT.md        Step-by-step deployment guide
```

---

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for full instructions (Render · Railway · Fly.io).

Quick deploy to Render:
1. Push to GitHub
2. New Web Service → connect repo
3. Set `NASA_API_KEY` and a Python 3.11 runtime as described in the deployment guide
4. Enter the build and start commands from the guide explicitly

---

## Future Improvements

- SQLite cache for 365-day dataset performance
- Porkchop plot (departure × TOF heatmap) for visual launch window selection
- Real asteroid composition data for accurate resource estimates
- User accounts and saved mission plans
- Multi-asteroid simultaneous trajectory display

---

## Credits

- [NASA NeoWs API](https://api.nasa.gov/) — Near-Earth Object feed
- [JPL Small-Body Database](https://ssd.jpl.nasa.gov/) — Orbital elements
- [Asterank](http://www.asterank.com/) — Mining value estimates
- [CesiumJS](https://cesium.com/) — 3D globe engine
- [poliastro](https://docs.poliastro.space/) — Orbital mechanics
- [Space Devs / Launch Library 2](https://ll.thespacedevs.com/) — Launchpad & rocket data

---

## License

MIT License

---

**Disclaimer:** NEXUS ORBITAL is an educational demonstration project. It is not affiliated with NASA, JPL, SpaceX, or any space agency. All cost estimates and profit projections are speculative approximations not suitable for real mission planning.
