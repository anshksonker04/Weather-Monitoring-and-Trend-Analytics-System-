"""Single-page Streamlit front end for the Weather Monitoring system.
Run:  streamlit run app.py
"""
from datetime import timedelta

import pandas as pd
import streamlit as st
from pymongo.errors import DuplicateKeyError, WriteError

import aggregations as agg
import config
import crud
import schema
import seed_data
from config import utcnow

st.set_page_config(page_title="Weather Monitoring & Trend Analytics",
                   page_icon="🌦️", layout="wide")


# ---------------------------------------------------------------- helpers
@st.cache_resource
def connect():
    return config.get_db()


def flash(msg, kind="success"):
    st.session_state["flash"] = (kind, msg)
    st.rerun()


def show_flash():
    if "flash" in st.session_state:
        kind, msg = st.session_state.pop("flash")
        getattr(st, kind)(msg)


def stations_df(db):
    rows = []
    for s in db.stations.find({}, {"_id": 0}):
        lon, lat = s["location"]["coordinates"]
        rows.append({"station_id": s["station_id"], "name": s["name"], "city": s["city"],
                     "state": s["state"], "status": s["status"],
                     "elevation_m": s.get("elevation_m"), "lat": lat, "lon": lon,
                     "sensors": ", ".join(s.get("sensors", []))})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- connect
st.title("🌦️ Weather Monitoring & Trend Analytics")
st.caption("MongoDB + PyMongo + Streamlit  |  CSE494 Intelligent NoSQL Databases")

try:
    db = connect()
except Exception as e:                       # server down / bad URI
    st.error(f"Cannot connect to MongoDB at {config.MONGO_URI}.\n\n{e}")
    st.stop()

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Controls")
    st.success(f"Connected: {config.DB_NAME}")
    sdf = stations_df(db)
    if sdf.empty:
        st.warning("No data yet. Initialise the database below.")
        station_id, days = None, 30
    else:
        labels = {r.station_id: f"{r.station_id} - {r.city}" for r in sdf.itertuples()}
        station_id = st.selectbox("Station", list(labels), format_func=labels.get)
        days = st.slider("Analysis window (days)", 3, 60, 30)

    st.divider()
    st.subheader("Database setup")
    st.caption("Recreates collections, validators, indexes and sample data.")
    confirm = st.checkbox("I understand this deletes existing data")
    if st.button("Initialise / reseed", disabled=not confirm):
        schema.setup_schema(db, drop=True)
        seed_data.seed(db)
        flash("Database initialised with sample data.")

show_flash()
if sdf.empty:
    st.stop()

tab_dash, tab_trend, tab_read, tab_stn, tab_alert = st.tabs(
    ["📊 Dashboard", "📈 Trends & Analytics", "➕ Readings & Validation",
     "🏢 Stations (CRUD)", "🚨 Alerts"])

# ================================================================ DASHBOARD
with tab_dash:
    latest = crud.latest_reading(db, station_id)
    st.subheader(f"Latest reading - {labels[station_id]}")
    if latest:
        c = st.columns(5)
        c[0].metric("Temperature", f"{latest['temperature_c']} °C")
        c[1].metric("Humidity", f"{latest['humidity_pct']} %")
        c[2].metric("Pressure", f"{latest['pressure_hpa']} hPa")
        c[3].metric("Wind", f"{latest['wind']['speed_kmh']} km/h")
        c[4].metric("Rainfall", f"{latest['rainfall_mm']} mm")
        st.caption(f"{latest['timestamp']} UTC  |  condition: {latest['condition']}")
    else:
        st.info("No readings for this station yet.")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Daily temperature (min / avg / max)")
        daily = agg.daily_summary(db, station_id, min(days, 14))
        if daily:
            d = pd.DataFrame(daily).set_index("date")
            st.line_chart(d[["min_temp", "avg_temp", "max_temp"]])
            st.bar_chart(d["total_rain_mm"])
    with right:
        st.subheader("Station map")
        st.map(sdf[["lat", "lon"]], zoom=3)

    st.subheader(f"Station leaderboard (last {days} days)")
    lb = pd.DataFrame(agg.station_leaderboard(db, days))
    if not lb.empty:
        st.dataframe(lb, width="stretch", hide_index=True)
        st.bar_chart(lb.set_index("city")["avg_temp"])

# ================================================================ TRENDS
with tab_trend:
    st.subheader(f"Temperature trend with 3-day moving average - {labels[station_id]}")
    trend = pd.DataFrame(agg.temperature_trend(db, station_id, max(days, 7)))
    if not trend.empty:
        st.line_chart(trend.set_index("date")[["avg_temp", "moving_avg_3d"]])
        with st.expander("Show pipeline output"):
            st.dataframe(trend, width="stretch", hide_index=True)

    a, b = st.columns(2)
    with a:
        st.subheader("Temperature distribution ($bucket)")
        dist = agg.temperature_distribution(db, days)
        if dist:
            dd = pd.DataFrame(dist)
            dd["range"] = dd["_id"].astype(str) + "+ °C"
            dd["avg_humidity"] = dd["avg_humidity"].round(1)
            st.bar_chart(dd.set_index("range")["readings"])
    with b:
        st.subheader("Weather condition share")
        cs = pd.DataFrame(agg.condition_share(db, days))
        if not cs.empty:
            st.bar_chart(cs.set_index("condition")["percent"])
            st.dataframe(cs, width="stretch", hide_index=True)

    st.subheader("Extreme heat events")
    thr = st.slider("Heat threshold (°C)", 30, 45, 38)
    heat = pd.DataFrame(agg.extreme_heat_events(db, thr, days))
    if heat.empty:
        st.info("No readings above this threshold.")
    else:
        st.dataframe(heat, width="stretch", hide_index=True)

    st.subheader("State climate report ($lookup + $group)")
    sr = pd.DataFrame(agg.state_climate_report(db, days))
    if not sr.empty:
        sr["cities"] = sr["cities"].apply(", ".join)
        st.dataframe(sr, width="stretch", hide_index=True)

# ================================================================ READINGS
with tab_read:
    st.subheader("Add a reading")
    st.caption("Values are NOT limited in the form on purpose: try temperature 999 "
               "and watch the MongoDB $jsonSchema validator reject it.")
    with st.form("add_reading", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        r_station = c1.selectbox("Station", list(labels), index=list(labels).index(station_id),
                                 format_func=labels.get)
        r_temp = c1.number_input("Temperature (°C)", value=30.0, min_value=-500.0, max_value=500.0)
        r_hum = c2.number_input("Humidity (%)", value=60.0, min_value=-500.0, max_value=500.0)
        r_press = c2.number_input("Pressure (hPa)", value=1000.0, min_value=0.0, max_value=5000.0)
        r_wind = c3.number_input("Wind speed (km/h)", value=10.0, min_value=-100.0, max_value=500.0)
        r_dir = c3.number_input("Wind direction (deg)", value=90.0, min_value=-100.0, max_value=1000.0)
        r_rain = c1.number_input("Rainfall (mm)", value=0.0, min_value=-100.0, max_value=1000.0)
        r_cond = c2.selectbox("Condition", ["clear", "cloudy", "rainy", "hot", "humid", "stormy"])
        submitted = st.form_submit_button("Insert reading")
    if submitted:
        doc = {"station_id": r_station, "timestamp": utcnow(), "temperature_c": r_temp,
               "humidity_pct": r_hum, "pressure_hpa": r_press,
               "wind": {"speed_kmh": r_wind, "direction_deg": r_dir},
               "rainfall_mm": r_rain, "condition": r_cond}
        try:
            _id = crud.add_reading(db, doc)
            st.success(f"Inserted reading {_id}")
        except WriteError as e:
            st.error("Rejected by MongoDB validation (Document failed validation).")
            st.json(e.details.get("errInfo", {"error": str(e)}), expanded=False)

    st.subheader(f"Recent readings - {labels[station_id]}")
    n = st.slider("Rows", 5, 50, 10)
    recent = crud.readings_in_range(db, station_id, utcnow() - timedelta(days=90),
                                    utcnow() + timedelta(days=1), n)
    if recent:
        flat = pd.json_normalize(recent)
        st.dataframe(flat, width="stretch", hide_index=True)

    st.subheader("Query: hot & humid readings")
    q1, q2 = st.columns(2)
    qt = q1.slider("Min temperature (°C)", 20, 45, 35)
    qh = q2.slider("Min humidity (%)", 0, 100, 60)
    hh = crud.hot_and_humid(db, qt, qh, 10)
    if hh:
        st.dataframe(pd.DataFrame(hh), width="stretch", hide_index=True)
    else:
        st.info("No matches.")

    st.subheader("Maintenance: delete old readings")
    old_days = st.number_input("Delete readings older than (days)", 1, 365, 45)
    if st.button("Delete old readings"):
        flash(f"Deleted {crud.delete_old_readings(db, int(old_days))} old readings.")

# ================================================================ STATIONS
with tab_stn:
    st.subheader("All stations")
    st.dataframe(sdf.drop(columns=["lat", "lon"]), width="stretch", hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Create station")
        with st.form("new_station"):
            ns_id = st.text_input("Station id (WS###)", "WS009")
            ns_name = st.text_input("Name", "Pune Hills Station")
            ns_city = st.text_input("City", "Pune")
            ns_state = st.text_input("State", "Maharashtra")
            g1, g2, g3 = st.columns(3)
            ns_lon = g1.number_input("Longitude", value=73.8567, format="%.4f")
            ns_lat = g2.number_input("Latitude", value=18.5204, format="%.4f")
            ns_elev = g3.number_input("Elevation (m)", value=560)
            ns_status = st.selectbox("Status", ["active", "inactive", "maintenance"])
            ns_sensors = st.multiselect("Sensors", ["temperature", "humidity", "pressure",
                                                    "wind", "rainfall"], ["temperature", "humidity"])
            create = st.form_submit_button("Create station")
        if create:
            doc = {"station_id": ns_id.strip(), "name": ns_name, "city": ns_city,
                   "state": ns_state, "elevation_m": ns_elev, "status": ns_status,
                   "location": {"type": "Point", "coordinates": [ns_lon, ns_lat]},
                   "installed_on": utcnow(), "sensors": ns_sensors}
            try:
                crud.create_station(db, doc)
                flash(f"Station {ns_id} created.")
            except DuplicateKeyError:
                st.error("station_id already exists (unique index).")
            except WriteError:
                st.error("Rejected by validation (check id format WS### and required fields).")

    with c2:
        st.subheader(f"Update / delete - {station_id}")
        new_status = st.selectbox("New status", ["active", "inactive", "maintenance"])
        if st.button("Update status"):
            flash(f"Modified {crud.set_station_status(db, station_id, new_status)} station(s).")
        sensor = st.selectbox("Add sensor", ["temperature", "humidity", "pressure", "wind", "rainfall"])
        if st.button("Add sensor ($addToSet)"):
            flash(f"Modified {crud.add_sensor(db, station_id, sensor)} station(s).")
        state_sel = st.selectbox("Bulk status by state", sorted(sdf["state"].unique()))
        bulk = st.selectbox("Set all in state to", ["active", "inactive", "maintenance"], key="bulk")
        if st.button("Bulk update (update_many)"):
            flash(f"Modified {crud.set_state_status(db, state_sel, bulk)} station(s).")
        st.divider()
        ok = st.checkbox(f"Confirm delete {station_id}")
        if st.button("Delete station", disabled=not ok):
            flash(f"Deleted {crud.delete_station(db, station_id)} station.", "warning")

    st.subheader("Geospatial search ($near on 2dsphere index)")
    g1, g2, g3 = st.columns(3)
    glon = g1.number_input("Longitude", value=79.0882, format="%.4f", key="glon")
    glat = g2.number_input("Latitude", value=21.1458, format="%.4f", key="glat")
    gkm = g3.slider("Radius (km)", 100, 3000, 1500)
    near = crud.stations_near(db, glon, glat, gkm)
    st.write("Nearest first:", ", ".join(near) if near else "none in range")

# ================================================================ ALERTS
with tab_alert:
    st.subheader("Alert engine")
    st.caption("Scans readings for heatwave (>=40°C), cold wave (<=2°C), heavy rain "
               "(>=50mm) and high wind (>=60km/h) and writes alerts using $merge.")
    if st.button("Run alert generation"):
        flash(f"Alert scan complete. Total alerts stored: {agg.generate_alerts(db, days)}")

    rep = pd.DataFrame(agg.open_alerts_report(db))
    if rep.empty:
        st.info("No open alerts. Run alert generation.")
    else:
        rep["cities"] = rep["cities"].apply(", ".join)
        st.dataframe(rep, width="stretch", hide_index=True)

    al = list(db.alerts.find({"resolved": False}, {"_id": 0}).sort("triggered_at", -1).limit(50))
    if al:
        st.dataframe(pd.DataFrame(al), width="stretch", hide_index=True)
    if st.button(f"Resolve open alerts for {station_id}"):
        flash(f"Resolved {crud.resolve_alerts(db, station_id)} alert(s).")
