import requests
import json
import os

CACHE_FILE = "launchpad_cache.json"
BASE_URL = "https://ll.thespacedevs.com/2.2.0"

# ---------------------------------------------------------------------------
# Cost and capacity reference data
# ---------------------------------------------------------------------------

ROCKET_SPECS = {
    "Falcon 9":      {"cost": 67_000_000,    "leo_capacity": 22_800},
    "Falcon Heavy":  {"cost": 150_000_000,   "leo_capacity": 63_800},
    "SLS":           {"cost": 2_000_000_000, "leo_capacity": 95_000},
    "Soyuz":         {"cost": 50_000_000,    "leo_capacity": 7_020},
    "Ariane 5":      {"cost": 180_000_000,   "leo_capacity": 20_000},
    "Ariane 6":      {"cost": 115_000_000,   "leo_capacity": 21_650},
    "PSLV":          {"cost": 30_000_000,    "leo_capacity": 3_800},
    "GSLV":          {"cost": 55_000_000,    "leo_capacity": 10_000},
    "H-IIA":         {"cost": 90_000_000,    "leo_capacity": 15_000},
    "H-IIB":         {"cost": 90_000_000,    "leo_capacity": 16_500},
    "Electron":      {"cost": 7_500_000,     "leo_capacity": 300},
    "Proton":        {"cost": 65_000_000,    "leo_capacity": 23_000},
}

# Simplified pad → rocket mapping for the prototype.
# Keys are substrings of the actual Launch Library 2 pad names (case-insensitive).
PAD_ROCKET_MAP = {
    # USA — Kennedy Space Center
    "Launch Complex 39A":        ["Falcon 9", "Falcon Heavy"],
    "Launch Complex 39B":        ["SLS"],
    # USA — Vandenberg
    "Space Launch Complex 4E":   ["Falcon 9"],
    # Kazakhstan — Baikonur
    "81/23":                     ["Proton"],
    "1/5":                       ["Soyuz"],
    "Site 1":                    ["Soyuz"],
    # French Guiana — Kourou
    "Ariane Launch Area 3":      ["Ariane 5", "Ariane 6"],
    "Ariane Launch Area 4":      ["Ariane 5"],
    # India — Sriharikota
    "Satish Dhawan":             ["PSLV", "GSLV"],
    # Japan — Tanegashima
    "Yoshinobu":                 ["H-IIA", "H-IIB"],
    # New Zealand — Rocket Lab
    "LC-1":                      ["Electron"],
}


# ---------------------------------------------------------------------------
# Cache helpers (no expiration — launchpad data rarely changes)
# ---------------------------------------------------------------------------

def load_cache():
    """Return cached data if the cache file exists, otherwise None."""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_cache(data):
    """Save data to the cache file as JSON."""
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _paginate(url):
    """
    Generator that yields items from a paginated Launch Library 2 endpoint.
    Stops when the 'next' field is null or all pages have been fetched.
    Handles HTTP / connection errors gracefully.
    """
    while url:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                print("Warning: Launch Library 2 rate limit reached (15 req/hr). "
                      "Using partial data.")
            else:
                print(f"Warning: HTTP error fetching {url}: {e}")
            break
        except requests.RequestException as e:
            print(f"Warning: Request failed for {url}: {e}")
            break

        for item in data.get("results", []):
            yield item

        url = data.get("next")  # None when last page


# ---------------------------------------------------------------------------
# Fetch launchpads
# ---------------------------------------------------------------------------

def fetch_launchpads():
    """
    Fetch all launch pads from Launch Library 2.
    Returns a list of dicts with id, name, latitude, longitude, and location.
    """
    url = f"{BASE_URL}/pad/?limit=100&offset=0"
    print(f"[DEBUG] Fetching launchpads from: {url}")

    # Make the first request manually so we can log response details
    try:
        response = requests.get(url, timeout=30)
        print(f"[DEBUG] HTTP status: {response.status_code}")
        print(f"[DEBUG] Response text (first 500 chars): {response.text[:500]}")
        response.raise_for_status()
        first_page = response.json()
    except requests.exceptions.HTTPError as e:
        print(f"[DEBUG] HTTP error: {e}")
        print(f"[DEBUG] Response body: {response.text[:500]}")
        return []
    except requests.RequestException as e:
        print(f"[DEBUG] Request failed: {e}")
        return []

    raw_count = first_page.get("count", 0)
    print(f"[DEBUG] API reports {raw_count} total pads")
    print(f"[DEBUG] Pads in first page: {len(first_page.get('results', []))}")

    # Collect all pads across all pages (first page already fetched)
    all_pads_raw = list(first_page.get("results", []))
    next_url = first_page.get("next")
    while next_url:
        try:
            resp = requests.get(next_url, timeout=30)
            resp.raise_for_status()
            page = resp.json()
            all_pads_raw.extend(page.get("results", []))
            next_url = page.get("next")
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 429:
                print("[DEBUG] Rate limit hit (429). Using pads fetched so far.")
            else:
                print(f"[DEBUG] HTTP error on pagination: {e}")
            break
        except requests.RequestException as e:
            print(f"[DEBUG] Pagination request failed: {e}")
            break

    print(f"[DEBUG] Total raw pads fetched across all pages: {len(all_pads_raw)}")

    pads = []
    for pad in all_pads_raw:
        try:
            location = pad.get("location") or {}
            pads.append({
                "id": pad["id"],
                "name": pad["name"],
                "latitude": pad.get("latitude"),
                "longitude": pad.get("longitude"),
                "location": {
                    "name": location.get("name"),
                    "country_code": location.get("country_code"),
                },
            })
        except (KeyError, TypeError):
            continue

    print(f"[DEBUG] Pads after parsing (no status filter): {len(pads)}")
    return pads


# ---------------------------------------------------------------------------
# Fetch launch vehicles
# ---------------------------------------------------------------------------

def fetch_launch_vehicles():
    """
    Fetch launcher configurations from Launch Library 2.
    Returns a list of dicts with id, name, family, leo_capacity, gto_capacity.
    """
    url = f"{BASE_URL}/config/launcher/?limit=100&offset=0"
    launchers = []

    for launcher in _paginate(url):
        try:
            launchers.append({
                "id": launcher["id"],
                "name": launcher["name"],
                "family": launcher.get("launch_vehicle_family") or launcher.get("family", ""),
                "leo_capacity": launcher.get("leo_capacity"),
                "gto_capacity": launcher.get("gto_capacity"),
            })
        except (KeyError, TypeError):
            continue

    return launchers


# ---------------------------------------------------------------------------
# Combine pads with rocket associations
# ---------------------------------------------------------------------------

def combine_data(pads, launchers):
    """
    Build simplified pad objects with associated rocket specs.

    Uses a curated PAD_ROCKET_MAP for prototype accuracy, then supplements
    with any API-fetched launcher data. Falls back gracefully when no mapping
    exists for a pad.
    """
    # Build a quick lookup from launcher name → API data
    launcher_lookup = {l["name"]: l for l in launchers}

    result = []
    for pad in pads:
        pad_name = pad["name"]
        country = pad["location"].get("country_code", "")

        # Find the best matching key in PAD_ROCKET_MAP
        rocket_names = []
        for map_key, rockets in PAD_ROCKET_MAP.items():
            if map_key.lower() in pad_name.lower() or pad_name.lower() in map_key.lower():
                rocket_names = rockets
                break

        # Build rocket objects, merging spec table with any API-sourced data
        rocket_objects = []
        for rname in rocket_names:
            specs = ROCKET_SPECS.get(rname, {})
            api_data = launcher_lookup.get(rname, {})

            # Prefer curated specs; fall back to API values
            leo = specs.get("leo_capacity") or api_data.get("leo_capacity")
            cost = specs.get("cost")

            rocket_objects.append({
                "name": rname,
                "leo_capacity": leo,
                "cost": cost,
            })

        result.append({
            "name": pad_name,
            "latitude": pad.get("latitude"),
            "longitude": pad.get("longitude"),
            "country": country,
            "rockets": rocket_objects,
        })

    return result


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def get_launchpad_data():
    """
    Return a list of launchpad objects with associated rocket data.
    Serves from cache when available; otherwise fetches from the API.

    Each launchpad object contains:
        name, latitude, longitude, country,
        rockets: [{name, leo_capacity, cost}, ...]
    """
    cached = load_cache()
    if cached is not None:
        return cached

    pads = fetch_launchpads()
    launchers = fetch_launch_vehicles()
    combined = combine_data(pads, launchers)
    save_cache(combined)
    return combined


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Fetching launchpad data...")
    launchpads = get_launchpad_data()

    print(f"\nTotal launchpads: {len(launchpads)}\n")
    print("=" * 70)

    for pad in launchpads:
        lat = f"{float(pad['latitude']):.4f}" if pad.get("latitude") else "N/A"
        lon = f"{float(pad['longitude']):.4f}" if pad.get("longitude") else "N/A"
        print(f"  {pad['name']}")
        print(f"    Location : {pad['country']}  ({lat}, {lon})")

        rockets = pad.get("rockets", [])
        if rockets:
            print(f"    Rockets  :")
            for r in rockets:
                leo = f"{r['leo_capacity']:,} kg" if r.get("leo_capacity") else "N/A"
                cost = f"${r['cost']:,.0f}" if r.get("cost") else "N/A"
                print(f"      - {r['name']:<18}  LEO: {leo:<12}  Cost/launch: {cost}")
        else:
            print("    Rockets  : (no mapping available)")
        print()
