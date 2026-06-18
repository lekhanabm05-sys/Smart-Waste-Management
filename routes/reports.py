# routes/reports.py
from flask import Blueprint, jsonify
from app import mongo

reports_bp = Blueprint("reports", __name__)

@reports_bp.route("/reports/summary", methods=["GET"])
def summary():
    waste_count = mongo.db.waste.count_documents({})
    bin_count = mongo.db.bins.count_documents({})
    tracked_bins = len(mongo.db.gps.distinct("bin_id"))
    return jsonify({
        "waste_records": waste_count,
        "bins": bin_count,
        "tracked_bins": tracked_bins
    }), 200