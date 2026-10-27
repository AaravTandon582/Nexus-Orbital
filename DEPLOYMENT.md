# Deployment Guide

Hosting instructions for Nexus Orbital. To run a GitHub download on your own computer, follow the [local setup in README.md](README.md#run-locally-macos-linux-or-windows) first.

---

## Prerequisites

- GitHub account with the repo pushed
- NASA API key from [api.nasa.gov](https://api.nasa.gov/)
- Python 3.11 for the pinned dependencies

The current UI uses Plotly and does not require a Cesium Ion token.

---

## Deploy to Render.com

### 1. Create a Render account
Sign up at [render.com](https://render.com/) (free tier available).

### 2. Create a New Web Service
- Click **New +** → **Web Service**
- Connect your GitHub account and select the `Nexus-Orbital` repository

### 3. Configure the service
| Setting | Value |
|---------|-------|
| **Name** | `asteroid-tracker` (or any name) |
| **Branch** | `master-temp` (current default branch) |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT` |
| **Instance Type** | Free (or Starter for better performance) |

Enter both commands explicitly in Render; the start command matches the repository's `Procfile`. See [Render's Flask deployment guide](https://render.com/docs/deploy-flask).

### 4. Set Environment Variables
In the Render dashboard → **Environment** tab, add:

| Key | Value |
|-----|-------|
| `NASA_API_KEY` | Your NASA API key |
| `PYTHON_VERSION` | `3.11.15` (the Python version used for the clean-install check) |
| `FLASK_DEBUG` | `false` |

Render supports an explicit `PYTHON_VERSION` environment variable; do not rely on `runtime.txt` to select its runtime. See [Render's Python version configuration](https://render.com/docs/python-version). Let the hosting platform provide `PORT`; the `.env.example` port is for local use.

### 5. Deploy
Click **Create Web Service**. Render will:
1. Clone the repo
2. Run `pip install -r requirements.txt`
3. Start gunicorn
4. Assign a URL like `https://asteroid-tracker.onrender.com`

First deploy takes 2–3 minutes. Subsequent deploys trigger automatically on pushes to the branch connected to the service.

### 6. Verify
Visit your Render URL. The page can load before the asteroid table. The initial NASA/JPL/Asterank fetch may take a minute or longer; check the service logs for API errors and `[startup] Asteroid cache ready.`. An empty result can also be cached, so confirm that records actually appear.

**Note on cold starts:** Free tier services sleep after 15 minutes of inactivity. The first request after sleeping takes 30–60 seconds.

---

## Deploy to Railway

Alternative to Render with similar ease of use.

1. Go to [railway.app](https://railway.app/) → **New Project** → **Deploy from GitHub**
2. Select your repo
3. Railway auto-detects Python and uses the `Procfile`
4. Go to **Variables** and add `NASA_API_KEY`; configure the build runtime to use Python 3.11
5. Railway assigns a domain automatically

---

## Deploy to Fly.io

For more control and zero cold starts.

```bash
# Install flyctl
brew install flyctl

# Login
fly auth login

# In the project directory
fly launch   # follows prompts, creates fly.toml
fly secrets set NASA_API_KEY=your_key
fly deploy
```

---

## Troubleshooting

### App crashes on startup
- Check logs in Render dashboard → **Logs** tab
- Ensure all packages in `requirements.txt` install successfully
- If pip fails, fix the installation first: use Python 3.11 and rerun the build command. The pure-math fallback handles unavailable orbital imports at runtime; it does not bypass a failed dependency installation.

### Asteroid data not loading
- Check `NASA_API_KEY` is set correctly
- Use a real NASA key; `DEMO_KEY` is rate-limited and unsuitable for this app's year-long feed
- After correcting a key, refresh the cache in the UI; a failed fetch may have cached an empty result

### 3D view not showing
- The current UI uses Plotly, so a Cesium token is not needed
- Check WebGL support and browser access to `cdn.plot.ly` and `cdn.jsdelivr.net`

### Mission planning times out
- The free Render tier has limited CPU — mission planning may take longer
- Upgrade to Starter plan for consistent performance
- The app has a 90-second timeout built in

### Cache issues
- The app caches asteroid data for 6 hours in JSON files
- On Render free tier, the filesystem resets on each deploy — data will be re-fetched
- For persistent caching, use a Redis add-on or switch to a database

---

## Performance Notes

- First asteroid data load: can take a minute or longer (fetches from NASA + JPL + Asterank)
- Subsequent loads: ~0.1 seconds (from cache)
- Mission planning: 5–60 seconds depending on window size
- Globe rendering: depends on user's GPU/browser
