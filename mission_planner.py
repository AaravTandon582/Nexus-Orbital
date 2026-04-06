"""
mission_planner.py — Asteroid mission trajectory computation and planning.

Uses poliastro for orbital mechanics with pure-math fallbacks when unavailable.
"""

import math
import random
import numpy as np
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Optional poliastro / astropy imports with graceful fallback
# ---------------------------------------------------------------------------
POLIASTRO_AVAILABLE = False
try:
    from astropy.time import Time
    from astropy import units as u
    from astropy.coordinates import get_body_barycentric_posvel
    from poliastro.bodies import Sun, Earth
    try:
        from poliastro.twobody.orbit import Orbit
    except ImportError:
        from poliastro.twobody import Orbit
    from poliastro.iod import izzo as _izzo
    POLIASTRO_AVAILABLE = True
    print("[mission_planner] poliastro + astropy loaded OK")
except ImportError as e:
    print(f"[mission_planner] poliastro/astropy unavailable: {e} — using fallback math")

from asteroid_data import get_asteroid_data
from launchpad_data import get_launchpad_data

# Physical constants
GM_SUN_KM3_S2 = 1.32712440018e11   # km³/s²
AU_TO_KM = 1.495978707e8            # km per AU
DEG_TO_RAD = math.pi / 180.0
SCALE_DIVISOR = 100.0               # divide km positions by this for Cesium visualization


# ---------------------------------------------------------------------------
# Kepler's equation solver: mean anomaly → true anomaly
# ---------------------------------------------------------------------------

def _mean_to_true_anomaly(M_deg: float, ecc: float) -> float:
    """Convert mean anomaly (°) to true anomaly (°) via iterative Kepler solver."""
    M = M_deg * DEG_TO_RAD
    # Newton's method for eccentric anomaly E: E - e·sin(E) = M
    E = M
    for _ in range(150):
        dE = (M - E + ecc * math.sin(E)) / (1 - ecc * math.cos(E))
        E += dE
        if abs(dE) < 1e-12:
            break
    nu = 2.0 * math.atan2(
        math.sqrt(1.0 + ecc) * math.sin(E / 2.0),
        math.sqrt(1.0 - ecc) * math.cos(E / 2.0),
    )
    return math.degrees(nu)


# ---------------------------------------------------------------------------
# Pure-math heliocentric position from Keplerian elements
# ---------------------------------------------------------------------------

def _elements_to_heliocentric_km(a_au, ecc, inc_deg, raan_deg, argp_deg, M_deg,
                                   epoch_jd=None):
    """
    Convert classical orbital elements to heliocentric ecliptic position (km).
    Propagates mean anomaly forward from epoch to current UTC if epoch is given.
    """
    # Propagate mean anomaly from epoch to now
    if epoch_jd is not None:
        try:
            j2000 = datetime(2000, 1, 1, 12, 0, 0)
            dt_days = (datetime.utcnow() - j2000).total_seconds() / 86400.0
            jd_now = 2451545.0 + dt_days

            delta_days = jd_now - float(epoch_jd)
            a_km = a_au * AU_TO_KM
            n_rad_per_s = math.sqrt(GM_SUN_KM3_S2 / (a_km ** 3))
            n_rad_per_day = n_rad_per_s * 86400.0
            M_now = (M_deg * DEG_TO_RAD + n_rad_per_day * delta_days) % (2 * math.pi)
            M_deg = math.degrees(M_now)
        except Exception:
            pass  # fall through with original M_deg

    nu_deg = _mean_to_true_anomaly(M_deg, ecc)
    nu = nu_deg * DEG_TO_RAD
    inc = inc_deg * DEG_TO_RAD
    raan = raan_deg * DEG_TO_RAD
    argp = argp_deg * DEG_TO_RAD

    a_km = a_au * AU_TO_KM
    r = a_km * (1.0 - ecc ** 2) / (1.0 + ecc * math.cos(nu))

    # Perifocal coordinates
    xp = r * math.cos(nu)
    yp = r * math.sin(nu)

    # Rotation matrices: R3(-Ω) · R1(-i) · R3(-ω)
    cr, sr = math.cos(raan), math.sin(raan)
    ci, si = math.cos(inc), math.sin(inc)
    ca, sa = math.cos(argp), math.sin(argp)

    x = (cr * ca - sr * sa * ci) * xp + (-cr * sa - sr * ca * ci) * yp
    y = (sr * ca + cr * sa * ci) * xp + (-sr * sa + cr * ca * ci) * yp
    z = (sa * si) * xp + (ca * si) * yp

    return (x, y, z)


# ---------------------------------------------------------------------------
# Earth's heliocentric position at a given date/JD
# ---------------------------------------------------------------------------

def _earth_heliocentric_km(when=None):
    """
    Approximate Earth heliocentric position (km) using a simple circular orbit.
    'when' is a datetime; defaults to now.
    """
    if when is None:
        when = datetime.utcnow()
    j2000 = datetime(2000, 1, 1, 12, 0, 0)
    T = (when - j2000).total_seconds() / 86400.0
    L_deg = (100.466457 + 360.0 / 365.25636 * T) % 360.0
    L_rad = L_deg * DEG_TO_RAD
    r = AU_TO_KM
    return (r * math.cos(L_rad), r * math.sin(L_rad), 0.0)


def _earth_heliocentric_km_at_date(date_obj):
    """Return Earth heliocentric position for a date object (not datetime)."""
    dt = datetime(date_obj.year, date_obj.month, date_obj.day, 12, 0, 0)
    return _earth_heliocentric_km(dt)


# ---------------------------------------------------------------------------
# Earth velocity (approximate, km/s)
# ---------------------------------------------------------------------------

def _earth_velocity_km_s(when=None):
    """Approximate Earth heliocentric velocity (km/s) — perpendicular to radius."""
    if when is None:
        when = datetime.utcnow()
    pos = _earth_heliocentric_km(when)
    # Speed ≈ 29.78 km/s; direction is perpendicular to radius in ecliptic plane
    r = math.sqrt(pos[0]**2 + pos[1]**2)
    speed = math.sqrt(GM_SUN_KM3_S2 / r)
    # Velocity is 90° ahead in prograde direction
    return (-speed * pos[1] / r, speed * pos[0] / r, 0.0)


# ---------------------------------------------------------------------------
# Task 3.2 helper: compute geocentric positions for all enriched asteroids
# ---------------------------------------------------------------------------

def compute_asteroid_positions():
    """
    Compute current geocentric positions (km, divided by SCALE_DIVISOR) for every
    asteroid that has orbital elements in the data store.

    Returns list of dicts: id, name, x, y, z, is_hazardous, estimated_value,
                           miss_distance_au, position_approximate (bool).
    """
    asteroids = get_asteroid_data()
    results = []

    for asteroid in asteroids:
        if not asteroid.get("semi_major_axis_au"):
            continue  # no orbital elements — skip

        name = asteroid.get("name", "Unknown")

        try:
            a_au = float(asteroid["semi_major_axis_au"])
            ecc = float(asteroid.get("eccentricity") or 0)
            inc_deg = float(asteroid.get("inclination_deg") or 0)
            raan_deg = float(asteroid.get("longitude_ascending_node_deg") or 0)
            argp_deg = float(asteroid.get("argument_of_perihelion_deg") or 0)
            M_deg = float(asteroid.get("mean_anomaly_deg") or 0)
            epoch_jd = asteroid.get("epoch")

            if a_au <= 0 or ecc >= 1.0:
                continue

            pos_km = None  # geocentric position in km

            # Attempt poliastro-based calculation first
            if POLIASTRO_AVAILABLE:
                try:
                    nu_deg = _mean_to_true_anomaly(M_deg, ecc)
                    if epoch_jd:
                        epoch_time = Time(float(epoch_jd), format="jd")
                    else:
                        epoch_time = Time("2024-01-01", format="iso")

                    orb = Orbit.from_classical(
                        Sun,
                        a=a_au * u.AU,
                        ecc=ecc * u.one,
                        inc=inc_deg * u.deg,
                        raan=raan_deg * u.deg,
                        argp=argp_deg * u.deg,
                        nu=nu_deg * u.deg,
                        epoch=epoch_time,
                    )
                    t_now = Time.now()
                    tof = (t_now - epoch_time).to(u.s)
                    orb_now = orb.propagate(tof)
                    r_heli = orb_now.r.to(u.km).value  # [x, y, z] in km

                    earth_pv = get_body_barycentric_posvel("earth", t_now)
                    e_heli = earth_pv[0].get_xyz().to(u.km).value

                    pos_km = (r_heli[0] - e_heli[0],
                              r_heli[1] - e_heli[1],
                              r_heli[2] - e_heli[2])
                except Exception as e:
                    print(f"[mission_planner] poliastro position failed for {name}: {e}")

            # Fallback: pure Kepler
            if pos_km is None:
                a_heli = _elements_to_heliocentric_km(
                    a_au, ecc, inc_deg, raan_deg, argp_deg, M_deg, epoch_jd
                )
                e_heli = _earth_heliocentric_km()
                pos_km = (a_heli[0] - e_heli[0],
                          a_heli[1] - e_heli[1],
                          a_heli[2] - e_heli[2])

            x = pos_km[0] / SCALE_DIVISOR
            y = pos_km[1] / SCALE_DIVISOR
            z = pos_km[2] / SCALE_DIVISOR
            estimated_value = float(asteroid.get("price") or asteroid.get("profit") or 0)

            results.append({
                "id": asteroid.get("id"),
                "name": name,
                "x": round(x, 2),
                "y": round(y, 2),
                "z": round(z, 2),
                "is_hazardous": bool(asteroid.get("is_potentially_hazardous_asteroid")),
                "estimated_value": estimated_value,
                "miss_distance_au": asteroid.get("miss_distance_au"),
                "position_approximate": False,
            })

        except Exception as e:
            print(f"[mission_planner] Position failed for {name}: {e}")
            # Last-resort: place at miss_distance in a random direction
            try:
                miss_km = float(asteroid.get("miss_distance_km") or 7.5e6)
                theta = random.uniform(0, 2 * math.pi)
                phi = random.uniform(-math.pi / 6, math.pi / 6)
                results.append({
                    "id": asteroid.get("id"),
                    "name": name,
                    "x": round(miss_km * math.cos(phi) * math.cos(theta) / SCALE_DIVISOR, 2),
                    "y": round(miss_km * math.cos(phi) * math.sin(theta) / SCALE_DIVISOR, 2),
                    "z": round(miss_km * math.sin(phi) / SCALE_DIVISOR, 2),
                    "is_hazardous": bool(asteroid.get("is_potentially_hazardous_asteroid")),
                    "estimated_value": float(asteroid.get("price") or 0),
                    "miss_distance_au": asteroid.get("miss_distance_au"),
                    "position_approximate": True,
                })
            except Exception:
                pass

    return results


# ---------------------------------------------------------------------------
# Trajectory arc generation (pure math fallback)
# ---------------------------------------------------------------------------

def _arc_trajectory_points(asteroid, departure_date, arrival_date):
    """
    Generate a visually plausible transfer arc between Earth and the asteroid.
    Returns list of {x, y, z} dicts in scaled geocentric km.
    """
    try:
        a_au = float(asteroid.get("semi_major_axis_au") or 1.5)
        ecc = float(asteroid.get("eccentricity") or 0.3)
        inc_deg = float(asteroid.get("inclination_deg") or 0)
        raan_deg = float(asteroid.get("longitude_ascending_node_deg") or 0)
        argp_deg = float(asteroid.get("argument_of_perihelion_deg") or 0)
        M_dep = float(asteroid.get("mean_anomaly_deg") or 0)

        # Earth at departure
        dep_dt = datetime(departure_date.year, departure_date.month, departure_date.day, 12)
        arr_dt = datetime(arrival_date.year, arrival_date.month, arrival_date.day, 12)
        e_dep = _earth_heliocentric_km(dep_dt)
        e_arr = _earth_heliocentric_km(arr_dt)

        # Asteroid at arrival (propagate M forward)
        j2000 = datetime(2000, 1, 1, 12, 0, 0)
        epoch_jd = asteroid.get("epoch")
        if epoch_jd:
            jd_dep = 2451545.0 + (dep_dt - j2000).total_seconds() / 86400
            delta_days = jd_dep - float(epoch_jd)
            a_km = a_au * AU_TO_KM
            n_rad_per_day = math.sqrt(GM_SUN_KM3_S2 / a_km**3) * 86400
            M_dep_rad = (M_dep * DEG_TO_RAD + n_rad_per_day * delta_days) % (2 * math.pi)
            M_dep = math.degrees(M_dep_rad)

        # Propagate asteroid to arrival
        tof_days = (arr_dt - dep_dt).total_seconds() / 86400
        a_km_val = a_au * AU_TO_KM
        n_rad_per_day_ast = math.sqrt(GM_SUN_KM3_S2 / a_km_val**3) * 86400
        M_arr_rad = (M_dep * DEG_TO_RAD + n_rad_per_day_ast * tof_days) % (2 * math.pi)
        M_arr = math.degrees(M_arr_rad)

        a_pos_heli = _elements_to_heliocentric_km(a_au, ecc, inc_deg, raan_deg, argp_deg, M_arr)

        # Geocentric start/end
        start = (0.0, 0.0, 0.0)   # Earth at departure (geocentric origin)
        end_x = (a_pos_heli[0] - e_dep[0]) / SCALE_DIVISOR
        end_y = (a_pos_heli[1] - e_dep[1]) / SCALE_DIVISOR
        end_z = (a_pos_heli[2] - e_dep[2]) / SCALE_DIVISOR
        end = (end_x, end_y, end_z)

        # Arc length for out-of-plane deviation
        arc_height = math.sqrt(end_x**2 + end_y**2 + end_z**2) * 0.25

        N = 25
        points = []
        for i in range(N + 1):
            t = i / N
            h = 4 * t * (1 - t)   # 0 at endpoints, 1 at midpoint

            x = start[0] + t * end[0]
            y = start[1] + t * end[1] + h * arc_height * 0.5
            z = start[2] + t * end[2] + h * arc_height * math.sin(inc_deg * DEG_TO_RAD)

            points.append({"x": round(x, 2), "y": round(y, 2), "z": round(z, 2)})

        return points
    except Exception as e:
        print(f"[mission_planner] Arc trajectory generation failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Task 4.1: compute_transfer
# ---------------------------------------------------------------------------

def compute_transfer(asteroid, departure_date, arrival_date):
    """
    Calculate delta-v for Earth → asteroid transfer via Lambert's problem.

    Parameters
    ----------
    asteroid : dict  — asteroid record (must have orbital elements)
    departure_date : date
    arrival_date   : date

    Returns dict with departure_dv, arrival_dv, total_dv (km/s),
    trajectory_points (list of scaled geocentric {x,y,z}), or None on failure.
    """
    try:
        tof_days = (arrival_date - departure_date).days
        if tof_days <= 0:
            return None

        a_au = float(asteroid.get("semi_major_axis_au") or 0)
        ecc = float(asteroid.get("eccentricity") or 0)
        if a_au <= 0 or ecc >= 1.0:
            return None

        if POLIASTRO_AVAILABLE:
            result = _transfer_poliastro(asteroid, departure_date, arrival_date)
            if result is not None:
                return result

        # Fallback: Hohmann-like vis-viva approximation
        return _transfer_fallback(asteroid, departure_date, arrival_date)

    except Exception as e:
        print(f"[mission_planner] compute_transfer error: {e}")
        return _transfer_fallback(asteroid, departure_date, arrival_date)


def _transfer_poliastro(asteroid, departure_date, arrival_date):
    """
    Poliastro-based Lambert solver implementation.
    """
    try:
        dep_dt = datetime(departure_date.year, departure_date.month, departure_date.day, 12)
        arr_dt = datetime(arrival_date.year, arrival_date.month, arrival_date.day, 12)

        dep_time = Time(dep_dt.isoformat(), format="isot", scale="utc")
        arr_time = Time(arr_dt.isoformat(), format="isot", scale="utc")
        tof = (arr_time - dep_time).to(u.s)

        # Earth state at departure
        earth_dep_pv = get_body_barycentric_posvel("earth", dep_time)
        r_earth = earth_dep_pv[0].get_xyz().to(u.km)
        v_earth = earth_dep_pv[1].get_xyz().to(u.km / u.s)

        # Asteroid orbit at arrival
        a_au = float(asteroid["semi_major_axis_au"])
        ecc = float(asteroid.get("eccentricity") or 0)
        inc_deg = float(asteroid.get("inclination_deg") or 0)
        raan_deg = float(asteroid.get("longitude_ascending_node_deg") or 0)
        argp_deg = float(asteroid.get("argument_of_perihelion_deg") or 0)
        M_deg = float(asteroid.get("mean_anomaly_deg") or 0)
        epoch_jd = asteroid.get("epoch")

        nu_deg = _mean_to_true_anomaly(M_deg, ecc)
        if epoch_jd:
            epoch_time = Time(float(epoch_jd), format="jd")
        else:
            epoch_time = Time("2024-01-01", format="iso")

        orb_epoch = Orbit.from_classical(
            Sun,
            a=a_au * u.AU,
            ecc=ecc * u.one,
            inc=inc_deg * u.deg,
            raan=raan_deg * u.deg,
            argp=argp_deg * u.deg,
            nu=nu_deg * u.deg,
            epoch=epoch_time,
        )

        # Propagate to arrival
        tof_arr = (arr_time - epoch_time).to(u.s)
        orb_arr = orb_epoch.propagate(tof_arr)
        r_asteroid = orb_arr.r  # km
        v_asteroid = orb_arr.v  # km/s

        # Lambert solver (izzo.lambert is a generator that yields (v0, v) solutions)
        k = Sun.k.to(u.km ** 3 / u.s ** 2)
        lambert_solutions = list(_izzo.lambert(k, r_earth, r_asteroid, tof))
        if not lambert_solutions:
            raise ValueError("Lambert solver returned no solutions")
        v0_l, v1_l = lambert_solutions[0]  # use first (prograde) solution

        dv_dep = float(np.linalg.norm((v0_l - v_earth).value))
        dv_arr = float(np.linalg.norm((v_asteroid - v1_l).value))
        total_dv = dv_dep + dv_arr

        # Trajectory points — use fast arc approximation (avoids slow propagate loop)
        traj_pts = _arc_trajectory_points(asteroid, departure_date, arrival_date)

        return {
            "departure_dv": round(dv_dep, 3),
            "arrival_dv": round(dv_arr, 3),
            "total_dv": round(total_dv, 3),
            "trajectory_points": traj_pts,
        }

    except Exception as e:
        print(f"[mission_planner] poliastro Lambert failed: {e}")
        return None


def _transfer_fallback(asteroid, departure_date, arrival_date):
    """
    Vis-viva Hohmann-like delta-v approximation when poliastro is unavailable.
    """
    try:
        a_au = float(asteroid.get("semi_major_axis_au") or 1.5)
        ecc = float(asteroid.get("eccentricity") or 0.3)

        r1 = AU_TO_KM           # Earth orbit radius
        # Target: asteroid perihelion or semi-latus rectum as approximation
        r2_min = a_au * AU_TO_KM * (1 - ecc)
        r2_max = a_au * AU_TO_KM * (1 + ecc)
        r2 = (r2_min + r2_max) / 2   # average radius as transfer target

        if r2 <= 0 or r2 == r1:
            r2 = a_au * AU_TO_KM

        a_t = (r1 + r2) / 2  # semi-major axis of transfer ellipse

        v_earth = math.sqrt(GM_SUN_KM3_S2 / r1)
        v_t_dep = math.sqrt(GM_SUN_KM3_S2 * (2.0 / r1 - 1.0 / a_t))
        v_t_arr = math.sqrt(GM_SUN_KM3_S2 * (2.0 / r2 - 1.0 / a_t))
        v_asteroid = math.sqrt(GM_SUN_KM3_S2 * (2.0 / r2 - 1.0 / (a_au * AU_TO_KM)))

        dv_dep = abs(v_t_dep - v_earth)
        dv_arr = abs(v_t_arr - v_asteroid)

        # Add inclination penalty
        inc_deg = float(asteroid.get("inclination_deg") or 0)
        inc_penalty = 0.5 * v_earth * math.sin(inc_deg * DEG_TO_RAD)
        total_dv = dv_dep + dv_arr + inc_penalty

        traj_pts = _arc_trajectory_points(asteroid, departure_date, arrival_date)

        return {
            "departure_dv": round(dv_dep, 3),
            "arrival_dv": round(dv_arr, 3),
            "total_dv": round(total_dv, 3),
            "trajectory_points": traj_pts,
        }
    except Exception as e:
        print(f"[mission_planner] Fallback transfer failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Task 4.1: scan_launch_windows
# ---------------------------------------------------------------------------

def scan_launch_windows(asteroid, departure_window_start, departure_window_end,
                        min_time_of_flight_days=60, max_time_of_flight_days=365):
    """
    Find the best launch opportunity by evaluating a grid of departure dates
    and times-of-flight. Returns the combination with minimum total delta-v.

    Returns dict with best_departure_date, best_arrival_date,
    best_time_of_flight_days, minimum_delta_v, transfer_result — or None.
    """
    best = None
    best_dv = float("inf")

    # Grid resolution — coarse scan with vis-viva (fast), then one poliastro call for winner
    # Caps: max 60 departure samples × 6 TOF samples = 360 fast calls (~1-2 s total)
    dep_step = max(5, (departure_window_end - departure_window_start).days // 12)
    tof_step = max(30, (max_time_of_flight_days - min_time_of_flight_days) // 6)

    dep_days_total = max(0, (departure_window_end - departure_window_start).days)
    tof_days_range = max(0, max_time_of_flight_days - min_time_of_flight_days)

    dep_count = dep_days_total // dep_step + 1
    tof_count = tof_days_range // tof_step + 1

    print(f"[mission_planner] Scanning {dep_count}×{tof_count} grid "
          f"(dep_step={dep_step}d, tof_step={tof_step}d) for {asteroid.get('name')}...")

    for i in range(dep_count):
        dep_date = departure_window_start + timedelta(days=i * dep_step)
        if dep_date > departure_window_end:
            break

        for j in range(tof_count):
            tof = min_time_of_flight_days + j * tof_step
            if tof > max_time_of_flight_days:
                break

            arr_date = dep_date + timedelta(days=tof)

            # Use fast vis-viva for the coarse scan — no poliastro propagation
            result = _transfer_fallback(asteroid, dep_date, arr_date)
            if result is None:
                continue

            dv = result["total_dv"]
            if dv < best_dv:
                best_dv = dv
                best = {
                    "best_departure_date": dep_date,
                    "best_arrival_date": arr_date,
                    "best_time_of_flight_days": tof,
                    "minimum_delta_v": dv,
                    "transfer_result": result,   # placeholder; refined below
                }

    if best is None:
        return None

    # Refine the winner with poliastro Lambert (one call only, not 100+)
    best_dep = best["best_departure_date"]
    best_arr = best["best_arrival_date"]
    refined = None
    if POLIASTRO_AVAILABLE:
        try:
            refined = _transfer_poliastro(asteroid, best_dep, best_arr)
        except Exception as e:
            print(f"[mission_planner] Lambert refinement failed: {e}")

    if refined is not None:
        best["minimum_delta_v"] = refined["total_dv"]
        best["transfer_result"] = refined
    # else: keep the vis-viva result already stored

    return best


# ---------------------------------------------------------------------------
# Task 4.1: estimate_mission_cost
# ---------------------------------------------------------------------------

def estimate_mission_cost(delta_v_km_s, flight_time_days, rocket_launch_cost_usd,
                          spacecraft_mass_kg=1000):
    """
    Simplified mission cost model (USD):
      - Spacecraft: $50k/kg
      - Operations: $1M/month of flight time
      - Launch: rocket cost
    """
    spacecraft_cost = spacecraft_mass_kg * 50_000
    operations_cost = (flight_time_days / 30.0) * 1_000_000
    total = rocket_launch_cost_usd + spacecraft_cost + operations_cost
    return round(total)


# ---------------------------------------------------------------------------
# Task 4.1: match_rockets_to_mission
# ---------------------------------------------------------------------------

# Hardcoded rocket specs as a reliable fallback when launchpad DB is sparse
_BUILTIN_ROCKETS = [
    {"rocket_name": "Falcon 9",    "launchpad_name": "Launch Complex 39A, Kennedy Space Center",    "country": "USA", "rocket_cost": 67_000_000,     "leo_capacity": 22800, "latitude": 28.6080, "longitude": -80.6040},
    {"rocket_name": "Falcon Heavy","launchpad_name": "Launch Complex 39A, Kennedy Space Center",    "country": "USA", "rocket_cost": 150_000_000,    "leo_capacity": 63800, "latitude": 28.6080, "longitude": -80.6040},
    {"rocket_name": "SLS",         "launchpad_name": "Launch Complex 39B, Kennedy Space Center",    "country": "USA", "rocket_cost": 2_000_000_000,  "leo_capacity": 95000, "latitude": 28.6271, "longitude": -80.6208},
    {"rocket_name": "Ariane 5",    "launchpad_name": "Ariane Launch Area 3, Kourou",               "country": "GUF", "rocket_cost": 180_000_000,    "leo_capacity": 20000, "latitude": 5.2390,  "longitude": -52.7690},
    {"rocket_name": "Ariane 6",    "launchpad_name": "Ariane Launch Area 4, Kourou",               "country": "GUF", "rocket_cost": 115_000_000,    "leo_capacity": 21650, "latitude": 5.2392,  "longitude": -52.7752},
    {"rocket_name": "Proton",      "launchpad_name": "Site 81/23, Baikonur Cosmodrome",            "country": "KAZ", "rocket_cost": 65_000_000,     "leo_capacity": 23000, "latitude": 46.0750, "longitude": 63.0440},
    {"rocket_name": "Soyuz",       "launchpad_name": "Site 1/5, Baikonur Cosmodrome",              "country": "KAZ", "rocket_cost": 50_000_000,     "leo_capacity": 7020,  "latitude": 45.9200, "longitude": 63.3420},
    {"rocket_name": "H-IIA",       "launchpad_name": "Yoshinobu Launch Complex, Tanegashima",      "country": "JPN", "rocket_cost": 90_000_000,     "leo_capacity": 15000, "latitude": 30.4000, "longitude": 130.9700},
    {"rocket_name": "PSLV",        "launchpad_name": "Satish Dhawan Space Centre, Sriharikota",    "country": "IND", "rocket_cost": 30_000_000,     "leo_capacity": 3800,  "latitude": 13.7330, "longitude": 80.2350},
]


def match_rockets_to_mission(required_delta_v_km_s, all_launchpads_data):
    """
    Return list of rocket/launchpad combinations capable of achieving the
    given delta-v budget, based on a simple capability-tier model.

    Searches launchpad DB first; falls back to built-in curated list so
    results are always returned even when the DB cache is sparse.
    """
    if required_delta_v_km_s < 4.0:
        capable = {
            "Falcon 9", "Falcon Heavy", "SLS", "Soyuz", "Proton",
            "Ariane 5", "Ariane 6", "PSLV", "GSLV", "H-IIA", "H-IIB",
        }
    elif required_delta_v_km_s < 7.0:
        capable = {
            "Falcon 9", "Falcon Heavy", "SLS", "Proton",
            "Ariane 5", "Ariane 6", "H-IIA",
        }
    else:
        capable = {"Falcon Heavy", "SLS"}

    viable = []
    seen = set()

    # Primary: launchpad database
    for pad in all_launchpads_data:
        for rocket in pad.get("rockets", []):
            rname = rocket.get("name", "")
            if rname in capable and rname not in seen:
                seen.add(rname)
                viable.append({
                    "rocket_name": rname,
                    "launchpad_name": pad.get("name", "Unknown"),
                    "country": pad.get("country", ""),
                    "rocket_cost": rocket.get("cost") or 100_000_000,
                    "leo_capacity": rocket.get("leo_capacity"),
                    "latitude": pad.get("latitude"),
                    "longitude": pad.get("longitude"),
                })

    # Fallback: built-in curated list fills any gaps
    for entry in _BUILTIN_ROCKETS:
        rname = entry["rocket_name"]
        if rname in capable and rname not in seen:
            seen.add(rname)
            viable.append(dict(entry))

    return viable


# ---------------------------------------------------------------------------
# Task 4.1: plan_mission (main function)
# ---------------------------------------------------------------------------

def plan_mission(asteroid_id, departure_window_start, departure_window_end,
                 max_time_of_flight_days=365):
    """
    Full mission plan: trajectory search + rocket matching + ROI analysis.

    Returns list of up to 5 ranked mission options (sorted by profit desc),
    or a dict with an "error" key on failure.
    """
    # Locate asteroid
    all_asteroids = get_asteroid_data()
    asteroid = next(
        (a for a in all_asteroids if str(a.get("id")) == str(asteroid_id)),
        None
    )

    if asteroid is None:
        return {"error": f"Asteroid ID {asteroid_id} not found in current dataset."}

    if not asteroid.get("semi_major_axis_au"):
        return {
            "error": (
                f"No orbital elements available for '{asteroid.get('name')}'. "
                "Only enriched asteroids (top 20 by proximity) support mission planning."
            )
        }

    # Validate dates
    if departure_window_end <= departure_window_start:
        return {"error": "Departure window end must be after start."}

    # Find optimal window
    print(f"[mission_planner] Starting mission plan for {asteroid.get('name')} ...")
    window = scan_launch_windows(
        asteroid,
        departure_window_start,
        departure_window_end,
        min_time_of_flight_days=60,
        max_time_of_flight_days=max_time_of_flight_days,
    )

    if window is None:
        return {
            "error": (
                "No valid transfer orbit found. Try widening the date range "
                "or increasing maximum flight time."
            )
        }

    best_dep = window["best_departure_date"]
    best_arr = window["best_arrival_date"]
    best_tof = window["best_time_of_flight_days"]
    best_dv = window["minimum_delta_v"]
    traj_pts = window["transfer_result"].get("trajectory_points", [])

    # Launchpads
    launchpads = get_launchpad_data()
    rockets = match_rockets_to_mission(best_dv, launchpads)

    if not rockets:
        return {"error": f"No rocket capable of Δv = {best_dv:.1f} km/s found in database."}

    # Asteroid value
    asteroid_value = float(asteroid.get("price") or asteroid.get("profit") or 0)
    if asteroid_value <= 0:
        # Rough estimate based on diameter
        d = float(asteroid.get("diameter_km") or 0.1)
        asteroid_value = max(1e9, d ** 3 * 1e10)

    # Build one result per rocket option
    results = []
    for opt in rockets:
        try:
            cost = estimate_mission_cost(best_dv, best_tof, opt["rocket_cost"])
            profit = asteroid_value - cost
            roi = (profit / cost * 100.0) if cost > 0 else 0.0

            results.append({
                "launch_site_name": opt["launchpad_name"],
                "rocket_name": opt["rocket_name"],
                "country": opt["country"],
                "departure_date": best_dep.strftime("%Y-%m-%d"),
                "arrival_date": best_arr.strftime("%Y-%m-%d"),
                "flight_time_days": best_tof,
                "delta_v_total": round(best_dv, 3),
                "mission_cost_usd": cost,
                "asteroid_value_usd": round(asteroid_value),
                "potential_profit_usd": round(profit),
                "roi_percentage": round(roi, 1),
                "trajectory_points": traj_pts,
                "launch_lat": opt.get("latitude"),
                "launch_lon": opt.get("longitude"),
            })
        except Exception as e:
            print(f"[mission_planner] Result build error for {opt['rocket_name']}: {e}")

    results.sort(key=lambda r: r["potential_profit_usd"], reverse=True)
    top5 = results[:5]
    for i, r in enumerate(top5):
        r["rank"] = i + 1

    print(f"[mission_planner] Done — {len(top5)} options returned.")
    return top5
