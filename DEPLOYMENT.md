# Deployment Guide

Step-by-step instructions for deploying to Render.com (recommended — free tier available).

---

## Prerequisites

- GitHub account with the repo pushed
- NASA API key from [api.nasa.gov](https://api.nasa.gov/)
- Cesium Ion token from [ion.cesium.com](https://ion.cesium.com/)

---

## Deploy to Render.com

### 1. Create a Render account
Sign up at [render.com](https://render.com/) (free tier available).

### 2. Create a New Web Service
- Click **New +** → **Web Service**
- Connect your GitHub account and select the `Asteroid_Project` repository

### 3. Configure the service
| Setting | Value |
|---------|-------|
| **Name** | `asteroid-tracker` (or any name) |
| **Branch** | `main` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app` |
| **Instance Type** | Free (or Starter for better performance) |

Render will auto-detect the `Procfile` — the Start Command is filled in automatically.

### 4. Set Environment Variables
In the Render dashboard → **Environment** tab, add:

| Key | Value |
|-----|-------|
| `NASA_API_KEY` | Your NASA API key |
| `CESIUM_ION_TOKEN` | Your Cesium Ion token |
| `FLASK_DEBUG` | `false` |

### 5. Deploy
Click **Create Web Service**. Render will:
1. Clone the repo
2. Run `pip install -r requirements.txt`
3. Start gunicorn
4. Assign a URL like `https://asteroid-tracker.onrender.com`

First deploy takes 2–3 minutes. Subsequent deploys trigger automatically on every push to `main`.

### 6. Verify
Visit your Render URL. The app should load the asteroid table within 30 seconds.

**Note on cold starts:** Free tier services sleep after 15 minutes of inactivity. The first request after sleeping takes 30–60 seconds.

---

## Deploy to Railway

Alternative to Render with similar ease of use.

1. Go to [railway.app](https://railway.app/) → **New Project** → **Deploy from GitHub**
2. Select your repo
3. Railway auto-detects Python and uses the `Procfile`
4. Go to **Variables** and add `NASA_API_KEY` and `CESIUM_ION_TOKEN`
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
fly secrets set NASA_API_KEY=your_key CESIUM_ION_TOKEN=your_token
fly deploy
```

---

## Troubleshooting

### App crashes on startup
- Check logs in Render dashboard → **Logs** tab
- Ensure all packages in `requirements.txt` install successfully
- poliastro sometimes has build issues — if so, the app falls back to pure-math calculations automatically

### Asteroid data not loading
- Check `NASA_API_KEY` is set correctly
- `DEMO_KEY` has a rate limit of 30 req/hour — use a real key for production

### Globe not showing
- Check `CESIUM_ION_TOKEN` is set correctly
- Verify the token has not expired in your Cesium Ion dashboard

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

- First asteroid data load: ~15–30 seconds (fetches from NASA + JPL + Asterank)
- Subsequent loads: ~0.1 seconds (from cache)
- Mission planning: 5–60 seconds depending on window size
- Globe rendering: depends on user's GPU/browser
