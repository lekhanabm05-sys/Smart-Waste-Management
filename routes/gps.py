# routes/gps.py
from flask import Blueprint, request, jsonify
from app import mongo

gps_bp = Blueprint("gps", __name__)

@gps_bp.route("/gps", methods=["POST"])
def gps_update():
    data = request.get_json()
    doc = {
        "bin_id": data.get("bin_id"),
        "lat": float(data.get("lat")),
        "lng": float(data.get("lng")),
    }
    if not doc["bin_id"]:
        return jsonify({"message": "bin_id required"}), 400
    mongo.db.gps.insert_one(doc)
    return jsonify({"message": "GPS updated"}), 201

@gps_bp.route("/gps/<bin_id>", methods=["GET"])
def gps_get(bin_id):
    records = list(mongo.db.gps.find({"bin_id": bin_id}, {"_id": 0}))
    return jsonify(records), 200

@gps_bp.route("/gps/latest", methods=["GET"])
def gps_latest():
    pipeline = [
        {"$sort": {"_id": -1}},
        {"$group": {"_id": "$bin_id", "lat": {"$first": "$lat"}, "lng": {"$first": "$lng"}}}
    ]
    latest = list(mongo.db.gps.aggregate(pipeline))
    return jsonify([{ "bin_id": x["_id"], "lat": x["lat"], "lng": x["lng"] } for x in latest]), 200 