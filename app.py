import os
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from dotenv import load_dotenv

from asteroid_data import get_asteroid_data, filter_asteroids
from launchpad_data import get_launchpad_data

load_dotenv()

CESIUM_TOKEN = os.getenv('CESIUM_ION_TOKEN')

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
# Mission planner (placeholder)
# ---------------------------------------------------------------------------

@app.route("/api/plan-mission", methods=["POST"])
def plan_mission():
    return jsonify({
        "status": "coming soon",
        "message": "Mission planner will be implemented on Day 4",
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
