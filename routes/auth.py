from flask import Blueprint, request, jsonify, session
from app import mongo
from flask_bcrypt import Bcrypt
from datetime import datetime

bcrypt = Bcrypt()
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

def log_activity(username, action, details=""):
    """Log user activity to activity_logs collection"""
    mongo.db.activity_logs.insert_one({
        "username": username,
        "action": action,
        "details": details,
        "timestamp": datetime.now(),
        "ip_address": request.remote_addr
    })

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.json
    hashed_pw = bcrypt.generate_password_hash(data["password"]).decode("utf-8")

    mongo.db.users.insert_one({
        "username": data["username"],
        "password": hashed_pw,
        "email": data.get("email"),
        "role": "user",
        "created_at": datetime.now()
    })
    
    # Log registration activity
    log_activity(data["username"], "User Registration", "New user registered")

    return jsonify({"message": "User registered successfully"})
 