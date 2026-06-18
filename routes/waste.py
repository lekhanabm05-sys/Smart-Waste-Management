from flask import Blueprint, request, jsonify
from app import mongo
from datetime import datetime

waste_bp = Blueprint("waste", __name__, url_prefix="/waste")

@waste_bp.route("/add", methods=["POST"])
def add_waste():
    mongo.db.waste_logs.insert_one({
        "type": request.form["type"],
        "image": request.form["image"],
        "bin_id": request.form["bin_id"],
        "timestamp": datetime.now()
    })
    return jsonify({"message": "Waste data added"})
