# Weather Monitoring & Trend Analytics System (MongoDB + PyMongo)

CSE494 Intelligent NoSQL Databases, CA2 project.

## Stack
MongoDB 6.0+ (Community or Atlas M0) | Python 3.10+ | PyMongo | Streamlit + pandas | MongoDB Compass | mongosh | VS Code

## Run
```
pip install -r requirements.txt
# make sure mongod is running (or set MONGO_URI to your Atlas string)
python main.py setup     # collections + validators + indexes + seed data
python main.py demo      # runs validation, CRUD and all 9 aggregations
python main.py menu      # interactive CLI
streamlit run app.py     # single-page web app (http://localhost:8501)
mongosh weather_monitoring queries.js   # raw mongosh versions
```
Note: `$setWindowFields` (trend pipeline) needs MongoDB 5.0+.

## Problem
Weather stations continuously produce sensor readings. Agencies need to store them
reliably, reject bad data, query recent conditions, spot trends and raise alerts.

## Design (3 collections)
| Collection | Purpose | Design choice |
|---|---|---|
| stations | Metadata + GeoJSON location + sensors array | Small, stable; sensors **embedded** as array |
| readings | Time-series style sensor data | Separate collection, **referenced** by station_id (unbounded growth); wind **embedded** sub-document |
| alerts | Generated warnings | Written by `$merge` from readings |

Indexes: unique station_id; 2dsphere on location; (station_id, timestamp desc) for latest/range queries.

## Validation
`$jsonSchema` on all collections: required fields, types, ranges (temperature -60..60,
humidity 0..100, pressure 300..1100), enums (status, condition, alert type), regex on
station_id, nested checks (wind, GeoJSON), `validationAction: error`, level `strict`.

## Report outline (5 marks)
1 Problem and relevance | 2 Stack | 3 Schema diagram + embed vs reference reasoning |
4 Validation rules + rejected-insert screenshot | 5 CRUD with screenshots |
6 Each aggregation: purpose, pipeline, output | 7 PyMongo structure | 8 Conclusion

## Likely viva questions
- Why is readings separate from stations? (unbounded growth, 16 MB doc limit, query patterns)
- What does `$lookup` do and when is it costly? (left outer join; index foreignField)
- Difference between `$set` / `$addToSet` / `$push`?
- Why validationAction error vs warn? strict vs moderate?
- How does `$merge` stay idempotent here? (deterministic `_id`, keepExisting)
- What does the compound index do for "latest reading"?
- Be ready to change thresholds, add a `$match`, or group by another field live.

## Make it yours
The brief asks for your own scenario: change the stations/cities, add a field
(e.g. air_quality_index) with its validator, and add one pipeline of your own.
