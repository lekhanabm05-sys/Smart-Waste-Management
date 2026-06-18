# Bin ID Management & IoT Integration Guide

## 2.1 Bin ID Format & Management (Complete Feature)

### Standard Bin ID Format
- **Format**: `BIN-YYMMDD-NNNNN`
- **Example**: `BIN-260207-00001`, `BIN-260207-00002`
- **Components**:
  - `BIN`: Fixed prefix
  - `YYMMDD`: Year-Month-Day (creation date)
  - `NNNNN`: Sequential 5-digit counter (auto-incremented per day)

### Auto-Generate Bin IDs
Bins can now be created with automatically generated IDs using the auto-generation function:

```python
def generate_bin_id():
    """Auto-generate unique Bin ID with format BIN-YYMMDD-NNNNN"""
    # Gets date + increments counter for the day
```

### Creating Bins with Auto-Generated IDs

**Endpoint**: `POST /api/bin/create`
**Authentication**: Admin required
**Request Body**:
```json
{
  "area_name": "Downtown Plaza",
  "lat": 28.6139,
  "lng": 77.2090,
  "type": "Mixed",
  "capacity": 50
}
```

**Response**:
```json
{
  "message": "Bin created successfully",
  "bin": {
    "bin_id": "BIN-260207-00001",
    "area_name": "Downtown Plaza",
    "lat": 28.6139,
    "lng": 77.2090,
    "type": "Mixed",
    "capacity": 50,
    "status": "active",
    "created_at": "2026-02-07T10:30:00Z",
    "created_by": "admin",
    "sensor_enabled": false
  }
}
```

### MongoDB Collection Structure
```javascript
{
  bin_id: "BIN-260207-00001",        // Unique ID
  area_name: "Downtown Plaza",        // Location name
  lat: 28.6139,                      // Latitude
  lng: 77.2090,                      // Longitude
  type: "Mixed",                     // Bin type (Wet, Dry, Plastic, Metal, Mixed)
  capacity: 50,                      // Items capacity
  status: "active",                  // active | inactive | retired
  created_at: ISODate(),
  created_by: "admin",
  created_date: "260207",            // For quick date-based queries
  
  // IoT Sensor Fields
  sensor_enabled: false,
  sensor_type: "ultrasonic",         // ultrasonic | weight | rfid | null
  last_synced: ISODate(),
  fullness_percent: 75,              // From ultrasonic sensor
  weight_kg: 45.2,                   // From weight sensor
  last_collection: ISODate(),        // From RFID sensor
  collection_count: 12
}
```

---

## 2.3 IoT Sensor Integration

### Overview
The system supports integration with multiple types of IoT sensors for real-time bin monitoring:

1. **Ultrasonic Sensors**: Measure distance to detect fullness percentage
2. **Weight Sensors**: Measure total weight for accurate capacity tracking
3. **RFID Sensors**: Track bin movement, collection events, and history

### Sensor Sync Endpoint
**Endpoint**: `POST /api/bin/<bin_id>/sensor-sync`
**Authentication**: Optional (can be called by IoT devices via API key)

### Sensor Type: Ultrasonic (Distance-based)
**Purpose**: Measures fullness by calculating distance from top

**Request Body**:
```json
{
  "sensor_type": "ultrasonic",
  "fullness_percent": 75,
  "distance_cm": 12
}
```

**Workflow**:
1. Sensor detects distance to waste surface
2. Converts to fullness % based on bin height
3. If fullness > 85%, triggers auto-alert
4. Data stored in `fullness_percent` field

### Sensor Type: Weight (Weight-based)
**Purpose**: Accurate capacity tracking via weight measurement

**Request Body**:
```json
{
  "sensor_type": "weight",
  "weight_kg": 45.2,
  "max_weight_kg": 50
}
```

**Workflow**:
1. Sensor measures total weight
2. Calculates fullness as (weight / max_weight) * 100
3. Triggers alert if > 85% of max capacity
4. Data stored in `weight_kg` field

### Sensor Type: RFID (Collection Tracking)
**Purpose**: Track bin movement, collection events, and usage patterns

**Request Body**:
```json
{
  "sensor_type": "rfid",
  "last_collection": "2026-02-07T10:30:00Z",
  "vehicle_id": "TRUCK-001",
  "emptied_by": "John Doe"
}
```

**Workflow**:
1. RFID reader detects bin when vehicle arrives
2. Records collection event with timestamp
3. Increments `collection_count`
4. Logs vehicle & operator info
5. Resets fullness tracking after collection

---

## System Integration Flow

```
IoT Sensor Device
    ↓
POST /api/bin/{bin_id}/sensor-sync
    ↓
Validate bin_id
    ↓
Process sensor data
    ↓
Update MongoDB bins collection
    ↓
Check fullness > 85% ?
    ├─ YES → Create notification + activity log
    └─ NO → Silent update
    ↓
Return success response
```

---

## Example cURL Commands

### Create Bin with Auto-Generated ID
```bash
curl -X POST http://localhost:5000/api/bin/create \
  -H "Content-Type: application/json" \
  -d '{
    "area_name": "Central Park",
    "lat": 28.6126,
    "lng": 77.2000,
    "type": "Wet",
    "capacity": 50
  }'
```

### Sync Ultrasonic Sensor Data
```bash
curl -X POST http://localhost:5000/api/bin/BIN-260207-00001/sensor-sync \
  -H "Content-Type: application/json" \
  -d '{
    "sensor_type": "ultrasonic",
    "fullness_percent": 87
  }'
```

### Sync Weight Sensor Data
```bash
curl -X POST http://localhost:5000/api/bin/BIN-260207-00001/sensor-sync \
  -H "Content-Type: application/json" \
  -d '{
    "sensor_type": "weight",
    "weight_kg": 48
  }'
```

### Sync RFID Collection Event
```bash
curl -X POST http://localhost:5000/api/bin/BIN-260207-00001/sensor-sync \
  -H "Content-Type: application/json" \
  -d '{
    "sensor_type": "rfid",
    "last_collection": "2026-02-07T14:30:00Z"
  }'
```

---

## Database Indexes for Performance
```javascript
db.bins.createIndex({ "bin_id": 1 }, { unique: true })
db.bins.createIndex({ "area_name": 1 })
db.bins.createIndex({ "created_date": 1 })
db.bins.createIndex({ "sensor_enabled": 1 })
db.bins.createIndex({ "fullness_percent": -1 })
db.bins.createIndex({ "last_synced": -1 })
```

---

## Feature Status

✅ **Completed**:
- Standard Bin ID format (BIN-YYMMDD-NNNNN)
- Auto-generate Bin IDs with `/api/bin/create`
- Connect to MongoDB bins collection
- IoT sensor endpoints (ultrasonic, weight, RFID)
- Auto-alerts when bins exceed 85% capacity
- Sensor data persistence and logging
- Activity tracking for bin creation and sensor syncs

---

## Next Steps (Optional Enhancements)

1. **IoT Device Registration**: Create `/api/iot/register` for device authentication
2. **Sensor Calibration**: Allow per-bin sensor offset configuration
3. **Predictive Maintenance**: Estimate collection times based on fill rate
4. **Historical Analytics**: Query sensor data trends over time
5. **Mobile IoT App**: React Native app for field technicians to sync sensors manually

