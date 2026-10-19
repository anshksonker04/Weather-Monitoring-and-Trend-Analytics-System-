"""Weather Monitoring & Trend Analytics System
Usage:  python main.py setup   -> create collections/validators + seed data
        python main.py demo    -> run every feature once (best for screenshots)
        python main.py menu    -> interactive CLI
"""
import sys
from pprint import pprint
from datetime import timedelta
from pymongo.errors import WriteError, DuplicateKeyError

import config, schema, seed_data, crud, aggregations as agg
from config import utcnow


def head(t):
    print(f"\n{'=' * 8} {t} {'=' * 8}")


NEW_STATION = {
    "station_id": "WS009", "name": "Pune Hills Station", "city": "Pune",
    "state": "Maharashtra", "location": {"type": "Point", "coordinates": [73.8567, 18.5204]},
    "elevation_m": 560, "status": "active", "installed_on": utcnow(),
    "sensors": ["temperature", "humidity"],
}


def setup(db):
    schema.setup_schema(db, drop=True)
    seed_data.seed(db)


def demo(db):
    head("VALIDATION: invalid reading must be rejected")
    bad = {"station_id": "WS001", "timestamp": utcnow(), "temperature_c": 999,
           "humidity_pct": 50, "pressure_hpa": 1000, "wind": {"speed_kmh": 5, "direction_deg": 90},
           "rainfall_mm": 0, "condition": "clear"}
    try:
        crud.add_reading(db, bad)
    except WriteError as e:
        print("Rejected by $jsonSchema validator ->", e.code, "DocumentValidationFailure")

    head("CREATE")
    crud.delete_station(db, "WS009")                       # keep demo re-runnable
    print("Inserted station _id:", crud.create_station(db, NEW_STATION))
    try:
        crud.create_station(db, NEW_STATION)
    except DuplicateKeyError:
        print("Duplicate station_id blocked by unique index")
    reading = {"station_id": "WS009", "timestamp": utcnow(), "temperature_c": 31.5,
               "humidity_pct": 62, "pressure_hpa": 955.2,
               "wind": {"speed_kmh": 11, "direction_deg": 220}, "rainfall_mm": 0.0,
               "condition": "clear"}
    print("Inserted reading _id:", crud.add_reading(db, reading))

    head("READ")
    pprint(crud.get_station(db, "WS001"))
    pprint(crud.latest_reading(db, "WS001"))
    print("Maharashtra stations:", crud.list_stations_by_state(db, "Maharashtra"))
    print("Hot & humid readings:"); pprint(crud.hot_and_humid(db))
    print("Stations within 1500 km of Nagpur, nearest first:", crud.stations_near(db, 79.0882, 21.1458, 1500))

    head("UPDATE")
    print("status ->", crud.set_station_status(db, "WS009", "maintenance"))
    print("sensor added ->", crud.add_sensor(db, "WS009", "pressure"))
    print("Maharashtra bulk update ->", crud.set_state_status(db, "Maharashtra", "active"))

    head("AGGREGATION 1: daily summary WS001 (last 5 days)")
    pprint(agg.daily_summary(db, "WS001", 5))
    head("AGGREGATION 2: station leaderboard ($lookup)")
    pprint(agg.station_leaderboard(db))
    head("AGGREGATION 3: state climate report")
    pprint(agg.state_climate_report(db))
    head("AGGREGATION 4: extreme heat events")
    pprint(agg.extreme_heat_events(db))
    head("AGGREGATION 5: temperature distribution ($bucket)")
    pprint(agg.temperature_distribution(db))
    head("AGGREGATION 6: condition share")
    pprint(agg.condition_share(db))
    head("AGGREGATION 7: 3-day moving average trend WS006")
    pprint(agg.temperature_trend(db, "WS006", 7))
    head("AGGREGATION 8: generate alerts ($merge)")
    print("Total alerts stored:", agg.generate_alerts(db))
    head("AGGREGATION 9: open alerts report")
    pprint(agg.open_alerts_report(db))

    head("DELETE")
    print("Old readings deleted (>45 days):", crud.delete_old_readings(db, 45))
    print("Station WS009 deleted:", crud.delete_station(db, "WS009"))


def menu(db):
    options = {
        "1": ("Latest reading of a station", lambda: pprint(crud.latest_reading(db, input("Station id (WS001-WS008): ").strip()))),
        "2": ("Add a reading", lambda: add_reading_cli(db)),
        "3": ("Daily summary", lambda: pprint(agg.daily_summary(db, input("Station id: ").strip(), 7))),
        "4": ("Station leaderboard", lambda: pprint(agg.station_leaderboard(db))),
        "5": ("Temperature trend (moving avg)", lambda: pprint(agg.temperature_trend(db, input("Station id: ").strip()))),
        "6": ("Generate + show alerts", lambda: (agg.generate_alerts(db), pprint(agg.open_alerts_report(db)))),
        "7": ("Change station status", lambda: print(crud.set_station_status(db, input("Station id: ").strip(), input("active/inactive/maintenance: ").strip()))),
        "0": ("Exit", None),
    }
    while True:
        print()
        for k, (label, _) in options.items():
            print(f"  {k}. {label}")
        choice = input("Choose: ").strip()
        if choice == "0":
            break
        if choice in options:
            try:
                options[choice][1]()
            except WriteError:
                print("Rejected by validation rules.")
        else:
            print("Invalid choice")


def add_reading_cli(db):
    r = {"station_id": input("Station id: ").strip(), "timestamp": utcnow(),
         "temperature_c": float(input("Temperature C: ")), "humidity_pct": float(input("Humidity %: ")),
         "pressure_hpa": float(input("Pressure hPa: ")),
         "wind": {"speed_kmh": float(input("Wind km/h: ")), "direction_deg": 0},
         "rainfall_mm": float(input("Rainfall mm: ")), "condition": input("Condition: ").strip()}
    print("Inserted:", crud.add_reading(db, r))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "menu"
    database = config.get_db()
    {"setup": setup, "demo": demo, "menu": menu}[mode](database)
