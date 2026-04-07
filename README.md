# NEXUS ORBITAL
### Asteroid Mining Mission Intelligence

> The intersection of Earth and space resources — real NASA data, orbital mechanics, and mission planning in your browser.

A premium web platform for tracking near-Earth asteroids, estimating their mining value, and computing optimal spacecraft trajectories — all visualized on a live 3D globe.

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
| 3D Globe | CesiumJS 1.114 |
| Fonts | Inter (Google Fonts) |
| Data Sources | NASA NeoWs · JPL SBDB · Asterank |
| Deployment | gunicorn · Render / Railway / Fly.io |

---

## API Keys Required

| Service | Where to get it |
|---------|----------------|
| **NASA API Key** | [api.nasa.gov](https://api.nasa.gov/) — free, instant registration |
| **Cesium Ion Token** | [ion.cesium.com](https://ion.cesium.com/) — free account → default token |

---

## Installation

### Prerequisites
- Python 3.11+
- pip

### Setup

```bash
# 1. Clone
git clone https://github.com/AaravTandon582/Asteroid_Project.git
cd Asteroid_Project

# 2. Virtual environment
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate

# 3. Dependencies
pip install -r requirements.txt

# 4. Environment
cp .env.example .env
# Edit .env → add NASA_API_KEY and CESIUM_ION_TOKEN

# 5. Run
python app.py
# → http://localhost:8080
```

### `.env` file

```env
NASA_API_KEY=your_nasa_api_key
CESIUM_ION_TOKEN=your_cesium_token
PORT=8080
FLASK_DEBUG=false
```

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
Asteroid_Project/
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
├── .env.example         Required environment variables
└── DEPLOYMENT.md        Step-by-step deployment guide
```

---

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for full instructions (Render · Railway · Fly.io).

Quick deploy to Render:
1. Push to GitHub
2. New Web Service → connect repo
3. Set `NASA_API_KEY` and `CESIUM_ION_TOKEN` in Environment
4. Auto-detected `Procfile` handles the rest

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
