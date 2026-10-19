"""Collections, $jsonSchema validators and indexes."""
from pymongo import ASCENDING, DESCENDING, GEOSPHERE

STATION_VALIDATOR = {"$jsonSchema": {
    "bsonType": "object",
    "required": ["station_id", "name", "city", "state", "location", "status"],
    "properties": {
        "station_id": {"bsonType": "string", "pattern": "^WS[0-9]{3}$",
                       "description": "e.g. WS001"},
        "name": {"bsonType": "string", "minLength": 3},
        "city": {"bsonType": "string"},
        "state": {"bsonType": "string"},
        "elevation_m": {"bsonType": "number", "minimum": -100, "maximum": 9000},
        "status": {"enum": ["active", "inactive", "maintenance"]},
        "installed_on": {"bsonType": "date"},
        "sensors": {"bsonType": "array", "uniqueItems": True,
                    "items": {"enum": ["temperature", "humidity", "pressure",
                                       "wind", "rainfall"]}},
        "location": {                      # GeoJSON Point -> enables 2dsphere queries
            "bsonType": "object",
            "required": ["type", "coordinates"],
            "properties": {
                "type": {"enum": ["Point"]},
                "coordinates": {"bsonType": "array", "minItems": 2, "maxItems": 2,
                                "items": {"bsonType": "number"}},
            }},
    }}}

READING_VALIDATOR = {"$jsonSchema": {
    "bsonType": "object",
    "required": ["station_id", "timestamp", "temperature_c", "humidity_pct",
                 "pressure_hpa", "wind", "rainfall_mm", "condition"],
    "properties": {
        "station_id": {"bsonType": "string", "pattern": "^WS[0-9]{3}$"},
        "timestamp": {"bsonType": "date"},
        "temperature_c": {"bsonType": "number", "minimum": -60, "maximum": 60},
        "humidity_pct": {"bsonType": "number", "minimum": 0, "maximum": 100},
        "pressure_hpa": {"bsonType": "number", "minimum": 300, "maximum": 1100},
        "rainfall_mm": {"bsonType": "number", "minimum": 0},
        "condition": {"enum": ["clear", "cloudy", "rainy", "hot", "humid", "stormy"]},
        "wind": {                           # embedded sub-document
            "bsonType": "object",
            "required": ["speed_kmh", "direction_deg"],
            "properties": {
                "speed_kmh": {"bsonType": "number", "minimum": 0},
                "direction_deg": {"bsonType": "number", "minimum": 0, "maximum": 360},
            }},
    }}}

ALERT_VALIDATOR = {"$jsonSchema": {
    "bsonType": "object",
    "required": ["station_id", "type", "severity", "message", "triggered_at", "resolved"],
    "properties": {
        "station_id": {"bsonType": "string", "pattern": "^WS[0-9]{3}$"},
        "type": {"enum": ["heatwave", "cold_wave", "heavy_rain", "high_wind"]},
        "severity": {"enum": ["info", "warning", "critical"]},
        "message": {"bsonType": "string"},
        "triggered_at": {"bsonType": "date"},
        "resolved": {"bsonType": "bool"},
    }}}

VALIDATORS = {"stations": STATION_VALIDATOR,
              "readings": READING_VALIDATOR,
              "alerts": ALERT_VALIDATOR}


def setup_schema(db, drop=False):
    existing = db.list_collection_names()
    for name, validator in VALIDATORS.items():
        if drop and name in existing:
            db.drop_collection(name)
            existing.remove(name)
        if name in existing:               # update validator on existing collection
            db.command("collMod", name, validator=validator,
                       validationLevel="strict", validationAction="error")
        else:
            db.create_collection(name, validator=validator,
                                 validationLevel="strict", validationAction="error")

    db.stations.create_index("station_id", unique=True)
    db.stations.create_index([("location", GEOSPHERE)])
    db.stations.create_index([("state", ASCENDING), ("city", ASCENDING)])
    db.readings.create_index([("station_id", ASCENDING), ("timestamp", DESCENDING)])
    db.readings.create_index("timestamp")
    db.alerts.create_index([("station_id", ASCENDING), ("triggered_at", DESCENDING)])
    print("Collections, validators and indexes are ready:", list(VALIDATORS))
