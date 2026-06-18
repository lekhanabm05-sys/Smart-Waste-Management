from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, send_from_directory
from flask_pymongo import PyMongo
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from datetime import datetime, timedelta
import calendar
import os
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId


# PDF/chart dependencies
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import tempfile
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import calendar


# Initialize extensions outside the app factory
mongo = PyMongo()
bcrypt = Bcrypt()
jwt = JWTManager()

def normalize_bin_id(value):
    if not value:
        return None

    value = str(value).strip().upper()

    # Already valid bin_id format (e.g., BIN001)
    if value.startswith("BIN"):
        return value

    # Try mapping using bins collection - only if mongo is available
    try:
        bin_doc = mongo.db.bins.find_one({
            "$or": [
                {"type": value},
                {"location": value},
                {"area_name": value}
            ]
        })

        if bin_doc:
            return bin_doc.get("bin_id")
    except Exception as e:
        print(f"Error in normalize_bin_id: {e}")

    return None

UPLOAD_FOLDER = 'static/uploads'

# ================= ACTIVITY LOGGING =================
def log_activity(username, action, details=""):
    """Log user activity to activity_logs collection"""
    try:
        mongo.db.activity_logs.insert_one({
            "username": username,
            "action": action,
            "details": details,
            "timestamp": datetime.now(),
            "ip_address": request.remote_addr if request else "unknown"
        })
    except Exception as e:
        print(f"Error logging activity: {e}")

# ================= NOTIFICATIONS =================
def create_notification(notification_type, title, message, recipient=None, icon="info", severity="info"):
    """Create a notification in the system"""
    try:
        notification_data = {
            "type": notification_type,  # "bin_full", "pickup_completed", "system_alert"
            "title": title,
            "message": message,
            "recipient": recipient,  # None for system-wide, or specific user
            "icon": icon,
            "severity": severity,  # "info", "warning", "danger", "success"
            "timestamp": datetime.now(),
            "read": False
        }
        print(f"DEBUG: Creating notification: {notification_data}")
        
        result = mongo.db.notifications.insert_one(notification_data)
        print(f"DEBUG: Notification inserted with ID: {result.inserted_id}")
        
    except Exception as e:
        print(f"Error creating notification: {e}")

def get_notifications(recipient=None, unread_only=False, limit=10):
    """Get notifications for a user or system-wide"""
    query = {}
    if recipient:
        # Get user's registration date to filter old notifications
        user = mongo.db.users.find_one({"email": recipient}) or mongo.db.users.find_one({"username": recipient})
        
        if user and 'created_at' in user:
            # Only show notifications created after user registration
            query = {
                "$or": [
                    {"recipient": recipient},
                    {"recipient": None, "timestamp": {"$gte": user['created_at']}}
                ]
            }
        else:
            # Fallback to original behavior if user not found or no created_at
            query = {"$or": [{"recipient": recipient}, {"recipient": None}]}
    
    if unread_only:
        query["read"] = False
    
    return list(mongo.db.notifications.find(query).sort([("timestamp", -1)]).limit(limit))

def get_unread_notification_count(recipient):
    """Get count of unread notifications for a user"""
    user = mongo.db.users.find_one({"email": recipient}) or mongo.db.users.find_one({"username": recipient})
    
    if user and 'created_at' in user:
        # Only count notifications created after user registration
        query = {
            "$or": [
                {"recipient": recipient},
                {"recipient": None, "timestamp": {"$gte": user['created_at']}}
            ],
            "read": False
        }
    else:
        # Fallback to original behavior
        query = {
            "$or": [
                {"recipient": recipient},
                {"recipient": None}
            ],
            "read": False
        }
    
    return mongo.db.notifications.count_documents(query)

# ================= BIN SEGREGATION LOGIC =================
BIN_MAPPING = {
    "Wet Waste": {
        "bin": "Green Bin",
        "color": "success",
        "image": "green_bin.png"
    },
    "Dry Waste": {
        "bin": "Blue Bin",
        "color": "primary",
        "image": "blue_bin.png"
    },
    "Plastic Waste": {
        "bin": "Red Bin",
        "color": "danger",
        "image": "red_bin.png"
    },
    "Metal Waste": {
        "bin": "Yellow Bin",
        "color": "warning",
        "image": "yellow_bin.png"
    }
}

# Threshold of items per bin before auto "bin full" alert (when using uploads)
BIN_ITEM_ALERT_THRESHOLD = 10


def create_app():
    app = Flask(__name__)
    app.secret_key = "smartwaste_secret"
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MONGO_URI'] = "mongodb://localhost:27017/smart_waste"
    app.config['JWT_SECRET_KEY'] = "jwt_secret_key"

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    mongo.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    CORS(app)

    @app.context_processor
    def inject_globals():
        """Inject global variables into all templates"""
        unread_complaints = 0
        if session.get('role') == 'admin':
            try:
                unread_complaints = mongo.db.complaints.count_documents({"admin_read": False})
            except:
                pass
        return dict(unread_complaints=unread_complaints)
    
    # Register blueprints (imported here to avoid circular imports)
    # Temporarily disabled to fix HTTP 500 error
    # from routes.bins import bins_bp
    # app.register_blueprint(bins_bp)
    
    # In-memory bins storage (fallback if MongoDB fails)
    app.bins_storage = []
    
    # Direct routes for bins management
    @app.route('/seed-bins', methods=['GET', 'POST'])
    def seed_bins_route():
        """Seed sample bins with locations for demo"""
        print("🔧 seed-bins route called")
        
        if session.get('role') != 'admin':
            print("❌ Not admin")
            return jsonify({"error": "Admin only"}), 403
        
        try:
            print("📦 Starting to seed bins...")
            
            sample_bins = [
                {"bin_id": "BIN001", "area_name": "Downtown Plaza", "lat": 28.6139, "lng": 77.2090, "type": "Mixed", "waste_type": "Mixed", "capacity": 50, "status": "active"},
                {"bin_id": "BIN002", "area_name": "Central Park", "lat": 28.6126, "lng": 77.2000, "type": "Wet", "waste_type": "Wet", "capacity": 50, "status": "active"},
                {"bin_id": "BIN003", "area_name": "Market Square", "lat": 28.6200, "lng": 77.2200, "type": "Dry", "waste_type": "Dry", "capacity": 50, "status": "active"},
                {"bin_id": "BIN004", "area_name": "Tech Hub", "lat": 28.6040, "lng": 77.2180, "type": "Plastic", "waste_type": "Plastic", "capacity": 50, "status": "active"},
                {"bin_id": "BIN005", "area_name": "Railway Station", "lat": 28.6431, "lng": 77.2197, "type": "Metal", "waste_type": "Metal", "capacity": 50, "status": "active"},
                {"bin_id": "BIN006", "area_name": "University Campus", "lat": 28.5721, "lng": 77.1929, "type": "Paper", "waste_type": "Paper", "capacity": 50, "status": "active"},
                {"bin_id": "BIN007", "area_name": "Beach Promenade", "lat": 28.5566, "lng": 77.2931, "type": "Mixed", "waste_type": "Mixed", "capacity": 50, "status": "active"},
                {"bin_id": "BIN008", "area_name": "Shopping Mall", "lat": 28.5488, "lng": 77.2049, "type": "Plastic", "waste_type": "Plastic", "capacity": 50, "status": "active"},
            ]
            
            # Try MongoDB first
            try:
                mongo.db.command('ping')
                print("✅ MongoDB connected - using database")
                
                for bin_data in sample_bins:
                    result = mongo.db.bins.update_one(
                        {"bin_id": bin_data["bin_id"]},
                        {"$set": bin_data},
                        upsert=True
                    )
                    print(f"  - {bin_data['bin_id']}: matched={result.matched_count}, modified={result.modified_count}")
                
                print(f"✅ Successfully seeded {len(sample_bins)} bins to MongoDB")
                
            except Exception as mongo_error:
                print(f"⚠️ MongoDB not available: {mongo_error}")
                print("📝 Using in-memory storage instead")
                app.bins_storage = sample_bins.copy()
                print(f"✅ Successfully seeded {len(sample_bins)} bins to memory")
            
            return jsonify({"message": f"Seeded {len(sample_bins)} bins", "count": len(sample_bins)}), 200
            
        except Exception as e:
            print(f"❌ ERROR in /seed-bins: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route('/bins', methods=['GET'])
    def get_bins_route():
        """Get all bins with location data"""
        print("🔧 /bins route called")
        try:
            bins = []
            
            # Try MongoDB first
            try:
                mongo.db.command('ping')
                print("✅ MongoDB connected - fetching from database")
                bins = list(mongo.db.bins.find({}, {"_id": 0}))
                print(f"📊 Found {len(bins)} bins in MongoDB")
                
            except Exception as mongo_error:
                print(f"⚠️ MongoDB not available: {mongo_error}")
                print("📝 Using in-memory storage instead")
                bins = app.bins_storage.copy()
                print(f"📊 Found {len(bins)} bins in memory")
            
            enriched = []
            for b in bins:
                # If static lat/lng not present, attempt to get latest GPS for that bin
                if not b.get('lat') or not b.get('lng'):
                    try:
                        gps = mongo.db.gps.find_one({'bin_id': b.get('bin_id')}, sort=[('_id', -1)])
                        if gps:
                            b['lat'] = gps.get('lat')
                            b['lng'] = gps.get('lng')
                    except:
                        pass  # GPS lookup failed, use existing coordinates
                enriched.append(b)
            
            print(f"✅ Returning {len(enriched)} enriched bins")
            return jsonify(enriched), 200
            
        except Exception as e:
            print(f"❌ ERROR in /bins: {e}")
            import traceback
            traceback.print_exc()
            return jsonify([]), 200

    # ================= LOGIN =================
    @app.route('/', methods=['GET', 'POST'])
    def login():
        # Check for registration success message
        success_message = None
        if 'registration_success' in session:
            success_message = "Account created successfully! Please login with your credentials"
            session.pop('registration_success', None)
        
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')

            # Check admin credentials (default admin)
            if email == "admin@gmail.com" and password == "admin123":
                session['user'] = email
                session['role'] = 'admin'
                session['username'] = 'admin'
                log_activity('admin', 'Login', f'Admin logged in from {request.remote_addr}')
                return redirect(url_for('home'))
            
            # Check regular user in database
            user = mongo.db.users.find_one({"email": email})
            if user and bcrypt.check_password_hash(user['password'], password):
                session['user'] = email
                session['role'] = user.get('role', 'user')
                session['username'] = user.get('username', email)
                log_activity(session['username'], 'Login', f'User logged in from {request.remote_addr}')
                return redirect(url_for('home'))
            else:
                return render_template('auth/login.html', error="Invalid credentials")

        return render_template('auth/login.html', success=success_message)

    # ================= REGISTER =================
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            # Validate form data
            if not username or not email or not password or not confirm_password:
                return render_template('auth/register.html', error="All fields are required")
            
            if password != confirm_password:
                return render_template('auth/register.html', error="Passwords do not match")
            
            if len(password) < 8:
                return render_template('auth/register.html', error="Password must be at least 8 characters long")
            
            # Check if email already exists
            existing_user = mongo.db.users.find_one({"email": email})
            if existing_user:
                return render_template('auth/register.html', error="Email already registered. Please login or use a different email")
            
            # Check if username already exists
            existing_username = mongo.db.users.find_one({"username": username})
            if existing_username:
                return render_template('auth/register.html', error="Username already taken. Please choose a different one")

            try:
                # Hash password
                hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")

                # Create new user
                mongo.db.users.insert_one({
                    "username": username,
                    "email": email,
                    "password": hashed_pw,
                    "role": "user",
                    "created_at": datetime.now(),
                    "is_active": True
                })

                # Log registration activity
                log_activity(username, 'User Registration', f'New user registered from {request.remote_addr}')

                # Store success message in session and redirect to login
                session['registration_success'] = True
                return redirect(url_for('login'))
            except Exception as e:
                return render_template('auth/register.html', error=f"Registration failed: {str(e)}")

        return render_template('auth/register.html')

    # ================= HOME =================
    @app.route('/home')
    def home():
        if 'user' not in session:
            return redirect(url_for('login'))
        
        # Filter records based on user role
        current_user = session['user']
        user_role = session.get('role', 'user')
        
        # Admin sees all records, regular users see only their own
        if user_role == 'admin':
            records = list(mongo.db.waste_records.find().sort([("timestamp", -1)]))
        else:
            records = list(mongo.db.waste_records.find(
                {"uploaded_by": current_user}
            ).sort([("timestamp", -1)]))
        
        # Calculate statistics
        total = len(records)
        recycled_count = sum(1 for r in records if r.get('status') == 'Recycled')
        collected_count = sum(1 for r in records if r.get('status') == 'Collected')
        
        # Calculate average confidence
        confidences = [r.get('confidence', 0) for r in records if r.get('confidence')]
        avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else 0
        
        # Get recent records (last 5)
        recent_records = records[:5]
        
        return render_template(
            'home/home.html',
            total=total,
            recycled=recycled_count,
            collected=collected_count,
            avg_conf=avg_confidence,
            recent_records=recent_records
        )

    # ================= DASHBOARD =================
    @app.route('/dashboard')
    def dashboard():
        if 'user' not in session:
            return redirect(url_for('login'))

        # Filter records based on user role
        current_user = session['user']
        user_role = session.get('role', 'user')
        
        # Admin sees all records, regular users see only their own
        if user_role == 'admin':
            records = list(
                mongo.db.waste_records.find().sort(
                    [("timestamp", -1)]
                )
            )
        else:
            records = list(
                mongo.db.waste_records.find(
                    {"uploaded_by": current_user}
                ).sort([("timestamp", -1)])
            )

        # Calculate status counts
        recycled_count = sum(1 for r in records if r.get('status') == 'Recycled')
        collected_count = sum(1 for r in records if r.get('status') == 'Collected')
        disposed_count = sum(1 for r in records if r.get('status') == 'Disposed')
        in_transit_count = sum(1 for r in records if r.get('status') == 'In Transit')

        # Calculate average confidence
        confidences = [r.get('confidence', 0) for r in records if r.get('confidence')]
        avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else 0

        # Get notifications
        notifications = get_notifications(recipient=session.get('username', session['user']), limit=5)
        unread_count = get_unread_notification_count(session.get('username', session['user']))

        return render_template(
            'dashboard/dashboard.html',
            records=records,
            recycled_count=recycled_count,
            collected_count=collected_count,
            disposed_count=disposed_count,
            in_transit_count=in_transit_count,
            avg_confidence=avg_confidence,
            notifications=notifications,
            unread_count=unread_count
        )

    # ================= STATISTICS =================
    @app.route('/dashboard/map')
    def dashboard_map():
        if 'user' not in session:
            return redirect(url_for('login'))

        # Filter records based on user role
        current_user = session['user']
        user_role = session.get('role', 'user')
        
        # Admin sees all records, regular users see only their own
        if user_role == 'admin':
            records = list(
                mongo.db.waste_records.find().sort(
                    [("timestamp", -1)]
                )
            )
            # Admin sees latest waste from all users
            latest_waste = mongo.db.waste_records.find_one(
                sort=[("timestamp", -1)]
            ) if records else None
        else:
            records = list(
                mongo.db.waste_records.find(
                    {"uploaded_by": current_user}
                ).sort([("timestamp", -1)])
            )
            # Regular users see only their latest waste
            latest_waste = mongo.db.waste_records.find_one(
                {"uploaded_by": current_user},
                sort=[("timestamp", -1)]
            ) if records else None

        # Calculate status counts
        recycled_count = sum(1 for r in records if r.get('status') == 'Recycled')
        collected_count = sum(1 for r in records if r.get('status') == 'Collected')
        disposed_count = sum(1 for r in records if r.get('status') == 'Disposed')
        in_transit_count = sum(1 for r in records if r.get('status') == 'In Transit')

        # Calculate average confidence
        confidences = [r.get('confidence', 0) for r in records if r.get('confidence')]
        avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else 0

        # Get all bins for the map (bins are shared across all users)
        bins = list(mongo.db.bins.find({}).sort("bin_id", 1))

        return render_template('dashboard/map.html', 
                             records=records,
                             bins=bins,
                             latest_waste=latest_waste,
                             total_classifications=len(records),
                             recycled_count=recycled_count,
                             collected_count=collected_count,
                             disposed_count=disposed_count,
                             in_transit_count=in_transit_count,
                             avg_confidence=avg_confidence)

    # Note: /seed-bins and /bins routes are now handled by the bins_bp blueprint in routes/bins.py
    
    @app.route('/test-mongo')
    def test_mongo():
        """Test MongoDB connection"""
        try:
            # Test connection
            mongo.db.command('ping')
            
            # Count bins
            bin_count = mongo.db.bins.count_documents({})
            
            # Get sample bin
            sample_bin = mongo.db.bins.find_one({}, {"_id": 0})
            
            return jsonify({
                "status": "connected",
                "database": "smart_waste",
                "bin_count": bin_count,
                "sample_bin": sample_bin
            }), 200
        except Exception as e:
            return jsonify({
                "status": "error",
                "error": str(e)
            }), 500
    
    @app.route('/test-bins')
    def test_bins():
        """Debug endpoint to check bins in database"""
        try:
            count = mongo.db.bins.count_documents({})
            sample = list(mongo.db.bins.find({}, {"_id": 0}).limit(3))
            return jsonify({
                "total_count": count,
                "sample_bins": sample,
                "message": f"Database has {count} bins"
            })
        except Exception as e:
            return jsonify({"error": str(e)})

    # ================= BIN ID GENERATION (2.1.2) =================
    def generate_bin_id():
        """
        Auto-generate a unique Bin ID with standard format: BINxxxxx
        Format: BIN-YYMMDD-NNNNN (Year-Month-Day-Sequence)
        Example: BIN-260207-00001, BIN-260207-00002
        """
        from datetime import datetime
        today = datetime.now().strftime('%y%m%d')
        # Get count of bins created today
        today_count = mongo.db.bins.count_documents({"created_date": datetime.now().strftime('%y%m%d')})
        sequence = str(today_count + 1).zfill(5)
        return f"BIN-{today}-{sequence}"

    @app.route('/api/bin/create', methods=['POST'])
    def create_bin_auto():
        """
        Create a new bin with auto-generated ID
        POST data: {area_name, lat, lng, type, capacity (optional)}
        Returns: {bin_id, area_name, lat, lng, type, capacity, created_at}
        """
        if 'user' not in session or session.get('role') != 'admin':
              return jsonify({"error": "Admin access required"}), 403

        try:
            data = request.get_json()
            bin_id = generate_bin_id()

            new_bin = {
                "bin_id": bin_id,
                "area_name": data.get('area_name', 'Unknown Area'),
                "lat": float(data.get('lat', 0)),
                "lng": float(data.get('lng', 0)),
                "type": data.get('type', 'Mixed'),
                "capacity": int(data.get('capacity', 50)),
                "status": "active",
                "created_at": datetime.now(),
                "created_date": datetime.now().strftime('%y%m%d'),
                "created_by": session.get('username', session['user']),
                "sensor_enabled": False,
                "sensor_type": None,
                "last_synced": None
            }

            mongo.db.bins.insert_one(new_bin)

            log_activity(
                session.get('username', session['user']),
                'Create Bin',
                f'Created new bin {bin_id} in {data.get("area_name")}'
            )

            return jsonify({
                "message": "Bin created successfully",
                "bin": {k: v for k, v in new_bin.items()
                        if k != '_id' and not isinstance(v, datetime)}
            }), 201

        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/api/bin/cleanup-duplicates', methods=['POST'])
    def cleanup_duplicate_bins():
        """
        Remove duplicate bins with format BIN-YYMMDD-NNNNN that have 'Shopping Mall' as area_name
        This is an admin-only cleanup function
        """
        if 'user' not in session or session.get('role') != 'admin':
            return jsonify({"error": "Admin access required"}), 403

        try:
            # Delete bins that match the pattern BIN-YYMMDD-NNNNN with Shopping Mall
            result = mongo.db.bins.delete_many({
                "bin_id": {"$regex": "^BIN-\\d{6}-\\d{5}$"},
                "area_name": "Shopping Mall"
            })

            log_activity(
                session.get('username', session['user']),
                'Cleanup Bins',
                f'Removed {result.deleted_count} duplicate bins'
            )

            return jsonify({
                "message": f"Successfully removed {result.deleted_count} duplicate bins",
                "deleted_count": result.deleted_count
            }), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/admin/cleanup-bins')
    def admin_cleanup_bins_page():
        """Admin page to cleanup duplicate bins"""
        if 'user' not in session or session.get('role') != 'admin':
            return redirect(url_for('login'))
        return send_from_directory('.', 'cleanup_bins.html')

    @app.route('/api/bin/<bin_id>/sensor-sync', methods=['POST'])
    def sync_bin_sensor(bin_id):
        """
        IoT Sensor Sync Endpoint
        Used by IoT sensors (ultrasonic, weight, RFID) to update bin status
        
        REQUEST BODY:
        {
            "sensor_type": "ultrasonic|weight|rfid",
            "fullness_percent": 75,
            "weight_kg": 45.2,
            "last_emptied": "2026-02-07T10:30:00Z"
        }
        
        This endpoint received data from:
        - Ultrasonic sensors: Measure distance to detect fullness %
        - Weight sensors: Measure total weight for capacity estimation
        - RFID sensors: Track bin movement and collection events
        """
        try:
            data = request.get_json()
            sensor_type = data.get('sensor_type')
            
            update_doc = {
                "last_synced": datetime.now(),
                "sensor_type": sensor_type,
                "sensor_enabled": True
            }
            
            # Log sensor-specific data
            if sensor_type == "ultrasonic":
                update_doc["fullness_percent"] = data.get('fullness_percent', 0)
            elif sensor_type == "weight":
                update_doc["weight_kg"] = data.get('weight_kg', 0)
            elif sensor_type == "rfid":
                update_doc["last_collection"] = data.get('last_collection')
                update_doc["collection_count"] = mongo.db.bins.find_one({"bin_id": bin_id}, {"collection_count": 1}).get("collection_count", 0) + 1
            
            mongo.db.bins.update_one(
                {"bin_id": bin_id},
                {"$set": update_doc}
            )
            
            # If fullness > 85%, trigger auto-alert and ensure a pending pickup
            if update_doc.get('fullness_percent', 0) > 85:
                create_notification(
                    notification_type="bin_full",
                    title="🚨 Bin Near Capacity (IoT Sensor)",
                    message=f"Bin {bin_id} is {update_doc['fullness_percent']}% full",
                    recipient=None,
                    icon="exclamation-triangle",
                    severity="danger"
                )
                # NOTE: Pickup will be created when user clicks "Allow" on notification
            
            return jsonify({
                "message": f"Bin {bin_id} synced with {sensor_type} sensor",
                "timestamp": datetime.now().isoformat()
            }), 200
            
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    # ================= STATISTICS =================
    @app.route('/statistics')
    def view_statistics():
        if 'user' not in session:
            return redirect(url_for('login'))

        # Filter records based on user role
        current_user = session['user']
        user_role = session.get('role', 'user')
        
        # Build query filter
        if user_role == 'admin':
            query_filter = {}
        else:
            query_filter = {"uploaded_by": current_user}

        total = mongo.db.waste_records.count_documents(query_filter)

        stats_cursor = mongo.db.waste_records.aggregate([
            {"$match": query_filter},
            {
                "$group": {
                    "_id": "$predicted_type",
                    "count": {"$sum": 1}
                }
            }
        ])

        waste_stats = {item["_id"]: item["count"] for item in stats_cursor}

        # ---------- Environmental impact estimates ----------
        # Per-item average weights (kg) — approximate defaults
        WEIGHTS_KG = {
            'Plastic Waste': 0.12,
            'Wet Waste': 0.18,
            'Dry Waste': 0.15,
            'Metal Waste': 0.05
        }

        # Estimated CO2 saved (kg CO2 per kg recycled)
        CO2_SAVED_PER_KG = {
            'Plastic Waste': 2.5,
            'Wet Waste': 0.4,
            'Dry Waste': 0.9,
            'Metal Waste': 1.8
        }

        # Count collected items per type (items that have been collected are considered processed)
        # Changed from "Recycled" to "Collected" status
        collected_filter = {**query_filter, "status": "Collected"}
        collected_cursor = mongo.db.waste_records.aggregate([
            {"$match": collected_filter},
            {"$group": {"_id": "$predicted_type", "count": {"$sum": 1}}}
        ])
        collected_by_type = {item["_id"]: item["count"] for item in collected_cursor}

        # Plastic saved (kg) — plastic items collected * average weight
        plastic_collected_count = collected_by_type.get('Plastic Waste', 0)
        plastic_saved_kg = round(plastic_collected_count * WEIGHTS_KG.get('Plastic Waste', 0), 2)

        # CO2 emission reduced (estimated) - based on collected items
        total_co2_saved = 0.0
        total_collected_count = 0
        for t, cnt in collected_by_type.items():
            w = WEIGHTS_KG.get(t, 0)
            co2_per = CO2_SAVED_PER_KG.get(t, 0)
            total_co2_saved += cnt * w * co2_per
            total_collected_count += cnt
        total_co2_saved = round(total_co2_saved, 2)

        # Recycling percentage - based on collected items
        recycling_percentage = round((total_collected_count / total * 100), 1) if total > 0 else 0.0

        # Get all users for admin dropdown (admin only)
        all_users = []
        if user_role == 'admin':
            all_users = list(
                mongo.db.users.find(
                    {"role": {"$ne": "admin"}},
                    {"_id": 0, "username": 1, "email": 1}
                ).sort("username", 1)
            )

        return render_template(
            'dashboard/statistics.html',
            total=total,
            waste_stats=waste_stats,
            plastic_saved_kg=plastic_saved_kg,
            total_co2_saved=total_co2_saved,
            recycling_percentage=recycling_percentage,
            all_users=all_users,
            now=datetime.now()
        )

    # ================= MONTHLY PDF REPORT =================
    @app.route('/download_monthly_report/<int:year>/<int:month>')
    def download_monthly_report(year, month):
        if 'user' not in session:
            return redirect(url_for('login'))
        
        # Filter records based on user role
        current_user = session['user']
        user_role = session.get('role', 'user')
        
        # Build query filter
        if user_role == 'admin':
            user_filter = {}
        else:
            user_filter = {"uploaded_by": current_user}
        
        try:
            # Get the first and last day of the selected month
            first_day = datetime(year, month, 1)
            if month == 12:
                last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = datetime(year, month + 1, 1) - timedelta(days=1)
            
            # Query waste records for the selected month
            month_start = datetime.combine(first_day, datetime.min.time())
            month_end = datetime.combine(last_day, datetime.max.time())
            
            # Get waste statistics for the month with user filter
            monthly_stats_cursor = mongo.db.waste_records.aggregate([
                {
                    "$match": {
                        **user_filter,
                        "timestamp": {"$gte": month_start, "$lte": month_end}
                    }
                },
                {
                    "$group": {
                        "_id": "$predicted_type",
                        "count": {"$sum": 1}
                    }
                }
            ])
            
            monthly_waste_stats = {item["_id"]: item["count"] for item in monthly_stats_cursor}
            monthly_total = sum(monthly_waste_stats.values())
            
            # Check if there's any data for the selected month
            if monthly_total == 0:
                return jsonify({"error": f"No data found for {first_day.strftime('%B %Y')}. Please select a month with recorded waste data."}), 404
            
            # Get collected items for the month with user filter (changed from Recycled to Collected)
            monthly_collected_cursor = mongo.db.waste_records.aggregate([
                {
                    "$match": {
                        **user_filter,
                        "timestamp": {"$gte": month_start, "$lte": month_end},
                        "status": "Collected"
                    }
                },
                {
                    "$group": {
                        "_id": "$predicted_type",
                        "count": {"$sum": 1}
                    }
                }
            ])
            
            monthly_collected = {item["_id"]: item["count"] for item in monthly_collected_cursor}
            monthly_collected_total = sum(monthly_collected.values())
            
            # Calculate environmental impact for the month
            WEIGHTS_KG = {
                'Plastic Waste': 0.12,
                'Wet Waste': 0.18,
                'Dry Waste': 0.15,
                'Metal Waste': 0.05
            }
            
            CO2_SAVED_PER_KG = {
                'Plastic Waste': 2.5,
                'Wet Waste': 0.4,
                'Dry Waste': 0.9,
                'Metal Waste': 1.8
            }
            
            monthly_plastic_saved = round(monthly_collected.get('Plastic Waste', 0) * WEIGHTS_KG.get('Plastic Waste', 0), 2)
            monthly_co2_saved = 0.0
            for waste_type, count in monthly_collected.items():
                weight = WEIGHTS_KG.get(waste_type, 0)
                co2_per_kg = CO2_SAVED_PER_KG.get(waste_type, 0)
                monthly_co2_saved += count * weight * co2_per_kg
            monthly_co2_saved = round(monthly_co2_saved, 2)
            
            monthly_recycling_rate = round((monthly_collected_total / monthly_total * 100), 1) if monthly_total > 0 else 0.0
            
            # Generate PDF
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, 
                                  rightMargin=50, leftMargin=50,
                                  topMargin=50, bottomMargin=30)
            story = []
            
            # Get styles
            styles = getSampleStyleSheet()
            
            # Premium professional styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=28,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#1B5E20'),
                fontName='Helvetica-Bold',
                borderWidth=2,
                borderColor=colors.HexColor('#4CAF50'),
                borderPadding=15,
                backColor=colors.HexColor('#E8F5E8'),
                borderRadius=10
            )
            
            subtitle_style = ParagraphStyle(
                'CustomSubtitle',
                parent=styles['Heading2'],
                fontSize=16,
                spaceAfter=25,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#2E7D32'),
                fontName='Helvetica-Oblique',
                italic=True
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=18,
                spaceAfter=20,
                spaceBefore=25,
                textColor=colors.white,
                fontName='Helvetica-Bold',
                borderWidth=1,
                borderColor=colors.HexColor('#4CAF50'),
                borderPadding=12,
                backColor=colors.HexColor('#2E7D32'),
                borderRadius=5,
                leading=22
            )
            
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontSize=11,
                spaceAfter=8,
                textColor=colors.black,
                fontName='Helvetica',
                leading=14
            )
            
            # Company Header
            header_data = [
                ['Smart Waste Management System', 'Environmental Impact Report'],
                ['Monthly Analytics Dashboard', 'Generated: ' + datetime.now().strftime('%Y-%m-%d %H:%M')]
            ]
            
            header_table = Table(header_data, colWidths=[3*inch, 3*inch])
            header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F8E9')),
                ('BORDERS', (0, 0), (-1, -1), 'RECT', colors.HexColor('#4CAF50'), 1),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('FONTSIZE', (0, 1), (-1, 1), 10),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1B5E20')),
                ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#2E7D32')),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            
            story.append(header_table)
            story.append(Spacer(1, 25))
            
            # Title
            month_name = calendar.month_name[month]
            title = Paragraph(f"Monthly Waste Management Report<br/>{month_name} {year}", title_style)
            story.append(title)
            story.append(Spacer(1, 20))
            
            # Summary Section
            story.append(Paragraph("Summary", heading_style))
            story.append(Spacer(1, 10))
            
            summary_data = [
                ['Metric', 'Value'],
                ['Total Waste Items', str(monthly_total)],
                ['Collected Items', str(monthly_collected_total)],
                ['Recycling Rate', f"{monthly_recycling_rate}%"],
                ['Plastic Saved', f"{monthly_plastic_saved} kg"],
                ['CO₂ Reduced', f"{monthly_co2_saved} kg"]
            ]
            
            summary_table = Table(summary_data, colWidths=[2.8*inch, 2.8*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B5E20')), # Darker green header
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), # White text for header
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 13),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 18),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')), # Light background
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#C8E6C9')), # Subtle green grid lines
                ('LEFTPADDING', (0,0), (-1,-1), 15),
                ('RIGHTPADDING', (0,0), (-1,-1), 15),
                ('TOPPADDING', (0,0), (-1,-1), 12),
                ('BOTTOMPADDING', (0,0), (-1,-1), 12),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 11),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F8E9')]), # Alternating rows
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BORDERS', (0, 0), (-1, -1), 'RECT', colors.HexColor('#4CAF50'), 2) # Outer border
            ]))
            
            story.append(summary_table)
            story.append(Spacer(1, 20))
            
            # Waste Type Breakdown
            if monthly_waste_stats:
                story.append(Paragraph("Waste Type Breakdown", heading_style))
                story.append(Spacer(1, 10))
                
                waste_data = [['Waste Type', 'Count', 'Percentage']]
                for waste_type, count in monthly_waste_stats.items():
                    percentage = round((count / monthly_total * 100), 1) if monthly_total > 0 else 0
                    waste_data.append([waste_type, str(count), f"{percentage}%"])
                
                waste_table = Table(waste_data, colWidths=[2.2*inch, 1.7*inch, 1.7*inch])
                waste_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B5E20')), # Darker green header
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), # White text for header
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 13),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 18),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')), # Light background
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#C8E6C9')), # Subtle green grid lines
                    ('LEFTPADDING', (0,0), (-1,-1), 15),
                    ('RIGHTPADDING', (0,0), (-1,-1), 15),
                    ('TOPPADDING', (0,0), (-1,-1), 12),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 12),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 11),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F8E9')]), # Alternating rows
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('BORDERS', (0, 0), (-1, -1), 'RECT', colors.HexColor('#4CAF50'), 2) # Outer border
                ]))
                
                story.append(waste_table)
                story.append(Spacer(1, 20))
            
            # Premium Chart
            if monthly_waste_stats:
                story.append(Paragraph("Waste Distribution Chart", heading_style))
                story.append(Spacer(1, 20))
                
                plt.figure(figsize=(8, 6), facecolor='white')
                waste_types = list(monthly_waste_stats.keys())
                counts = list(monthly_waste_stats.values())
                premium_colors = ['#1B5E20', '#2E7D32', '#4CAF50', '#81C784'] # Premium green gradient
                
                # Create pie chart with premium styling
                wedges, texts, autotexts = plt.pie(counts, 
                                                  labels=waste_types, 
                                                  autopct='%1.1f%%',
                                                  colors=premium_colors[:len(waste_types)],
                                                  startangle=90,
                                                  explode=[0.05]*len(waste_types), # Slight separation
                                                  textprops={'fontsize': 12, 'fontweight': 'bold'},
                                                  wedgeprops={'linewidth': 2, 'edgecolor': 'white'})
                
                # Enhance text appearance
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontweight('bold')
                    autotext.set_fontsize(11)
                    autotext.set_bbox(dict(boxstyle="round,pad=0.3", facecolor='#1B5E20', alpha=0.8))
                
                plt.title('Waste Distribution Analysis - ' + month_name + ' ' + str(year), 
                         fontsize=18, fontweight='bold', pad=25, color='#1B5E20')
                
                # Add professional styling
                centre_circle = plt.Circle((0,0),0.70,fc='white',linewidth=2, edgecolor='#4CAF50')
                fig = plt.gcf()
                fig.gca().add_artist(centre_circle)
                
                # Save chart to buffer with premium quality
                chart_buffer = BytesIO()
                plt.savefig(chart_buffer, format='png', dpi=400, bbox_inches='tight', 
                           facecolor='white', edgecolor='none', transparent=False)
                chart_buffer.seek(0)
                plt.close()
                
                # Add centered chart to PDF with border
                chart_wrapper = Table([[Image(chart_buffer, width=5.5*inch, height=4.125*inch)]], 
                                    colWidths=[5.5*inch])
                chart_wrapper.setStyle(TableStyle([
                    ('BORDERS', (0, 0), (-1, -1), 'RECT', colors.HexColor('#4CAF50'), 2),
                    ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                    ('PADDING', (0, 0), (-1, -1), 10),
                ]))
                story.append(chart_wrapper)
            
            # Professional Footer
            story.append(Spacer(1, 25))
            
            footer_line = Table([['', '', '']], colWidths=[1.5*inch, 3*inch, 1.5*inch])
            footer_line.setStyle(TableStyle([
                ('LINEABOVE', (1, 0), (1, 0), 2, colors.HexColor('#4CAF50')),
            ]))
            story.append(footer_line)
            story.append(Spacer(1, 15))
            
            footer_data = [
                ['Report ID:', f'WR-{year}{month:02d}-{monthly_total:04d}'],
                ['Generated:', datetime.now().strftime('%B %d, %Y at %I:%M %p')],
                ['System:', 'Smart Waste Management v2.0'],
                ['Classification:', 'Environmental Analytics'],
                ['Contact:', 'analytics@smartwaste.com']
            ]
            
            footer_table = Table(footer_data, colWidths=[1.2*inch, 4.8*inch])
            footer_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('FONTSIZE', (1, 0), (-1, -1), 9),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1B5E20')),
                ('TEXTCOLOR', (1, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3)
            ]))
            
            story.append(footer_table)
            
            # Build PDF
            doc.build(story)
            buffer.seek(0)
            
            # Create filename
            filename = f"waste-report-{year}-{month:02d}.pdf"
            
            return send_file(
                buffer,
                as_attachment=True,
                download_name=filename,
                mimetype='application/pdf'
            )
            
        except Exception as e:
            print(f"Error generating PDF: {e}")
            return jsonify({"error": "Failed to generate PDF report"}), 500

    # ================= UPLOAD =================
    @app.route('/upload')
    def upload():
        if 'user' not in session or session.get('role') == 'admin':
            return redirect(url_for('login'))
        
        # Get all bins for dropdown selection
        bins = list(mongo.db.bins.find({}).sort("bin_id", 1))
        
        return render_template('waste/upload.html', bins=bins)

    # ================= PREDICT =================
    @app.route('/predict', methods=['POST'])
    def predict():
        if 'user' not in session or session.get('role') == 'admin':
            return redirect(url_for('login'))

        try:
            img_file = request.files.get('image')
            if not img_file or img_file.filename == '':
                return render_template('waste/upload.html', error="No file selected", bins=[])

            # Validate file type
            if not img_file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                return render_template('waste/upload.html', error="Invalid file type. Please upload an image file", bins=[])

            filename = secure_filename(img_file.filename)
            
            # Ensure upload directory exists
            upload_dir = app.config['UPLOAD_FOLDER']
            os.makedirs(upload_dir, exist_ok=True)
            
            image_path = os.path.join(upload_dir, filename)
            img_file.save(image_path)

            # Optional bin association from the form
            raw_bin_id = request.form.get('bin_id')
            bin_id = normalize_bin_id(raw_bin_id) if raw_bin_id else None
            
            print(f"DEBUG: Processing file: {filename}")
            print(f"DEBUG: bin_id: {bin_id}")

            name = filename.lower()

            if "plastic" in name:
                predicted_class = "Plastic Waste"
                confidence = 92
            elif "food" in name or "wet" in name:
                predicted_class = "Wet Waste"
                confidence = 90
            elif "metal" in name:
                predicted_class = "Metal Waste"
                confidence = 88
            else:
                predicted_class = "Dry Waste"
                confidence = 85

            suggestion = BIN_MAPPING[predicted_class]

            # Store classification data in session for result page
            session['classification_result'] = {
                'uploaded_image': filename,
                'waste_type': predicted_class,
                'confidence': confidence,
                'bin': suggestion["bin"],
                'color': suggestion["color"],
                'image': suggestion["image"],
                'bin_id': bin_id
            }

            # Insert into database with error handling
            try:
                mongo.db.waste_records.insert_one({
                    "image": filename,
                    "predicted_type": predicted_class,
                    "confidence": confidence,
                    "bin": suggestion["bin"],
                    "bin_id": bin_id,
                    "status": "In Transit",
                    "uploaded_by": session['user'],
                    "timestamp": datetime.now()
                })
                print("Successfully inserted into database")
            except Exception as db_error:
                print(f"Database error: {db_error}")
                print("Continuing without database storage")

            # Log classification action
            try:
                log_activity(
                    session.get('username', session['user']),
                    'Upload & Classification',
                    f'Classified waste as {predicted_class} with {confidence}% confidence'
                )
            except Exception as log_error:
                print(f"Log error: {log_error}")
            
            # Redirect to result page with classification data
            return redirect(url_for('result'))

        except Exception as e:
            print(f"Predict route error: {e}")
            return render_template('waste/upload.html', error=f"Upload failed: {str(e)}", bins=[])

    # ================= RESULT PAGE =================
    @app.route('/result')
    def result():
        if 'user' not in session:
            return redirect(url_for('login'))
        
        # Get classification data from session (stored during upload)
        classification_data = session.pop('classification_result', None)
        
        if classification_data:
            return render_template('result.html', **classification_data)
        else:
            # Fallback to basic result page if no data in session
            return render_template('result.html')

    # ================= PDF MONTHLY REPORT EXPORT =================
    @app.route('/export/report/pdf')
    def export_report_pdf():
        # Import reportlab here to avoid import errors if not installed
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Image as RLImage, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from collections import Counter

        if 'user' not in session:
            return redirect(url_for('login'))

        # month param in YYYY-MM, default to current month
        month = request.args.get('month')
        if month:
            try:
                year, mon = map(int, month.split('-'))
                start = datetime(year, mon, 1)
            except Exception:
                start = datetime(datetime.now().year, datetime.now().month, 1)
        else:
            start = datetime(datetime.now().year, datetime.now().month, 1)

        # end of month
        if start.month == 12:
            end = datetime(start.year + 1, 1, 1)
        else:
            end = datetime(start.year, start.month + 1, 1)

        # Filter records based on user role
        current_user = session['user']
        user_role = session.get('role', 'user')
        
        # Query waste records in the month with user filtering
        if user_role == 'admin':
            monthly_records = list(mongo.db.waste_records.find({"timestamp": {"$gte": start, "$lt": end}}))
        else:
            monthly_records = list(mongo.db.waste_records.find({
                "uploaded_by": current_user,
                "timestamp": {"$gte": start, "$lt": end}
            }))

        # Aggregate counts
        ctr = Counter()
        for r in monthly_records:
            ctr[r.get('predicted_type', 'Unknown')] += 1

        labels = list(ctr.keys())
        counts = [ctr[k] for k in labels]

        # Create chart image
        try:
            fig, ax = plt.subplots(figsize=(8,4))
            ax.bar(labels, counts, color=[ '#20c997' if 'Wet' in l else '#0dcaf0' if 'Dry' in l else '#dc3545' if 'Plastic' in l else '#ffc107' for l in labels ])
            ax.set_title(f'Waste collected - {start.strftime("%B %Y")}')
            ax.set_ylabel('Count')
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha='right')
            plt.tight_layout()

            tmp_png = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            fig.savefig(tmp_png.name)
            plt.close(fig)
        except Exception:
            tmp_png = None

        # Build PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        story.append(Paragraph(f'Monthly Waste Report — {start.strftime("%B %Y")}', styles['Title']))
        story.append(Spacer(1, 12))

        # Add chart
        if tmp_png:
            story.append(RLImage(tmp_png.name, width=450, height=200))
            story.append(Spacer(1,12))

        # Table of counts
        table_data = [[ 'Waste Type', 'Count' ]]
        for k in labels:
            table_data.append([k, ctr[k]])
        table = Table(table_data, colWidths=[350, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#198754')),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('ALIGN',(1,1),(-1,-1),'RIGHT'),
            ('GRID',(0,0),(-1,-1),0.5,colors.grey)
        ]))
        story.append(table)
        story.append(Spacer(1,12))

        # Environmental stats
        # Reuse simple estimates
        weights = { 'Plastic Waste':0.12, 'Wet Waste':0.18, 'Dry Waste':0.15, 'Metal Waste':0.05 }
        co2_per = { 'Plastic Waste':2.5, 'Wet Waste':0.4, 'Dry Waste':0.9, 'Metal Waste':1.8 }
        total_co2 = 0.0
        for k,v in ctr.items():
            w = weights.get(k,0)
            total_co2 += v * w * co2_per.get(k,0)
        story.append(Paragraph(f'Estimated CO2 reduced (kg): {round(total_co2,2)}', styles['Normal']))

        doc.build(story)
        buffer.seek(0)

        # cleanup tmp
        if tmp_png:
            try:
                os.unlink(tmp_png.name)
            except:
                pass

        filename = f'waste-report-{start.strftime("%Y-%m")}.pdf'
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

    # ================= ADMIN - DOWNLOAD USER-SPECIFIC REPORT =================
    @app.route('/admin/download_user_report/<int:year>/<int:month>/<username>')
    def download_user_report(year, month, username):
        """Admin-only: Download monthly report for a specific user"""
        if 'user' not in session or session.get('role') != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        
        # Verify user exists and get their email
        user = mongo.db.users.find_one({"username": username})
        if not user:
            return jsonify({"error": f"User '{username}' not found"}), 404
        
        # Get the user's email (this is what's stored in uploaded_by field)
        user_email = user.get('email')
        if not user_email:
            return jsonify({"error": f"User '{username}' has no email address"}), 404
        
        try:
            # Get the first and last day of the selected month
            first_day = datetime(year, month, 1)
            if month == 12:
                last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = datetime(year, month + 1, 1) - timedelta(days=1)
            
            month_start = datetime.combine(first_day, datetime.min.time())
            month_end = datetime.combine(last_day, datetime.max.time())
            
            # Filter for specific user using their EMAIL (not username)
            user_filter = {"uploaded_by": user_email}
            
            # Get waste statistics for the month
            monthly_stats_cursor = mongo.db.waste_records.aggregate([
                {
                    "$match": {
                        **user_filter,
                        "timestamp": {"$gte": month_start, "$lte": month_end}
                    }
                },
                {
                    "$group": {
                        "_id": "$predicted_type",
                        "count": {"$sum": 1}
                    }
                }
            ])
            
            monthly_waste_stats = {item["_id"]: item["count"] for item in monthly_stats_cursor}
            monthly_total = sum(monthly_waste_stats.values())
            
            if monthly_total == 0:
                return jsonify({"error": f"No data found for user '{username}' in {first_day.strftime('%B %Y')}"}), 404
            
            # Get collected items for the month
            monthly_collected_cursor = mongo.db.waste_records.aggregate([
                {
                    "$match": {
                        **user_filter,
                        "timestamp": {"$gte": month_start, "$lte": month_end},
                        "status": "Collected"
                    }
                },
                {
                    "$group": {
                        "_id": "$predicted_type",
                        "count": {"$sum": 1}
                    }
                }
            ])
            
            monthly_collected = {item["_id"]: item["count"] for item in monthly_collected_cursor}
            monthly_collected_total = sum(monthly_collected.values())
            
            # Calculate environmental impact
            WEIGHTS_KG = {
                'Plastic Waste': 0.12,
                'Wet Waste': 0.18,
                'Dry Waste': 0.15,
                'Metal Waste': 0.05
            }
            
            CO2_SAVED_PER_KG = {
                'Plastic Waste': 2.5,
                'Wet Waste': 0.4,
                'Dry Waste': 0.9,
                'Metal Waste': 1.8
            }
            
            monthly_plastic_saved = round(monthly_collected.get('Plastic Waste', 0) * WEIGHTS_KG.get('Plastic Waste', 0), 2)
            monthly_co2_saved = 0.0
            for waste_type, count in monthly_collected.items():
                weight = WEIGHTS_KG.get(waste_type, 0)
                co2_per_kg = CO2_SAVED_PER_KG.get(waste_type, 0)
                monthly_co2_saved += count * weight * co2_per_kg
            monthly_co2_saved = round(monthly_co2_saved, 2)
            
            monthly_recycling_rate = round((monthly_collected_total / monthly_total * 100), 1) if monthly_total > 0 else 0.0
            
            # Generate PDF with pie chart (same as personal report)
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            
            # Title style
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=26,
                spaceAfter=20,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#1B5E20'),
                fontName='Helvetica-Bold'
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=18,
                spaceAfter=20,
                spaceBefore=25,
                textColor=colors.white,
                fontName='Helvetica-Bold',
                borderWidth=1,
                borderColor=colors.HexColor('#4CAF50'),
                borderPadding=12,
                backColor=colors.HexColor('#2E7D32'),
                borderRadius=5,
                leading=22
            )
            
            # Company Header
            header_data = [
                ['Smart Waste Management System', 'Environmental Impact Report'],
                ['Monthly Analytics Dashboard', 'Generated: ' + datetime.now().strftime('%Y-%m-%d %H:%M')]
            ]
            
            header_table = Table(header_data, colWidths=[3*inch, 3*inch])
            header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F8E9')),
                ('BORDERS', (0, 0), (-1, -1), 'RECT', colors.HexColor('#4CAF50'), 1),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('FONTSIZE', (0, 1), (-1, 1), 10),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1B5E20')),
                ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#2E7D32')),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            
            story.append(header_table)
            story.append(Spacer(1, 25))
            
            # Title
            month_name = calendar.month_name[month]
            title = Paragraph(f"User Report: {username}<br/>{month_name} {year}", title_style)
            story.append(title)
            story.append(Spacer(1, 20))
            
            # Summary Section
            story.append(Paragraph("Summary", heading_style))
            story.append(Spacer(1, 10))
            
            summary_data = [
                ['Metric', 'Value'],
                ['Total Classifications', str(monthly_total)],
                ['Collected Items', str(monthly_collected_total)],
                ['Recycling Rate', f"{monthly_recycling_rate}%"],
                ['Plastic Saved', f"{monthly_plastic_saved} kg"],
                ['CO₂ Reduced', f"{monthly_co2_saved} kg"]
            ]
            
            summary_table = Table(summary_data, colWidths=[2.8*inch, 2.8*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B5E20')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 13),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 18),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#C8E6C9')),
                ('LEFTPADDING', (0,0), (-1,-1), 15),
                ('RIGHTPADDING', (0,0), (-1,-1), 15),
                ('TOPPADDING', (0,0), (-1,-1), 12),
                ('BOTTOMPADDING', (0,0), (-1,-1), 12),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 11),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F8E9')]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BORDERS', (0, 0), (-1, -1), 'RECT', colors.HexColor('#4CAF50'), 2)
            ]))
            
            story.append(summary_table)
            story.append(Spacer(1, 20))
            
            # Waste Type Breakdown
            if monthly_waste_stats:
                story.append(Paragraph("Waste Type Breakdown", heading_style))
                story.append(Spacer(1, 10))
                
                waste_data = [['Waste Type', 'Count', 'Percentage']]
                for waste_type, count in monthly_waste_stats.items():
                    percentage = round((count / monthly_total * 100), 1) if monthly_total > 0 else 0
                    waste_data.append([waste_type, str(count), f"{percentage}%"])
                
                waste_table = Table(waste_data, colWidths=[2.2*inch, 1.7*inch, 1.7*inch])
                waste_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B5E20')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 13),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 18),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#C8E6C9')),
                    ('LEFTPADDING', (0,0), (-1,-1), 15),
                    ('RIGHTPADDING', (0,0), (-1,-1), 15),
                    ('TOPPADDING', (0,0), (-1,-1), 12),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 12),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 11),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F8E9')]),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('BORDERS', (0, 0), (-1, -1), 'RECT', colors.HexColor('#4CAF50'), 2)
                ]))
                
                story.append(waste_table)
                story.append(Spacer(1, 20))
            
            # Premium Pie Chart
            if monthly_waste_stats:
                story.append(Paragraph("Waste Distribution Chart", heading_style))
                story.append(Spacer(1, 20))
                
                plt.figure(figsize=(8, 6), facecolor='white')
                waste_types = list(monthly_waste_stats.keys())
                counts = list(monthly_waste_stats.values())
                premium_colors = ['#1B5E20', '#2E7D32', '#4CAF50', '#81C784']
                
                # Create pie chart with premium styling
                wedges, texts, autotexts = plt.pie(counts, 
                                                  labels=waste_types, 
                                                  autopct='%1.1f%%',
                                                  colors=premium_colors[:len(waste_types)],
                                                  startangle=90,
                                                  explode=[0.05]*len(waste_types),
                                                  textprops={'fontsize': 12, 'fontweight': 'bold'},
                                                  wedgeprops={'linewidth': 2, 'edgecolor': 'white'})
                
                # Enhance text appearance
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontweight('bold')
                    autotext.set_fontsize(11)
                    autotext.set_bbox(dict(boxstyle="round,pad=0.3", facecolor='#1B5E20', alpha=0.8))
                
                plt.title('Waste Distribution Analysis - ' + month_name + ' ' + str(year), 
                         fontsize=18, fontweight='bold', pad=25, color='#1B5E20')
                
                # Add professional styling (donut chart)
                centre_circle = plt.Circle((0,0),0.70,fc='white',linewidth=2, edgecolor='#4CAF50')
                fig = plt.gcf()
                fig.gca().add_artist(centre_circle)
                
                # Save chart to buffer with premium quality
                chart_buffer = BytesIO()
                plt.savefig(chart_buffer, format='png', dpi=400, bbox_inches='tight', 
                           facecolor='white', edgecolor='none', transparent=False)
                chart_buffer.seek(0)
                plt.close()
                
                # Add centered chart to PDF with border
                chart_wrapper = Table([[Image(chart_buffer, width=5.5*inch, height=4.125*inch)]], 
                                    colWidths=[5.5*inch])
                chart_wrapper.setStyle(TableStyle([
                    ('BORDERS', (0, 0), (-1, -1), 'RECT', colors.HexColor('#4CAF50'), 2),
                    ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                    ('PADDING', (0, 0), (-1, -1), 10),
                ]))
                story.append(chart_wrapper)
            
            # Professional Footer
            story.append(Spacer(1, 25))
            
            footer_line = Table([['', '', '']], colWidths=[1.5*inch, 3*inch, 1.5*inch])
            footer_line.setStyle(TableStyle([
                ('LINEABOVE', (1, 0), (1, 0), 2, colors.HexColor('#4CAF50')),
            ]))
            story.append(footer_line)
            story.append(Spacer(1, 15))
            
            footer_data = [
                ['Report ID:', f'WR-{year}{month:02d}-{monthly_total:04d}'],
                ['Generated:', datetime.now().strftime('%B %d, %Y at %I:%M %p')],
                ['System:', 'Smart Waste Management v2.0'],
                ['Classification:', 'Environmental Analytics'],
                ['Contact:', 'analytics@smartwaste.com']
            ]
            
            footer_table = Table(footer_data, colWidths=[1.2*inch, 4.8*inch])
            footer_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('FONTSIZE', (1, 0), (-1, -1), 9),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1B5E20')),
                ('TEXTCOLOR', (1, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3)
            ]))
            
            story.append(footer_table)
            
            doc.build(story)
            buffer.seek(0)
            
            filename = f'user-report-{username}-{first_day.strftime("%Y-%m")}.pdf'
            return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')
            
        except Exception as e:
            print(f"Error generating user report: {str(e)}")
            return jsonify({"error": str(e)}), 500

    # ================= ADMIN - DOWNLOAD OVERALL REPORT =================
    @app.route('/admin/download_overall_report/<int:year>/<int:month>')
    def download_overall_report(year, month):
        """Admin-only: Download overall monthly report for all users"""
        if 'user' not in session or session.get('role') != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        
        try:
            # Get the first and last day of the selected month
            first_day = datetime(year, month, 1)
            if month == 12:
                last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = datetime(year, month + 1, 1) - timedelta(days=1)
            
            month_start = datetime.combine(first_day, datetime.min.time())
            month_end = datetime.combine(last_day, datetime.max.time())
            
            # Get overall statistics (all users)
            monthly_stats_cursor = mongo.db.waste_records.aggregate([
                {
                    "$match": {
                        "timestamp": {"$gte": month_start, "$lte": month_end}
                    }
                },
                {
                    "$group": {
                        "_id": "$predicted_type",
                        "count": {"$sum": 1}
                    }
                }
            ])
            
            monthly_waste_stats = {item["_id"]: item["count"] for item in monthly_stats_cursor}
            monthly_total = sum(monthly_waste_stats.values())
            
            if monthly_total == 0:
                return jsonify({"error": f"No data found for {first_day.strftime('%B %Y')}"}), 404
            
            # Get per-user statistics
            user_stats_cursor = mongo.db.waste_records.aggregate([
                {
                    "$match": {
                        "timestamp": {"$gte": month_start, "$lte": month_end}
                    }
                },
                {
                    "$group": {
                        "_id": "$uploaded_by",
                        "total": {"$sum": 1},
                        "collected": {
                            "$sum": {
                                "$cond": [{"$eq": ["$status", "Collected"]}, 1, 0]
                            }
                        }
                    }
                },
                {"$sort": {"total": -1}}
            ])
            
            user_stats = list(user_stats_cursor)
            
            # Get collected items for environmental impact
            monthly_collected_cursor = mongo.db.waste_records.aggregate([
                {
                    "$match": {
                        "timestamp": {"$gte": month_start, "$lte": month_end},
                        "status": "Collected"
                    }
                },
                {
                    "$group": {
                        "_id": "$predicted_type",
                        "count": {"$sum": 1}
                    }
                }
            ])
            
            monthly_collected = {item["_id"]: item["count"] for item in monthly_collected_cursor}
            monthly_collected_total = sum(monthly_collected.values())
            
            # Calculate environmental impact
            WEIGHTS_KG = {
                'Plastic Waste': 0.12,
                'Wet Waste': 0.18,
                'Dry Waste': 0.15,
                'Metal Waste': 0.05
            }
            
            CO2_SAVED_PER_KG = {
                'Plastic Waste': 2.5,
                'Wet Waste': 0.4,
                'Dry Waste': 0.9,
                'Metal Waste': 1.8
            }
            
            monthly_plastic_saved = round(monthly_collected.get('Plastic Waste', 0) * WEIGHTS_KG.get('Plastic Waste', 0), 2)
            monthly_co2_saved = 0.0
            for waste_type, count in monthly_collected.items():
                weight = WEIGHTS_KG.get(waste_type, 0)
                co2_per_kg = CO2_SAVED_PER_KG.get(waste_type, 0)
                monthly_co2_saved += count * weight * co2_per_kg
            monthly_co2_saved = round(monthly_co2_saved, 2)
            
            monthly_recycling_rate = round((monthly_collected_total / monthly_total * 100), 1) if monthly_total > 0 else 0.0
            
            # Generate PDF
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=26,
                spaceAfter=20,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#1B5E20'),
                fontName='Helvetica-Bold'
            )
            
            story.append(Paragraph("Overall System Report", title_style))
            story.append(Paragraph(f"{first_day.strftime('%B %Y')}", styles['Heading2']))
            story.append(Spacer(1, 20))
            
            # Overall summary
            data = [
                ['Metric', 'Value'],
                ['Total Classifications', str(monthly_total)],
                ['Total Users', str(len(user_stats))],
                ['Collected Items', str(monthly_collected_total)],
                ['Plastic Saved', f'{monthly_plastic_saved} kg'],
                ['CO₂ Reduced', f'{monthly_co2_saved} kg'],
                ['Recycling Rate', f'{monthly_recycling_rate}%']
            ]
            
            table = Table(data, colWidths=[250, 200])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#E8F5E8')),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#4CAF50'))
            ]))
            
            story.append(table)
            story.append(Spacer(1, 30))
            
            # Per-user breakdown
            if user_stats:
                story.append(Paragraph("User Performance", styles['Heading2']))
                story.append(Spacer(1, 10))
                
                user_data = [['Username', 'Total', 'Collected', 'Rate']]
                for user_stat in user_stats[:20]:  # Top 20 users
                    username = user_stat['_id']
                    total = user_stat['total']
                    collected = user_stat['collected']
                    rate = round((collected / total * 100), 1) if total > 0 else 0
                    user_data.append([username, str(total), str(collected), f'{rate}%'])
                
                user_table = Table(user_data, colWidths=[150, 100, 100, 100])
                user_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#E8F5E8')),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#4CAF50'))
                ]))
                
                story.append(user_table)
                story.append(Spacer(1, 20))
            
            # Waste type breakdown
            if monthly_waste_stats:
                story.append(Paragraph("Waste Type Breakdown", styles['Heading2']))
                story.append(Spacer(1, 10))
                
                waste_data = [['Waste Type', 'Count', 'Percentage']]
                for waste_type, count in monthly_waste_stats.items():
                    percentage = round((count / monthly_total * 100), 1)
                    waste_data.append([waste_type, str(count), f'{percentage}%'])
                
                waste_table = Table(waste_data, colWidths=[200, 125, 125])
                waste_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 11),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#E8F5E8')),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#4CAF50'))
                ]))
                
                story.append(waste_table)
            
            doc.build(story)
            buffer.seek(0)
            
            filename = f'overall-report-{first_day.strftime("%Y-%m")}.pdf'
            return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')
            
        except Exception as e:
            print(f"Error generating overall report: {str(e)}")
            return jsonify({"error": str(e)}), 500

    # ================= ADMIN - CHECK DATA AVAILABILITY =================
    @app.route('/admin/check-data-availability')
    def check_data_availability():
        """Admin-only: Check what data is available in the system"""
        if 'user' not in session or session.get('role') != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        
        try:
            # Get all users with waste records
            users_with_data = mongo.db.waste_records.aggregate([
                {
                    "$group": {
                        "_id": "$uploaded_by",
                        "count": {"$sum": 1},
                        "first_upload": {"$min": "$timestamp"},
                        "last_upload": {"$max": "$timestamp"}
                    }
                },
                {"$sort": {"count": -1}}
            ])
            
            users_list = []
            for user in users_with_data:
                users_list.append({
                    "username": user["_id"],
                    "total_uploads": user["count"],
                    "first_upload": user["first_upload"].strftime("%Y-%m-%d") if user["first_upload"] else "N/A",
                    "last_upload": user["last_upload"].strftime("%Y-%m-%d") if user["last_upload"] else "N/A"
                })
            
            # Get months with data
            months_with_data = mongo.db.waste_records.aggregate([
                {
                    "$group": {
                        "_id": {
                            "year": {"$year": "$timestamp"},
                            "month": {"$month": "$timestamp"}
                        },
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"_id.year": -1, "_id.month": -1}}
            ])
            
            months_list = []
            for month_data in months_with_data:
                year = month_data["_id"]["year"]
                month = month_data["_id"]["month"]
                month_name = calendar.month_name[month]
                months_list.append({
                    "period": f"{month_name} {year}",
                    "year": year,
                    "month": month,
                    "count": month_data["count"]
                })
            
            # Get detailed user-month breakdown
            user_month_data = mongo.db.waste_records.aggregate([
                {
                    "$group": {
                        "_id": {
                            "user": "$uploaded_by",
                            "year": {"$year": "$timestamp"},
                            "month": {"$month": "$timestamp"}
                        },
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"_id.user": 1, "_id.year": -1, "_id.month": -1}}
            ])
            
            user_month_breakdown = []
            for item in user_month_data:
                year = item["_id"]["year"]
                month = item["_id"]["month"]
                month_name = calendar.month_name[month]
                user_month_breakdown.append({
                    "username": item["_id"]["user"],
                    "period": f"{month_name} {year}",
                    "year": year,
                    "month": month,
                    "count": item["count"]
                })
            
            return jsonify({
                "users_with_data": users_list,
                "months_with_data": months_list,
                "user_month_breakdown": user_month_breakdown,
                "total_users": len(users_list),
                "total_months": len(months_list)
            })
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ================= WORKER MANAGEMENT =================
    @app.route('/admin/workers')
    def admin_workers():
        if 'user' not in session or session.get('role') != 'admin':
            return redirect(url_for('login'))

        workers = list(mongo.db.workers.find().sort("name", 1))
        assignments = list(mongo.db.worker_assignments.find().sort("assigned_at", -1).limit(100))
        bins = list(mongo.db.bins.find({}, {"bin_id": 1, "area_name": 1, "location": 1}).sort("bin_id", 1))

        # Performance per worker
        performance = []
        for w in workers:
            total     = mongo.db.worker_assignments.count_documents({"worker_id": str(w["_id"])})
            completed = mongo.db.worker_assignments.count_documents({"worker_id": str(w["_id"]), "status": "Done"})
            pending   = total - completed
            rate      = round((completed / total * 100)) if total > 0 else 0
            performance.append({
                "name": w["name"], "worker_id": w.get("worker_id", ""),
                "zone": w.get("zone", ""), "total": total,
                "completed": completed, "pending": pending, "rate": rate
            })

        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        stats = {
            "total":           mongo.db.workers.count_documents({}),
            "active":          mongo.db.workers.count_documents({"status": "Active"}),
            "on_leave":        mongo.db.workers.count_documents({"status": "On Leave"}),
            "assigned_today":  mongo.db.worker_assignments.count_documents({"assigned_at": {"$gte": today_start}}),
            "completed_today": mongo.db.worker_assignments.count_documents({"status": "Done", "completed_at": {"$gte": today_start}}),
        }

        return render_template('admin/workers.html',
                               workers=workers, assignments=assignments,
                               bins=bins, performance=performance, stats=stats)

    @app.route('/admin/workers/add', methods=['POST'])
    def add_worker():
        if 'user' not in session or session.get('role') != 'admin':
            return redirect(url_for('login'))

        # Auto-generate worker ID
        count = mongo.db.workers.count_documents({})
        worker_id = f"WRK{count + 1:03d}"

        mongo.db.workers.insert_one({
            "worker_id":   worker_id,
            "name":        request.form.get('name', '').strip(),
            "phone":       request.form.get('phone', '').strip(),
            "zone":        request.form.get('zone', '').strip(),
            "shift":       request.form.get('shift', 'Morning'),
            "status":      request.form.get('status', 'Active'),
            "notes":       request.form.get('notes', '').strip(),
            "joined_date": datetime.now()
        })
        return redirect(url_for('admin_workers'))

    @app.route('/admin/workers/<worker_id>/edit', methods=['POST'])
    def edit_worker(worker_id):
        if 'user' not in session or session.get('role') != 'admin':
            return redirect(url_for('login'))

        mongo.db.workers.update_one(
            {"_id": ObjectId(worker_id)},
            {"$set": {
                "name":   request.form.get('name', '').strip(),
                "phone":  request.form.get('phone', '').strip(),
                "zone":   request.form.get('zone', '').strip(),
                "shift":  request.form.get('shift', 'Morning'),
                "status": request.form.get('status', 'Active'),
            }}
        )
        return redirect(url_for('admin_workers'))

    @app.route('/admin/workers/<worker_id>/delete', methods=['POST'])
    def delete_worker(worker_id):
        if 'user' not in session or session.get('role') != 'admin':
            return jsonify({"error": "Unauthorized"}), 403
        try:
            mongo.db.workers.delete_one({"_id": ObjectId(worker_id)})
            mongo.db.worker_assignments.delete_many({"worker_id": worker_id})
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/admin/workers/<worker_id>/assign', methods=['POST'])
    def assign_worker_task(worker_id):
        if 'user' not in session or session.get('role') != 'admin':
            return redirect(url_for('login'))

        worker = mongo.db.workers.find_one({"_id": ObjectId(worker_id)})
        if not worker:
            return redirect(url_for('admin_workers'))

        bin_id   = request.form.get('bin_id', '').strip()
        due_date = request.form.get('due_date', '')
        notes    = request.form.get('notes', '').strip()

        due_dt = None
        if due_date:
            try:
                due_dt = datetime.strptime(due_date, '%Y-%m-%d')
            except:
                pass

        # Get bin zone
        bin_doc = mongo.db.bins.find_one({"bin_id": bin_id})
        zone = bin_doc.get('area_name') or bin_doc.get('location', '') if bin_doc else worker.get('zone', '')

        mongo.db.worker_assignments.insert_one({
            "worker_id":   str(worker["_id"]),
            "worker_name": worker["name"],
            "bin_id":      bin_id,
            "zone":        zone,
            "status":      "Assigned",
            "notes":       notes,
            "due_date":    due_dt,
            "assigned_at": datetime.now(),
            "completed_at": None
        })

        # Update pickup status if a pending pickup exists for this bin
        mongo.db.pickups.update_many(
            {"bin_id": bin_id, "status": "pending"},
            {"$set": {"status": "approved", "assigned_worker": worker["name"], "approved_at": datetime.now()}}
        )

        return redirect(url_for('admin_workers'))

    @app.route('/admin/assignments/<assignment_id>/status', methods=['POST'])
    def update_assignment_status(assignment_id):
        if 'user' not in session or session.get('role') != 'admin':
            return redirect(url_for('login'))

        new_status = request.form.get('status', 'In Progress')
        update = {"status": new_status}
        if new_status == 'Done':
            update["completed_at"] = datetime.now()
            # Mark related pickup as collected
            assignment = mongo.db.worker_assignments.find_one({"_id": ObjectId(assignment_id)})
            if assignment:
                mongo.db.pickups.update_many(
                    {"bin_id": assignment["bin_id"], "status": "approved"},
                    {"$set": {"status": "collected", "collected_at": datetime.now(),
                              "collected_by": assignment["worker_name"]}}
                )
                # Update waste records status
                mongo.db.waste_records.update_many(
                    {"bin_id": assignment["bin_id"], "status": "In Transit"},
                    {"$set": {"status": "Collected"}}
                )

        mongo.db.worker_assignments.update_one(
            {"_id": ObjectId(assignment_id)},
            {"$set": update}
        )
        return redirect(url_for('admin_workers') + '#assignments')

    # ================= COMPLAINTS =================
    @app.route('/complaint', methods=['GET', 'POST'])
    def submit_complaint():
        if 'user' not in session or session.get('role') == 'admin':
            return redirect(url_for('login'))
        
        success = error = None
        if request.method == 'POST':
            category    = request.form.get('category', '').strip()
            subject     = request.form.get('subject', '').strip()
            description = request.form.get('description', '').strip()
            
            if not all([category, subject, description]):
                error = "All fields are required."
            else:
                mongo.db.complaints.insert_one({
                    "username":    session.get('username', session['user']),
                    "user_email":  session['user'],
                    "category":    category,
                    "subject":     subject,
                    "description": description,
                    "status":      "Pending",
                    "admin_reply": None,
                    "admin_read":  False,
                    "replied_at":  None,
                    "timestamp":   datetime.now()
                })
                # Notify admin
                create_notification(
                    notification_type="complaint_new",
                    title="New Complaint Received",
                    message=f"{session.get('username', session['user'])} submitted a complaint: \"{subject}\"",
                    recipient="admin",
                    icon="exclamation",
                    severity="warning"
                )
                success = "Your complaint has been submitted. We'll get back to you soon."
        
        return render_template('complaints/submit.html', success=success, error=error)

    @app.route('/my-complaints')
    def my_complaints():
        if 'user' not in session or session.get('role') == 'admin':
            return redirect(url_for('login'))
        
        complaints = list(mongo.db.complaints.find(
            {"user_email": session['user']}
        ).sort("timestamp", -1))
        
        return render_template('complaints/my_complaints.html', complaints=complaints)

    @app.route('/admin/complaints')
    def admin_complaints():
        if 'user' not in session or session.get('role') != 'admin':
            return redirect(url_for('login'))
        
        status_filter = request.args.get('status')
        query = {"status": status_filter} if status_filter else {}
        
        complaints = list(mongo.db.complaints.find(query).sort("timestamp", -1))
        
        # Mark all as admin-read when admin opens the page
        mongo.db.complaints.update_many({"admin_read": False}, {"$set": {"admin_read": True}})
        
        stats = {
            "total":     mongo.db.complaints.count_documents({}),
            "pending":   mongo.db.complaints.count_documents({"status": "Pending"}),
            "reviewing": mongo.db.complaints.count_documents({"status": "Reviewing"}),
            "resolved":  mongo.db.complaints.count_documents({"status": "Resolved"}),
        }
        
        return render_template('admin/complaints.html',
                               complaints=complaints,
                               stats=stats,
                               current_filter=status_filter)

    @app.route('/admin/complaints/<complaint_id>/reply', methods=['POST'])
    def admin_reply_complaint(complaint_id):
        if 'user' not in session or session.get('role') != 'admin':
            return redirect(url_for('login'))
        
        reply  = request.form.get('reply', '').strip()
        status = request.form.get('status', 'Reviewing')
        
        if not reply:
            return redirect(url_for('admin_complaints'))
        
        complaint = mongo.db.complaints.find_one({"_id": ObjectId(complaint_id)})
        if not complaint:
            return redirect(url_for('admin_complaints'))
        
        mongo.db.complaints.update_one(
            {"_id": ObjectId(complaint_id)},
            {"$set": {
                "admin_reply": reply,
                "status":      status,
                "replied_at":  datetime.now()
            }}
        )
        
        # Notify the user
        status_icons = {"Pending": "⏳", "Reviewing": "🔍", "Resolved": "✅", "Closed": "🔒"}
        create_notification(
            notification_type="complaint_reply",
            title=f"Complaint {status}: {complaint['subject']}",
            message=f"Admin replied to your complaint: \"{reply[:100]}{'...' if len(reply) > 100 else ''}\"",
            recipient=complaint.get('username', complaint.get('user_email')),
            icon="check",
            severity="success" if status == "Resolved" else "info"
        )
        
        return redirect(url_for('admin_complaints'))

    # ================= USER HISTORY =================
    @app.route('/history')
    def user_history():
        if 'user' not in session:
            return redirect(url_for('login'))
        
        # Get user's uploads
        records = list(
            mongo.db.waste_records.find(
                {"uploaded_by": session['user']}
            ).sort([("timestamp", -1)])
        )
        
        return render_template('user/history.html', records=records)

    # ================= ACTIVITY LOGS (USER VIEW) =================
    @app.route('/my-activity')
    def my_activity():
        if 'user' not in session:
            return redirect(url_for('login'))
        
        logs = list(
            mongo.db.activity_logs.find(
                {"username": session.get('username', session['user'])}
            ).sort([("timestamp", -1)]).limit(50)
        )
        
        return render_template('user/activity.html', logs=logs)

    # ================= PICKUPS - CREATE/CLAIM =================
    def _ensure_system_pickup_for_bin(bin_id):
        """
        Ensure there is a pending pickup request for the given bin.
        Used by auto "bin full" alerts so that admins see the bin under Pending Pickups.
        """
        if not bin_id:
            return

        existing = mongo.db.pickups.find_one({
            "bin_id": bin_id,
            "status": "pending"
        })
        if existing:
            return

        mongo.db.pickups.insert_one({
            "bin_id": bin_id,
            "requested_by": "system",
            "requested_by_username": "System Auto Alert",
            "status": "pending",
            "created_at": datetime.now(),
            "approved_at": None,
            "approved_by": None
        })

    @app.route('/request-pickup', methods=['POST'])
    def request_pickup():
        if 'user' not in session:
            return redirect(url_for('login'))
        
        bin_id = normalize_bin_id(request.form.get('bin_id'))
        bin_data = mongo.db.bins.find_one({"bin_id": bin_id})
        
        if not bin_data:
            return jsonify({"error": "Bin not found"}), 404
        
        # Create pickup request
        pickup = mongo.db.pickups.insert_one({
            "bin_id": bin_id,
            "requested_by": session['user'],
            "requested_by_username": session.get('username', session['user']),
            "status": "pending",
            "created_at": datetime.now(),
            "approved_at": None,
            "approved_by": None
        })
        
        log_activity(
            session.get('username', session['user']),
            'Request Pickup',
            f'Requested pickup for bin {bin_id}'
        )
        
        return jsonify({"message": "Pickup requested", "pickup_id": str(pickup.inserted_id)})

    # ================= ADMIN - PICKUPS MANAGEMENT =================
    @app.route('/admin/pickups')
    def admin_pickups():
        if 'user' not in session or session.get('role') != 'admin':
            return redirect(url_for('login'))

        pending = list(
            mongo.db.pickups.find({"status": "pending"})
            .sort([("created_at", -1)])
        )

        approved = list(
            mongo.db.pickups.find({"status": "approved"})
            .sort([("approved_at", -1)])
        )

        for p in pending + approved:
            bin_id = p.get('bin_id')
            p['items'] = list(
                mongo.db.waste_records.find({"bin_id": bin_id})
                .sort([("timestamp", -1)])
                .limit(5)
            )

        bins = list(
            mongo.db.bins.find({}, {"_id": 0, "bin_id": 1, "area_name": 1})
            .sort("bin_id", 1)
        )

        # Fetch all users for notification recipient selection
        users = list(
            mongo.db.users.find(
                {"role": {"$ne": "admin"}},  # Exclude admin users
                {"_id": 0, "username": 1, "email": 1}
            ).sort("username", 1)
        )

        return render_template(
            'admin/pickups.html',
            pending=pending,
            approved=approved,
            bins=bins,
            users=users
        )

    # ================= ADMIN - APPROVE PICKUP =================
    @app.route('/admin/approve-pickup/<pickup_id>', methods=['POST'])
    def approve_pickup(pickup_id):
        if 'user' not in session or session.get('role') != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        
        try:
            pickup_obj_id = ObjectId(pickup_id)
        except:
            return jsonify({"error": "Invalid pickup ID"}), 400
        
        pickup = mongo.db.pickups.find_one({"_id": pickup_obj_id})
        if not pickup:
            return jsonify({"error": "Pickup not found"}), 404
        
        result = mongo.db.pickups.update_one(
            {"_id": pickup_obj_id},
            {
                "$set": {
                    "status": "approved",
                    "approved_at": datetime.now(),
                    "approved_by": session['user']
                }
            }
        )
        
        if result.matched_count == 0:
            return jsonify({"error": "Pickup not found"}), 404
        
        # Create notification for pickup completion
        create_notification(
            notification_type="pickup_completed",
            title="Pickup Approved",
            message=f"Your pickup request for bin {pickup.get('bin_id')} has been approved and will be collected soon.",
            recipient=pickup.get('requested_by_username'),
            icon="truck",
            severity="success"
        )
        
        log_activity(
            session.get('username', session['user']),
            'Approve Pickup',
            f'Approved pickup request {pickup_id}'
        )
        
        return jsonify({"message": "Pickup approved"})

    # ================= ADMIN - REJECT PICKUP =================
    @app.route('/admin/reject-pickup/<pickup_id>', methods=['POST'])
    def reject_pickup(pickup_id):
        if 'user' not in session or session.get('role') != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        
        try:
            pickup_obj_id = ObjectId(pickup_id)
        except:
            return jsonify({"error": "Invalid pickup ID"}), 400
        
        pickup = mongo.db.pickups.find_one({"_id": pickup_obj_id})
        if not pickup:
            return jsonify({"error": "Pickup not found"}), 404
        
        result = mongo.db.pickups.update_one(
            {"_id": pickup_obj_id},
            {
                "$set": {
                    "status": "rejected",
                    "rejected_at": datetime.now(),
                    "rejected_by": session['user']
                }
            }
        )
        
        if result.matched_count == 0:
            return jsonify({"error": "Pickup not found"}), 404
        
        # Create notification for pickup rejection
        recipient_username = pickup.get('requested_by_username')
        print(f"DEBUG: Creating rejection notification for recipient: {recipient_username}")
        print(f"DEBUG: Pickup details: {pickup}")
        
        create_notification(
            notification_type="pickup_rejected",
            title="Pickup Request Rejected",
            message=f"Your pickup request for bin {pickup.get('bin_id')} has been rejected. Please contact admin for details.",
            recipient=recipient_username,
            icon="x-circle",
            severity="warning"
        )
        
        print(f"DEBUG: Rejection notification created successfully")
        
        log_activity(
            session.get('username', session['user']),
            'Reject Pickup',
            f'Rejected pickup request {pickup_id}'
        )
        
        return jsonify({"message": "Pickup rejected"})

    # ================= ADMIN - COMPLETE PICKUP (BIN EMPTIED) =================
    @app.route('/admin/complete-pickup/<pickup_id>', methods=['POST'])
    def complete_pickup(pickup_id):
        """Mark a pickup as completed and update related waste records."""
        if 'user' not in session or session.get('role') != 'admin':
            return jsonify({"error": "Admin access required"}), 403

        try:
            pickup_obj_id = ObjectId(pickup_id)
        except Exception:
            return jsonify({"error": "Invalid pickup ID"}), 400

        pickup = mongo.db.pickups.find_one({"_id": pickup_obj_id})
        if not pickup:
            return jsonify({"error": "Pickup not found"}), 404

        # Update pickup document
        result = mongo.db.pickups.update_one(
            {"_id": pickup_obj_id},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": datetime.now(),
                    "completed_by": session['user']
                }
            }
        )

        if result.matched_count == 0:
            return jsonify({"error": "Pickup not found"}), 404

        bin_id = pickup.get('bin_id')

        # Mark related waste records as Collected for that bin
        if bin_id:
            mongo.db.waste_records.update_many(
                {"bin_id": bin_id},
                {"$set": {"status": "Collected"}}
            )

        # Notify users about pickup completion
        # For system-generated pickups, send to all users
        if pickup.get('requested_by') == 'system':
            create_notification(
                notification_type="pickup_completed",
                title="Pickup Completed",
                message=f"Bin {bin_id} has been collected and emptied.",
                recipient=None,  # Send to all users
                icon="check-circle",
                severity="success"
            )
        else:
            # For user-requested pickups, send to specific user
            create_notification(
                notification_type="pickup_completed",
                title="Pickup Completed",
                message=f"Your pickup request for bin {bin_id} has been completed and the bin has been emptied.",
                recipient=pickup.get('requested_by_username'),
                icon="check-circle",
                severity="success"
            )

        log_activity(
            session.get('username', session['user']),
            'Complete Pickup',
            f'Completed pickup request {pickup_id} for bin {bin_id}'
        )

        return jsonify({"message": "Pickup completed"})

    # ================= ADMIN - SEND CUSTOM NOTIFICATION TO USER =================
    @app.route('/admin/send-notification', methods=['POST'])
    def send_custom_notification():
        """Send a custom notification to a specific user"""
        if 'user' not in session or session.get('role') != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        
        try:
            data = request.get_json()
            recipient = data.get('recipient')
            title = data.get('title')
            message = data.get('message')
            notification_type = data.get('notification_type', 'custom')
            severity = data.get('severity', 'info')
            
            # Validation
            if not recipient or not title or not message:
                return jsonify({"error": "Recipient, title, and message are required"}), 400
            
            # Verify recipient exists
            user = mongo.db.users.find_one({"username": recipient})
            if not user:
                return jsonify({"error": f"User '{recipient}' not found"}), 404
            
            # Create notification
            create_notification(
                notification_type=notification_type,
                title=title,
                message=message,
                recipient=recipient,
                icon="envelope",
                severity=severity
            )
            
            # Log activity
            log_activity(
                session.get('username', session['user']),
                'Send Custom Notification',
                f'Sent notification to {recipient}: {title}'
            )
            
            return jsonify({
                "message": f"Notification sent successfully to {recipient}",
                "recipient": recipient,
                "title": title
            })
            
        except Exception as e:
            print(f"Error sending custom notification: {str(e)}")
            return jsonify({"error": str(e)}), 500

    # ================= ADMIN - ACTIVITY LOGS =================
    @app.route('/admin/activity-logs')
    def admin_activity_logs():
        if 'user' not in session or session.get('role') != 'admin':
            return redirect(url_for('login'))
        
        logs = list(
            mongo.db.activity_logs.find().sort([("timestamp", -1)]).limit(100)
        )
        
        return render_template('admin/activity.html', logs=logs)

    # ================= NOTIFICATIONS ROUTES =================
    @app.route('/api/notifications')
    def get_user_notifications():
        """Get all notifications for current user"""
        if 'user' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        
        notifications = get_notifications(
            recipient=session.get('username', session['user']),
            limit=20
        )
        
        # Convert ObjectId to string for JSON serialization
        for notif in notifications:
            notif['_id'] = str(notif['_id'])
            notif['timestamp'] = notif['timestamp'].isoformat()
        
        return jsonify(notifications)

    @app.route('/api/notifications/<notification_id>/read', methods=['POST'])
    def mark_notification_read(notification_id):
        """Mark a notification as read and create pickup if bin full alert"""
        if 'user' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        
        try:
            notif_id = ObjectId(notification_id)
        except:
            return jsonify({"error": "Invalid notification ID"}), 400
        
        # Get notification details before marking as read
        notification = mongo.db.notifications.find_one({"_id": notif_id})
        
        result = mongo.db.notifications.update_one(
            {"_id": notif_id},
            {"$set": {"read": True}}
        )
        
        if result.matched_count == 0:
            return jsonify({"error": "Notification not found"}), 404
        
        # If this is a bin full notification, create pending pickup
        if notification and notification.get('type') == 'bin_full':
            # Extract bin_id from notification message
            message = notification.get('message', '')
            import re
            bin_match = re.search(r'Bin (\w+)', message)
            if bin_match:
                bin_id = bin_match.group(1)
                _ensure_system_pickup_for_bin(bin_id)
                log_activity(
                    session.get('username', session['user']),
                    'Allow Bin Full Alert',
                    f'Allowed bin full alert for bin {bin_id} - pickup created'
                )
        
        return jsonify({"message": "Notification marked as read"})

    @app.route('/api/notifications/read-all', methods=['POST'])
    def mark_all_notifications_read():
        """Mark all notifications as read for current user"""
        if 'user' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        # Only normal users (not admin) can mark all as read
        if session.get('role') == 'admin':
            return jsonify({"error": "Admins cannot bulk-mark notifications as read"}), 403
        
        username = session.get('username', session['user'])
        mongo.db.notifications.update_many(
            {"$or": [{"recipient": username}, {"recipient": None}], "read": False},
            {"$set": {"read": True}}
        )
        
        return jsonify({"message": "All notifications marked as read"})

    @app.route('/notifications')
    def notifications_page():
        """View all notifications"""
        if 'user' not in session:
            return redirect(url_for('login'))
        # Hide notifications page for admin accounts
        if session.get('role') == 'admin':
            return redirect(url_for('dashboard'))
        
        current_user = session.get('username', session['user'])
        print(f"DEBUG: Getting notifications for user: {current_user}")
        print(f"DEBUG: Session data: {session}")
        
        notifications = get_notifications(
            recipient=current_user,
            limit=50
        )
        
        print(f"DEBUG: Retrieved {len(notifications)} notifications for {current_user}")
        for notif in notifications:
            print(f"DEBUG: Notification - Type: {notif.get('type')}, Title: {notif.get('title')}, Recipient: {notif.get('recipient')}")
        
        return render_template('notifications.html', notifications=notifications)

    # ================= ADMIN - BIN FULL ALERT =================
    @app.route('/admin/alert-bin-full/<bin_id>', methods=['POST'])
    def alert_bin_full(bin_id):
        """Send a bin full alert to users"""
        if 'user' not in session or session.get('role') != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        
        # Get optional recipient from request
        data = request.get_json() or {}
        recipient = data.get('recipient', None)  # None means all users
        
        # Check if bin has at least 6 items in transit
        in_transit_count = mongo.db.waste_records.count_documents({
            "bin_id": bin_id,
            "status": "In Transit"
        })
        
        if in_transit_count < 6:
            return jsonify({
                "error": f"Bin {bin_id} only has {in_transit_count} items. Bin full alert requires at least 6 items in transit."
            }), 400
        
        # Verify recipient exists if specified
        if recipient and recipient != 'all':
            user = mongo.db.users.find_one({"username": recipient})
            if not user:
                return jsonify({"error": f"User '{recipient}' not found"}), 404
        
        # Set recipient to None if 'all' is selected
        if recipient == 'all':
            recipient = None
        
        create_notification(
            notification_type="bin_full",
            title="⚠️ Bin Full Alert",
            message=f"Bin {bin_id} is now full and requires immediate collection.",
            recipient=recipient,
            icon="exclamation-triangle",
            severity="warning"
        )
        
        # Ensure a pending pickup exists so this bin appears under Pending Pickups
        _ensure_system_pickup_for_bin(bin_id)
        
        recipient_text = f"to {recipient}" if recipient else "to all users"
        log_activity(
            session.get('username', session['user']),
            'Bin Full Alert',
            f'Sent bin full alert for bin {bin_id} {recipient_text} ({in_transit_count} items)'
        )
        
        return jsonify({"message": f"Bin full alert sent {recipient_text}"})

    # ================= ADMIN - SYSTEM ALERT =================
    @app.route('/admin/system-alert', methods=['POST'])
    def create_system_alert():
        """Create a system-wide alert"""
        if 'user' not in session or session.get('role') != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        
        data = request.get_json() or request.form
        title = data.get('title', 'System Alert')
        message = data.get('message', '')
        severity = data.get('severity', 'info')  # info, warning, danger
        recipient = data.get('recipient', None)  # None means all users
        
        # Verify recipient exists if specified
        if recipient and recipient != 'all':
            user = mongo.db.users.find_one({"username": recipient})
            if not user:
                return jsonify({"error": f"User '{recipient}' not found"}), 404
        
        # Set recipient to None if 'all' is selected
        if recipient == 'all':
            recipient = None
        
        create_notification(
            notification_type="system_alert",
            title=title,
            message=message,
            recipient=recipient,
            icon="info-circle",
            severity=severity
        )
        
        recipient_text = f"to {recipient}" if recipient else "to all users"
        log_activity(
            session.get('username', session['user']),
            'System Alert',
            f'Created system alert: {title} {recipient_text}'
        )
        
        return jsonify({"message": f"System alert sent {recipient_text}"})

    # ================= LOGOUT =================
    @app.route('/logout')
    def logout():
        if 'user' in session:
            log_activity(
                session.get('username', session['user']),
                'Logout',
                'User logged out'
            )
        session.clear()
        return redirect(url_for('login'))

    return app


if __name__ == "__main__":
    app = create_app()
    # Run on all network interfaces (0.0.0.0) to allow mobile access
    # Access from mobile: http://<your-computer-ip>:5000
    app.run(host='0.0.0.0', port=5000, debug=True)
