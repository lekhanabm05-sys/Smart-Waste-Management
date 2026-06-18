# models/indexes.py
from app import mongo

def ensure_indexes():
    # Users collection
    mongo.db.users.create_index("email", unique=True)
    
    # Bins collection
    mongo.db.bins.create_index("bin_id", unique=True)
    
    # GPS tracking
    mongo.db.gps.create_index([("bin_id", 1), ("_id", -1)])
    
    # Waste records
    mongo.db.waste_records.create_index([("uploaded_by", 1), ("timestamp", -1)])
    mongo.db.waste_records.create_index("bin")
    
    # Activity logs
    mongo.db.activity_logs.create_index([("username", 1), ("timestamp", -1)])
    mongo.db.activity_logs.create_index("action")
    mongo.db.activity_logs.create_index("timestamp")
    
    # Pickups
    mongo.db.pickups.create_index([("status", 1), ("created_at", -1)])
    mongo.db.pickups.create_index("bin_id")
    mongo.db.pickups.create_index("requested_by")
    
    # Notifications
    mongo.db.notifications.create_index([("recipient", 1), ("timestamp", -1)])
    mongo.db.notifications.create_index([("recipient", 1), ("read", 1)])
    mongo.db.notifications.create_index("type")
    mongo.db.notifications.create_index("timestamp")