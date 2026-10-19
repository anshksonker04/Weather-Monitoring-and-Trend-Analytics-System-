"""Generates realistic synthetic weather data (30 days, every 6 hours, 8 stations)."""
import math
import random
from datetime import timedelta
from config import utcnow

# id, name, city, state, lon, lat, elevation, base temp, daily swing
STATIONS = [
    ("WS001", "Delhi Central Observatory", "Delhi", "Delhi", 77.2090, 28.6139, 216, 28, 8),
    ("WS002", "Mumbai Coastal Station", "Mumbai", "Maharashtra", 72.8777, 19.0760, 14, 29, 3),
    ("WS003", "Chennai Marina Station", "Chennai", "Tamil Nadu", 80.2707, 13.0827, 6, 31, 4),
    ("WS004", "Kolkata Delta Station", "Kolkata", "West Bengal", 88.3639, 22.5726, 9, 29, 5),
    ("WS005", "Bengaluru Plateau Station", "Bengaluru", "Karnataka", 77.5946, 12.9716, 920, 25, 4),
    ("WS006", "Jaipur Desert Edge Station", "Jaipur", "Rajasthan", 75.7873, 26.9124, 431, 30, 8),
    ("WS007", "Shimla Hill Station", "Shimla", "Himachal Pradesh", 77.1734, 31.1048, 2276, 15, 6),
    ("WS008", "Hyderabad Deccan Station", "Hyderabad", "Telangana", 78.4867, 17.3850, 542, 28, 6),
]


def build_stations():
    now = utcnow()
    return [{
        "station_id": sid, "name": name, "city": city, "state": state,
        "location": {"type": "Point", "coordinates": [lon, lat]},
        "elevation_m": elev, "status": "active",
        "installed_on": now - timedelta(days=random.randint(400, 2000)),
        "sensors": ["temperature", "humidity", "pressure", "wind", "rainfall"],
    } for sid, name, city, state, lon, lat, elev, _, _ in STATIONS]


def _condition(temp, hum, rain, wind):
    if rain > 20 and wind > 25: return "stormy"
    if rain > 0:                return "rainy"
    if temp >= 38:              return "hot"
    if hum > 85:                return "humid"
    return random.choice(["clear", "clear", "cloudy"])


def build_readings(days=30, step_hours=6):
    random.seed(42)                         # reproducible demo data
    now = utcnow()
    start = now.replace(hour=0, minute=0, second=0) - timedelta(days=days)
    docs = []
    for sid, _, _, _, _, _, elev, base, amp in STATIONS:
        t = start
        while t <= now:
            temp = base + amp * math.sin(2 * math.pi * (t.hour - 9) / 24) + random.gauss(0, 1.5)
            if random.random() < 0.03:      # occasional heat spike
                temp += 6
            hum = min(100, max(15, 90 - (temp - 20) * 1.8 + random.gauss(0, 5)))
            rain = round(random.expovariate(1 / 8), 1) if random.random() < 0.15 else 0.0
            wind = abs(random.gauss(12, 6))
            docs.append({
                "station_id": sid, "timestamp": t,
                "temperature_c": round(temp, 1), "humidity_pct": round(hum, 1),
                "pressure_hpa": round(1013 - elev * 0.11 + random.gauss(0, 3), 1),
                "wind": {"speed_kmh": round(wind, 1),
                         "direction_deg": random.randint(0, 360)},
                "rainfall_mm": rain,
                "condition": _condition(temp, hum, rain, wind),
            })
            t += timedelta(hours=step_hours)

    # hand-made extremes so the alert pipeline always has something to find
    t = now - timedelta(days=2)
    extremes = [("WS006", 44.6, 14.0, 0.0, 18.0, "hot"),
                ("WS007", 1.4, 70.0, 0.0, 9.0, "clear"),
                ("WS003", 27.0, 96.0, 65.0, 72.0, "stormy")]
    for sid, temp, hum, rain, wind, cond in extremes:
        docs.append({"station_id": sid, "timestamp": t, "temperature_c": temp,
                     "humidity_pct": hum, "pressure_hpa": 1000.0,
                     "wind": {"speed_kmh": wind, "direction_deg": 180},
                     "rainfall_mm": rain, "condition": cond})
    return docs


def seed(db):
    db.stations.delete_many({}); db.readings.delete_many({}); db.alerts.delete_many({})
    db.stations.insert_many(build_stations())
    db.readings.insert_many(build_readings())
    print(f"Seeded {db.stations.count_documents({})} stations and "
          f"{db.readings.count_documents({})} readings.")
