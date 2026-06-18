# routes/bins.py
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta

bins_bp = Blueprint("bins", __name__)

@bins_bp.route("/bins", methods=["POST"])
def create_bin():
    from app import mongo
    data = request.get_json()
    bin_id = data.get("bin_id")
    if not bin_id:
        return jsonify({"message": "bin_id required"}), 400
    doc = {
        "bin_id": bin_id,
        "area_name": data.get("area_name") or data.get("location"),
        "lat": data.get("lat"),
        "lng": data.get("lng"),
        "type": data.get("type", "general"),
        "capacity": data.get("capacity", 50),
        "status": data.get("status", "unknown"),
        "qr": data.get("qr", bin_id),  # QR encodes bin_id by default
        "last_updated": datetime.utcnow().isoformat()
    }
    mongo.db.bins.insert_one(doc)
    return jsonify({"message": "Bin created", "bin": doc}), 201

@bins_bp.route("/seed-bins", methods=["GET", "POST"])
def seed_bins():
    """Seed demo bins with GPS coordinates and realistic data"""
    try:
        from flask import session
        from app import mongo
        
        # Check admin access
        if session.get('role') != 'admin':
            return jsonify({"error": "Admin only"}), 403
        
        # Demo bin data with realistic coordinates - using simple names
        demo_bins = [
            {
                "bin_id": "BIN001",
                "area_name": "Downtown Plaza",
                "lat": 28.6139,
                "lng": 77.2090,
                "type": "Mixed",
                "waste_type": "Mixed",
                "capacity": 50,
                "status": "active",
                "last_updated": datetime.utcnow().isoformat()
            },
            {
                "bin_id": "BIN002", 
                "area_name": "Central Park",
                "lat": 28.6126,
                "lng": 77.2000,
                "type": "Wet",
                "waste_type": "Wet",
                "capacity": 50,
                "status": "active",
                "last_updated": datetime.utcnow().isoformat()
            },
            {
                "bin_id": "BIN003",
                "area_name": "Market Square",
                "lat": 28.6200,
                "lng": 77.2200,
                "type": "Dry",
                "waste_type": "Dry",
                "capacity": 50,
                "status": "active",
                "last_updated": datetime.utcnow().isoformat()
            },
            {
                "bin_id": "BIN004",
                "area_name": "Tech Hub",
                "lat": 28.6040,
                "lng": 77.2180,
                "type": "Plastic",
                "waste_type": "Plastic",
                "capacity": 50,
                "status": "active",
                "last_updated": datetime.utcnow().isoformat()
            },
            {
                "bin_id": "BIN005",
                "area_name": "Railway Station",
                "lat": 28.6431,
                "lng": 77.2197,
                "type": "Metal",
                "waste_type": "Metal",
                "capacity": 50,
                "status": "active",
                "last_updated": datetime.utcnow().isoformat()
            },
            {
                "bin_id": "BIN006",
                "area_name": "University Campus",
                "lat": 28.5721,
                "lng": 77.1929,
                "type": "Paper",
                "waste_type": "Paper",
                "capacity": 50,
                "status": "active",
                "last_updated": datetime.utcnow().isoformat()
            },
            {
                "bin_id": "BIN007",
                "area_name": "Beach Promenade",
                "lat": 28.5566,
                "lng": 77.2931,
                "type": "Mixed",
                "waste_type": "Mixed",
                "capacity": 50,
                "status": "active",
                "last_updated": datetime.utcnow().isoformat()
            },
            {
                "bin_id": "BIN008",
                "area_name": "Shopping Mall",
                "lat": 28.5488,
                "lng": 77.2049,
                "type": "Plastic",
                "waste_type": "Plastic",
                "capacity": 50,
                "status": "active",
                "last_updated": datetime.utcnow().isoformat()
            }
        ]
        
        # Upsert bins (update if exists, insert if not)
        for bin_data in demo_bins:
            mongo.db.bins.update_one(
                {"bin_id": bin_data["bin_id"]},
                {"$set": bin_data},
                upsert=True
            )
        
        print(f"DEBUG: Successfully seeded {len(demo_bins)} bins")
        
        return jsonify({
            "message": f"Seeded {len(demo_bins)} bins",
            "count": len(demo_bins)
        }), 200
        
    except Exception as e:
        print(f"ERROR in seed_bins: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to seed bins: {str(e)}"}), 500

@bins_bp.route("/bins", methods=["GET"])
def list_bins():
    """Get all bins with location data"""
    try:
        from app import mongo
        bins = list(mongo.db.bins.find({}, {"_id": 0}))
        print(f"DEBUG: Found {len(bins)} bins in database")
        enriched = []
        for b in bins:
            # If static lat/lng not present, attempt to get latest GPS for that bin
            if not b.get('lat') or not b.get('lng'):
                gps = mongo.db.gps.find_one({'bin_id': b.get('bin_id')}, sort=[('_id', -1)])
                if gps:
                    b['lat'] = gps.get('lat')
                    b['lng'] = gps.get('lng')
            enriched.append(b)
        print(f"DEBUG: Returning {len(enriched)} enriched bins")
        return jsonify(enriched), 200
    except Exception as e:
        print(f"ERROR in /bins GET: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "bins": []}), 200