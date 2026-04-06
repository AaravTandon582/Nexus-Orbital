import requests
import json
import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")
CACHE_FILE      = "asteroid_cache.json"       # raw NASA NEO feed
FULL_CACHE_FILE = "asteroid_full_cache.json"  # fully enriched output
CACHE_HOURS = 6


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def load_cache():
    """Return cached data if it exists and is fresh, else None."""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r") as f:
            cached = json.load(f)
        saved_at = datetime.fromisoformat(cached["timestamp"])
        if datetime.now() - saved_at < timedelta(hours=CACHE_HOURS):
            return cached["data"]
    except (KeyError, ValueError, json.JSONDecodeError):
        pass
    return None


def save_cache(data):
    """Save data with current timestamp to cache file."""
    payload = {"timestamp": datetime.now().isoformat(), "data": data}
    with open(CACHE_FILE, "w") as f:
        json.dump(payload, f)


# ---------------------------------------------------------------------------
# NASA NeoWs feed
# ---------------------------------------------------------------------------

def fetch_neo_feed(start_date, end_date):
    """
    Fetch near-Earth object feed from NASA NeoWs for a date range.
    Handles the 7-day API limit by chunking automatically.
    Uses local cache when fresh data is available.
    Returns a deduplicated list of asteroid dicts.
    """
    cached = load_cache()
    if cached is not None:
        return cached

    url = "https://api.nasa.gov/neo/rest/v1/feed"
    asteroids_by_id = {}

    current = start_date
    while current < end_date:
        chunk_end = min(current + timedelta(days=7), end_date)
        params = {
            "start_date": current.strftime("%Y-%m-%d"),
            "end_date": chunk_end.strftime("%Y-%m-%d"),
            "api_key": NASA_API_KEY,
        }
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"Warning: NeoWs request failed for {params['start_date']}: {e}")
            current = chunk_end + timedelta(days=1)
            continue

        for date_str, neo_list in data.get("near_earth_objects", {}).items():
            for neo in neo_list:
                try:
                    neo_id = neo["id"]
                    name = neo["name"]
                    abs_mag = neo["absolute_magnitude_h"]

                    diam = neo["estimated_diameter"]["kilometers"]
                    diameter_km = (
                        diam["estimated_diameter_min"] + diam["estimated_diameter_max"]
                    ) / 2

                    is_hazardous = neo["is_potentially_hazardous_asteroid"]

                    approach = neo["close_approach_data"][0]
                    close_approach_date = approach["close_approach_date"]
                    velocity_km_s = float(
                        approach["relative_velocity"]["kilometers_per_second"]
                    )
                    miss_distance_au = float(approach["miss_distance"]["astronomical"])
                    miss_distance_km = float(approach["miss_distance"]["kilometers"])

                    asteroid = {
                        "id": neo_id,
                        "name": name,
                        "absolute_magnitude_h": abs_mag,
                        "diameter_km": round(diameter_km, 4),
                        "is_potentially_hazardous_asteroid": is_hazardous,
                        "close_approach_date": close_approach_date,
                        "velocity_km_s": round(velocity_km_s, 4),
                        "miss_distance_au": round(miss_distance_au, 6),
                        "miss_distance_km": round(miss_distance_km, 2),
                    }

                    # Keep the closest approach when duplicates exist
                    if (
                        neo_id not in asteroids_by_id
                        or asteroid["miss_distance_au"]
                        < asteroids_by_id[neo_id]["miss_distance_au"]
                    ):
                        asteroids_by_id[neo_id] = asteroid

                except (KeyError, IndexError, ValueError, TypeError):
                    continue

        current = chunk_end + timedelta(days=1)

    results = list(asteroids_by_id.values())
    save_cache(results)
    return results


# ---------------------------------------------------------------------------
# JPL SBDB orbital elements
# ---------------------------------------------------------------------------

def fetch_orbital_elements(asteroid_id):
    """
    Fetch orbital elements for a single asteroid from JPL SBDB.
    Returns a dict with orbital parameters or an empty dict on failure.
    """
    url = "https://ssd-api.jpl.nasa.gov/sbdb.api"
    params = {"sstr": asteroid_id, "phys-par": "true"}
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()

        orbit = data.get("orbit", {})
        elements = {e["label"]: e.get("value") for e in orbit.get("elements", [])}

        return {
            "eccentricity": elements.get("e"),
            "semi_major_axis_au": elements.get("a"),
            "inclination_deg": elements.get("i"),
            "longitude_ascending_node_deg": elements.get("om"),
            "argument_of_perihelion_deg": elements.get("w"),
            "mean_anomaly_deg": elements.get("M"),
            "epoch": orbit.get("epoch"),
        }
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Orbit enrichment
# ---------------------------------------------------------------------------

def enrich_with_orbits(asteroids):
    """
    Fetch orbital elements for the 20 closest asteroids (by miss distance).
    Merges orbital data into those asteroids and returns the full list.
    """
    sorted_all = sorted(asteroids, key=lambda a: a["miss_distance_au"])
    top_20 = sorted_all[:20]
    rest = sorted_all[20:]

    enriched = []
    for asteroid in top_20:
        orbital = fetch_orbital_elements(asteroid["id"])
        enriched.append({**asteroid, **orbital})
        time.sleep(0.5)

    return enriched + rest


# ---------------------------------------------------------------------------
# Asterank valuations
# ---------------------------------------------------------------------------

def fetch_asterank_data():
    """
    Fetch asteroid valuation data from Asterank API.
    Returns a dict keyed by cleaned asteroid name.
    """
    url = "http://www.asterank.com/api/asterank?query={}&limit=1000"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        records = response.json()

        result = {}
        for record in records:
            try:
                raw_name = record.get("full_name", "")
                clean = _clean_name(raw_name)
                result[clean] = {
                    "full_name": raw_name,
                    "profit": record.get("profit"),
                    "price": record.get("price"),
                    "closeness": record.get("closeness"),
                    "spec_B": record.get("spec_B"),
                }
            except Exception:
                continue
        return result
    except Exception as e:
        print(f"Warning: Asterank API failed: {e}")
        return {}


def _clean_name(name):
    """Lowercase, remove parenthetical segments, collapse whitespace.
    Primary key used by fetch_asterank_data for its lookup table.
    """
    import re
    name = re.sub(r"\(.*?\)", "", name)
    return " ".join(name.lower().split())


def _name_candidates(name):
    """
    Generate multiple lookup-key candidates for a NASA asteroid name so we
    have the best chance of matching against Asterank's naming convention.

    NASA formats seen in practice:
      "(2013 GM3)"          → designation inside parens, no proper name
      "363599 (2004 FG11)"  → number + designation in parens
      "(433) Eros (1898 DQ)"→ number in parens, proper name, old designation
      "326290 Akhenaten (1998 HE3)"

    Asterank formats:
      "433 eros", "2013 gm3", "1 ceres"
    """
    import re

    low = name.lower()

    # All content inside any set of parentheses
    parens_texts = re.findall(r"\(([^)]+)\)", low)

    # Text with ALL parenthetical segments removed
    stripped = re.sub(r"\(.*?\)", "", low)
    stripped = " ".join(stripped.split())

    candidates = set()

    # 1. Each parenthetical chunk on its own
    for pt in parens_texts:
        pt = " ".join(pt.split())
        if pt:
            candidates.add(pt)

    # 2. Stripped text alone
    if stripped:
        candidates.add(stripped)

    # 3. Leading number from stripped + each paren text
    num_match = re.match(r"^(\d+)", stripped)
    leading_num = num_match.group(1) if num_match else None
    if leading_num:
        for pt in parens_texts:
            pt = " ".join(pt.split())
            candidates.add(f"{leading_num} {pt}")
            candidates.add(f"{pt} {leading_num}")

    # 4. Combination of first-paren and stripped
    if parens_texts and stripped:
        fp = " ".join(parens_texts[0].split())
        candidates.add(f"{fp} {stripped}")
        candidates.add(f"{stripped} {fp}")

    # 5. Full name normalised (no parens removal)
    candidates.add(" ".join(low.split()))

    # Remove empty and very-short noise tokens
    return {c for c in candidates if len(c) > 1}


def _estimate_value_usd(diameter_km):
    """
    Rough mining-value estimate based on diameter alone when Asterank has
    no record.  Assumes average bulk density ~2 g/cm³ and a mix of water,
    silicates, and metals at ~$1 per kg of accessible resource.
    Returns USD float.
    """
    if not diameter_km or diameter_km <= 0:
        return None
    radius_km = diameter_km / 2.0
    # Volume of sphere (km³)
    vol_km3 = (4.0 / 3.0) * 3.14159 * radius_km ** 3
    # Convert to tonnes: 1 km³ × 2e9 t/km³ (2 g/cm³ density)
    mass_tonnes = vol_km3 * 2e9
    # Rough value: $500/tonne accessible resource (very conservative)
    value_usd = mass_tonnes * 500
    return round(value_usd)


# ---------------------------------------------------------------------------
# Merge valuations
# ---------------------------------------------------------------------------

def merge_valuations(asteroids, asterank_data):
    """
    Match NASA asteroids to Asterank records using multiple name-key
    candidates.  Falls back to a diameter-based estimate when no Asterank
    record is found so the UI always shows a value.
    """
    for asteroid in asteroids:
        raw_name = asteroid.get("name", "")
        candidates = _name_candidates(raw_name)

        match = None
        for key in candidates:
            if key in asterank_data:
                match = asterank_data[key]
                break

        if match:
            asteroid["profit"] = match.get("profit")
            asteroid["price"] = match.get("price")
        else:
            # No Asterank record — use diameter-based estimate
            estimated = _estimate_value_usd(asteroid.get("diameter_km"))
            asteroid["profit"] = estimated
            asteroid["price"] = estimated
    return asteroids


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------

def filter_asteroids(
    asteroids, max_distance_au=0.05, min_value=None, hazardous_only=False
):
    """
    Filter and sort asteroids.

    Parameters
    ----------
    max_distance_au : float
        Maximum miss distance in AU to include.
    min_value : float or None
        Minimum Asterank profit value to include (ignored when None).
    hazardous_only : bool
        When True, include only potentially hazardous asteroids.
    """
    filtered = []
    for a in asteroids:
        if a["miss_distance_au"] > max_distance_au:
            continue
        if hazardous_only and not a.get("is_potentially_hazardous_asteroid"):
            continue
        if min_value is not None:
            profit = a.get("profit")
            if profit is None or profit < min_value:
                continue
        filtered.append(a)

    filtered.sort(key=lambda a: a["miss_distance_au"])
    return filtered


# ---------------------------------------------------------------------------
# Full-cache helpers (caches fully enriched data, not just raw NEO feed)
# ---------------------------------------------------------------------------

def _load_full_cache():
    """Return fully-enriched asteroid list if cache is fresh, else None."""
    if not os.path.exists(FULL_CACHE_FILE):
        return None
    try:
        with open(FULL_CACHE_FILE, "r") as f:
            cached = json.load(f)
        saved_at = datetime.fromisoformat(cached["timestamp"])
        if datetime.now() - saved_at < timedelta(hours=CACHE_HOURS):
            return cached["data"]
    except (KeyError, ValueError, json.JSONDecodeError):
        pass
    return None


def _save_full_cache(data):
    """Save fully-enriched asteroid list with current timestamp."""
    payload = {"timestamp": datetime.now().isoformat(), "data": data}
    with open(FULL_CACHE_FILE, "w") as f:
        json.dump(payload, f)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def get_asteroid_data(days_ahead=60, max_distance_au=0.05):
    """
    Fetch, enrich, and return asteroid data for the next `days_ahead` days.

    Caches the *fully enriched* result (NASA feed + Asterank valuations +
    JPL orbital elements) so repeated calls are instant instead of ~15 s.

    Parameters
    ----------
    days_ahead : int
        Number of days ahead from today to search.
    max_distance_au : float
        Passed through to filter_asteroids (not applied here — callers filter).

    Returns
    -------
    list of dict
        Fully enriched asteroid records.
    """
    # Fast path: return cached enriched data when fresh
    cached = _load_full_cache()
    if cached is not None:
        return cached

    # Slow path: fetch + enrich + save
    today = datetime.now().date()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today + timedelta(days=days_ahead), datetime.min.time())

    asteroids = fetch_neo_feed(start, end)
    asterank_data = fetch_asterank_data()
    asteroids = merge_valuations(asteroids, asterank_data)
    asteroids = enrich_with_orbits(asteroids)

    _save_full_cache(asteroids)
    return asteroids


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Fetching asteroid data (60-day window)...")
    all_asteroids = get_asteroid_data(days_ahead=60)

    nearby = filter_asteroids(all_asteroids, max_distance_au=0.05)

    print(f"\nTotal asteroids fetched : {len(all_asteroids)}")
    print(f"Within 0.05 AU          : {len(nearby)}\n")

    header = (
        f"{'Name':<35} {'Diameter (km)':>13} {'Distance (AU)':>13} "
        f"{'Velocity (km/s)':>16} {'Value (USD)':>15} {'Hazardous':>9}"
    )
    print(header)
    print("-" * len(header))

    for a in nearby[:20]:
        name = a["name"][:34]
        diameter = f"{a['diameter_km']:.3f}"
        distance = f"{a['miss_distance_au']:.5f}"
        velocity = f"{a['velocity_km_s']:.2f}"
        value = f"${a['price']:,.0f}" if a.get("price") is not None else "N/A"
        hazardous = "YES" if a.get("is_potentially_hazardous_asteroid") else "no"

        print(
            f"{name:<35} {diameter:>13} {distance:>13} "
            f"{velocity:>16} {value:>15} {hazardous:>9}"
        )
