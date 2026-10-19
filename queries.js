// mongosh equivalents of the main queries.  Run: mongosh weather_monitoring queries.js
use("weather_monitoring");

// ---- Validator (schema.py shows the full version) ----
db.runCommand({ collMod: "readings", validationLevel: "strict", validationAction: "error" });

// ---- CREATE ----
db.stations.insertOne({
  station_id: "WS009", name: "Pune Hills Station", city: "Pune", state: "Maharashtra",
  location: { type: "Point", coordinates: [73.8567, 18.5204] },
  elevation_m: 560, status: "active", sensors: ["temperature", "humidity"]
});

// ---- READ ----
db.readings.find({ station_id: "WS001" }).sort({ timestamp: -1 }).limit(1);
db.readings.find({ temperature_c: { $gte: 35 }, humidity_pct: { $gte: 60 } }).sort({ temperature_c: -1 }).limit(5);
db.stations.find({ location: { $near: { $geometry: { type: "Point", coordinates: [79.0882, 21.1458] }, $maxDistance: 1500000 } } });

// ---- UPDATE ----
db.stations.updateOne({ station_id: "WS009" }, { $set: { status: "maintenance" } });
db.stations.updateOne({ station_id: "WS009" }, { $addToSet: { sensors: "pressure" } });
db.stations.updateMany({ state: "Maharashtra" }, { $set: { status: "active" } });

// ---- DELETE ----
db.readings.deleteMany({ timestamp: { $lt: new Date(Date.now() - 45 * 864e5) } });
db.stations.deleteOne({ station_id: "WS009" });

// ---- AGGREGATION: leaderboard with $lookup ----
db.readings.aggregate([
  { $match: { timestamp: { $gte: new Date(Date.now() - 30 * 864e5) } } },
  { $group: { _id: "$station_id", avg_temp: { $avg: "$temperature_c" }, total_rain: { $sum: "$rainfall_mm" } } },
  { $lookup: { from: "stations", localField: "_id", foreignField: "station_id", as: "station" } },
  { $unwind: "$station" },
  { $project: { _id: 0, city: "$station.city", avg_temp: { $round: ["$avg_temp", 1] }, total_rain: { $round: ["$total_rain", 1] } } },
  { $sort: { avg_temp: -1 } }
]);

// ---- AGGREGATION: moving average ----
db.readings.aggregate([
  { $match: { station_id: "WS006" } },
  { $group: { _id: { $dateToString: { format: "%Y-%m-%d", date: "$timestamp" } }, avg_temp: { $avg: "$temperature_c" } } },
  { $setWindowFields: { sortBy: { _id: 1 }, output: { moving_avg_3d: { $avg: "$avg_temp", window: { documents: [-2, 0] } } } } }
]);
