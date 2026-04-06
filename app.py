import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from dotenv import load_dotenv

_PLAN_EXECUTOR = ThreadPoolExecutor(max_workers=2)
PLAN_TIMEOUT_SECONDS = 90   # hard ceiling for mission planning

from asteroid_data import get_asteroid_data, filter_asteroids
from launchpad_data import get_launchpad_data

load_dotenv()

CESIUM_TOKEN = os.getenv("CESIUM_ION_TOKEN")

app = Flask(__name__)
CORS(app)


# ---------------------------------------------------------------------------
# Homepage
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", cesium_token=CESIUM_TOKEN)


# ---------------------------------------------------------------------------
# Asteroids API
# ---------------------------------------------------------------------------

@app.route("/api/asteroids")
def asteroids():
    try:
        raw_distance = request.args.get("max_distance", "0.05")
        raw_value = request.args.get("min_value", None)

        try:
            max_distance = float(raw_distance)
        except (ValueError, TypeError):
            return jsonify({"error": "max_distance must be a number"}), 400

        min_value = None
        if raw_value is not None:
            try:
                min_value = float(raw_value)
            except (ValueError, TypeError):
                return jsonify({"error": "min_value must be a number"}), 400

        all_asteroids = get_asteroid_data()
        filtered = filter_asteroids(
            all_asteroids,
            max_distance_au=max_distance,
            min_value=min_value,
        )
        return jsonify(filtered)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Launchpads API
# ---------------------------------------------------------------------------

@app.route("/api/launchpads")
def launchpads():
    try:
        data = get_launchpad_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Asteroid positions API (3D globe coordinates)
# ---------------------------------------------------------------------------

@app.route("/api/asteroid-positions")
def asteroid_positions():
    """
    Returns geocentric positions for asteroids that have orbital elements.
    Coordinates are in km / 100 (scaled for Cesium visualization).
    Cesium should multiply by 1000 to convert to metres.
    """
    try:
        # Import here to avoid slow startup — only loaded when route is called
        from mission_planner import compute_asteroid_positions
        positions = compute_asteroid_positions()
        return jsonify(positions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Mission planner API
# ---------------------------------------------------------------------------

@app.route("/api/plan-mission", methods=["POST"])
def plan_mission_route():
    """
    POST body (JSON):
      asteroid_id             : str
      departure_window_start  : str  (YYYY-MM-DD)
      departure_window_end    : str  (YYYY-MM-DD)
      max_time_of_flight_days : int  (optional, default 365)

    Returns ranked list of mission options or {"error": "..."}.
    """
    try:
        body = request.get_json(silent=True) or {}

        asteroid_id = body.get("asteroid_id")
        dep_start_str = body.get("departure_window_start")
        dep_end_str = body.get("departure_window_end")
        max_tof = int(body.get("max_time_of_flight_days", 365))

        # Validate required fields
        if not asteroid_id:
            return jsonify({"error": "asteroid_id is required"}), 400
        if not dep_start_str or not dep_end_str:
            return jsonify({"error": "departure_window_start and departure_window_end are required"}), 400

        # Parse dates
        try:
            dep_start = datetime.strptime(dep_start_str, "%Y-%m-%d").date()
            dep_end = datetime.strptime(dep_end_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Dates must be in YYYY-MM-DD format"}), 400

        if dep_end <= dep_start:
            return jsonify({"error": "departure_window_end must be after departure_window_start"}), 400

        from mission_planner import plan_mission

        future = _PLAN_EXECUTOR.submit(plan_mission, asteroid_id, dep_start, dep_end, max_tof)
        try:
            result = future.result(timeout=PLAN_TIMEOUT_SECONDS)
        except FuturesTimeout:
            future.cancel()
            return jsonify({
                "error": (
                    f"Mission planning timed out after {PLAN_TIMEOUT_SECONDS}s. "
                    "Try a smaller date window or shorter max flight time."
                )
            }), 408

        # plan_mission returns either a list (success) or dict with "error"
        if isinstance(result, dict) and "error" in result:
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
