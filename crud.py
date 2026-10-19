"""CRUD operations (PyMongo)."""
from datetime import timedelta
from config import utcnow


# ---------- CREATE ----------
def create_station(db, station):
    return db.stations.insert_one(station).inserted_id

def add_reading(db, reading):
    return db.readings.insert_one(reading).inserted_id

def add_readings(db, readings):
    return db.readings.insert_many(readings).inserted_ids


# ---------- READ ----------
def get_station(db, station_id):
    return db.stations.find_one({"station_id": station_id}, {"_id": 0})

def list_stations_by_state(db, state):
    return list(db.stations.find({"state": state}, {"_id": 0, "station_id": 1, "city": 1, "status": 1}))

def latest_reading(db, station_id):
    return db.readings.find_one({"station_id": station_id}, {"_id": 0},
                                sort=[("timestamp", -1)])

def readings_in_range(db, station_id, start, end, limit=10):
    q = {"station_id": station_id, "timestamp": {"$gte": start, "$lt": end}}
    return list(db.readings.find(q, {"_id": 0}).sort("timestamp", -1).limit(limit))

def hot_and_humid(db, temp=35, humidity=60, limit=5):
    q = {"temperature_c": {"$gte": temp}, "humidity_pct": {"$gte": humidity}}
    return list(db.readings.find(q, {"_id": 0, "station_id": 1, "timestamp": 1,
                                     "temperature_c": 1, "humidity_pct": 1})
                .sort("temperature_c", -1).limit(limit))

def stations_near(db, lon, lat, max_km=500):
    """Geospatial query using the 2dsphere index."""
    q = {"location": {"$near": {"$geometry": {"type": "Point", "coordinates": [lon, lat]},
                                "$maxDistance": max_km * 1000}}}
    return [s["city"] for s in db.stations.find(q, {"city": 1})]


# ---------- UPDATE ----------
def set_station_status(db, station_id, status):
    return db.stations.update_one({"station_id": station_id},
                                  {"$set": {"status": status}}).modified_count

def add_sensor(db, station_id, sensor):
    return db.stations.update_one({"station_id": station_id},
                                  {"$addToSet": {"sensors": sensor}}).modified_count

def set_state_status(db, state, status):
    return db.stations.update_many({"state": state},
                                   {"$set": {"status": status}}).modified_count

def correct_reading(db, station_id, timestamp, new_temp):
    return db.readings.update_one({"station_id": station_id, "timestamp": timestamp},
                                  {"$set": {"temperature_c": new_temp}}).modified_count

def resolve_alerts(db, station_id):
    return db.alerts.update_many({"station_id": station_id, "resolved": False},
                                 {"$set": {"resolved": True}}).modified_count


# ---------- DELETE ----------
def delete_station(db, station_id):
    return db.stations.delete_one({"station_id": station_id}).deleted_count

def delete_old_readings(db, days):
    cutoff = utcnow() - timedelta(days=days)
    return db.readings.delete_many({"timestamp": {"$lt": cutoff}}).deleted_count
