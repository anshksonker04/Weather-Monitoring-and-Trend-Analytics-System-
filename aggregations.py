"""Aggregation pipelines. Each function returns a list of result documents."""
from datetime import timedelta
from config import utcnow


def _since(days):
    return utcnow() - timedelta(days=days)


# 1. Daily min/avg/max temperature + rainfall for one station
def daily_summary(db, station_id, days=7):
    return list(db.readings.aggregate([
        {"$match": {"station_id": station_id, "timestamp": {"$gte": _since(days)}}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                    "avg_temp": {"$avg": "$temperature_c"},
                    "min_temp": {"$min": "$temperature_c"},
                    "max_temp": {"$max": "$temperature_c"},
                    "total_rain_mm": {"$sum": "$rainfall_mm"}}},
        {"$project": {"_id": 0, "date": "$_id", "min_temp": 1, "max_temp": 1,
                      "avg_temp": {"$round": ["$avg_temp", 1]},
                      "total_rain_mm": {"$round": ["$total_rain_mm", 1]}}},
        {"$sort": {"date": 1}},
    ]))


# 2. Station leaderboard with $lookup (join readings -> stations)
def station_leaderboard(db, days=30):
    return list(db.readings.aggregate([
        {"$match": {"timestamp": {"$gte": _since(days)}}},
        {"$group": {"_id": "$station_id",
                    "avg_temp": {"$avg": "$temperature_c"},
                    "max_temp": {"$max": "$temperature_c"},
                    "avg_humidity": {"$avg": "$humidity_pct"},
                    "total_rain_mm": {"$sum": "$rainfall_mm"},
                    "readings": {"$sum": 1}}},
        {"$lookup": {"from": "stations", "localField": "_id",
                     "foreignField": "station_id", "as": "station"}},
        {"$unwind": "$station"},
        {"$project": {"_id": 0, "station_id": "$_id", "city": "$station.city",
                      "readings": 1, "max_temp": 1,
                      "avg_temp": {"$round": ["$avg_temp", 1]},
                      "avg_humidity": {"$round": ["$avg_humidity", 1]},
                      "total_rain_mm": {"$round": ["$total_rain_mm", 1]}}},
        {"$sort": {"avg_temp": -1}},
    ]))


# 3. State-level climate report ($lookup + $group on joined field)
def state_climate_report(db, days=30):
    return list(db.readings.aggregate([
        {"$match": {"timestamp": {"$gte": _since(days)}}},
        {"$lookup": {"from": "stations", "localField": "station_id",
                     "foreignField": "station_id", "as": "st"}},
        {"$unwind": "$st"},
        {"$group": {"_id": "$st.state",
                    "avg_temp": {"$avg": "$temperature_c"},
                    "total_rain_mm": {"$sum": "$rainfall_mm"},
                    "cities": {"$addToSet": "$st.city"}}},
        {"$project": {"_id": 0, "state": "$_id", "cities": 1,
                      "avg_temp": {"$round": ["$avg_temp", 1]},
                      "total_rain_mm": {"$round": ["$total_rain_mm", 1]}}},
        {"$sort": {"total_rain_mm": -1}},
    ]))


# 4. Extreme-heat events per station (top 5)
def extreme_heat_events(db, threshold=38, days=30):
    return list(db.readings.aggregate([
        {"$match": {"temperature_c": {"$gte": threshold}, "timestamp": {"$gte": _since(days)}}},
        {"$group": {"_id": "$station_id", "events": {"$sum": 1},
                    "peak_temp": {"$max": "$temperature_c"}}},
        {"$sort": {"events": -1, "peak_temp": -1}},
        {"$limit": 5},
        {"$project": {"_id": 0, "station_id": "$_id", "events": 1, "peak_temp": 1}},
    ]))


# 5. Temperature distribution using $bucket
def temperature_distribution(db, days=30):
    return list(db.readings.aggregate([
        {"$match": {"timestamp": {"$gte": _since(days)}}},
        {"$bucket": {"groupBy": "$temperature_c",
                     "boundaries": [-60, 10, 20, 25, 30, 35, 40, 61],
                     "default": "other",
                     "output": {"readings": {"$sum": 1},
                                "avg_humidity": {"$avg": "$humidity_pct"}}}},
    ]))


# 6. Weather condition share (%) using $group twice + $unwind
def condition_share(db, days=30):
    return list(db.readings.aggregate([
        {"$match": {"timestamp": {"$gte": _since(days)}}},
        {"$group": {"_id": "$condition", "n": {"$sum": 1}}},
        {"$group": {"_id": None, "total": {"$sum": "$n"},
                    "items": {"$push": {"condition": "$_id", "n": "$n"}}}},
        {"$unwind": "$items"},
        {"$project": {"_id": 0, "condition": "$items.condition", "count": "$items.n",
                      "percent": {"$round": [{"$multiply": [{"$divide": ["$items.n", "$total"]}, 100]}, 1]}}},
        {"$sort": {"count": -1}},
    ]))


# 7. TREND ANALYTICS: 3-day moving average ($setWindowFields, MongoDB 5.0+)
def temperature_trend(db, station_id, days=14):
    return list(db.readings.aggregate([
        {"$match": {"station_id": station_id, "timestamp": {"$gte": _since(days)}}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                    "avg_temp": {"$avg": "$temperature_c"}}},
        {"$set": {"date": "$_id"}},
        {"$setWindowFields": {"sortBy": {"date": 1},
                              "output": {"moving_avg_3d": {"$avg": "$avg_temp",
                                                           "window": {"documents": [-2, 0]}},
                                         "prev_day": {"$shift": {"output": "$avg_temp", "by": -1}}}}},
        {"$project": {"_id": 0, "date": 1,
                      "avg_temp": {"$round": ["$avg_temp", 1]},
                      "moving_avg_3d": {"$round": ["$moving_avg_3d", 1]},
                      "change_vs_prev_day": {"$round": [{"$subtract": ["$avg_temp", {"$ifNull": ["$prev_day", "$avg_temp"]}]}, 1]}}},
        {"$sort": {"date": 1}},
    ]))


# 8. ALERT GENERATION: scan readings and write alerts with $merge (idempotent)
def generate_alerts(db, days=30):
    db.readings.aggregate([
        {"$match": {"timestamp": {"$gte": _since(days)},
                    "$or": [{"temperature_c": {"$gte": 40}}, {"temperature_c": {"$lte": 2}},
                            {"rainfall_mm": {"$gte": 50}}, {"wind.speed_kmh": {"$gte": 60}}]}},
        {"$addFields": {"type": {"$switch": {"branches": [
            {"case": {"$gte": ["$temperature_c", 40]}, "then": "heatwave"},
            {"case": {"$lte": ["$temperature_c", 2]}, "then": "cold_wave"},
            {"case": {"$gte": ["$rainfall_mm", 50]}, "then": "heavy_rain"},
            {"case": {"$gte": ["$wind.speed_kmh", 60]}, "then": "high_wind"}],
            "default": "heatwave"}}}},
        {"$project": {
            "_id": {"$concat": ["$station_id", "-", "$type", "-",
                                {"$dateToString": {"format": "%Y%m%d%H", "date": "$timestamp"}}]},
            "station_id": 1, "type": 1,
            "severity": {"$cond": [{"$or": [{"$gte": ["$temperature_c", 44]},
                                            {"$gte": ["$rainfall_mm", 100]}]}, "critical", "warning"]},
            "message": {"$concat": ["Threshold exceeded (", "$type", "): temp ",
                                    {"$toString": "$temperature_c"}, "C, rain ",
                                    {"$toString": "$rainfall_mm"}, "mm, wind ",
                                    {"$toString": "$wind.speed_kmh"}, "km/h"]},
            "triggered_at": "$timestamp",
            "resolved": {"$literal": False}}},
        {"$merge": {"into": "alerts", "whenMatched": "keepExisting", "whenNotMatched": "insert"}},
    ])
    return db.alerts.count_documents({})


# 9. Open alerts grouped by type with the cities involved
def open_alerts_report(db):
    return list(db.alerts.aggregate([
        {"$match": {"resolved": False}},
        {"$lookup": {"from": "stations", "localField": "station_id",
                     "foreignField": "station_id", "as": "st"}},
        {"$unwind": "$st"},
        {"$group": {"_id": {"type": "$type", "severity": "$severity"},
                    "count": {"$sum": 1}, "cities": {"$addToSet": "$st.city"}}},
        {"$project": {"_id": 0, "type": "$_id.type", "severity": "$_id.severity",
                      "count": 1, "cities": 1}},
        {"$sort": {"count": -1}},
    ]))
