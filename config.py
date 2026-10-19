"""Connection settings. Override with:  export MONGO_URI="mongodb+srv://user:pass@cluster/..."  """
import os
from datetime import datetime
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "weather_monitoring"


def get_db():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")          # fail fast if MongoDB is not running
    return client[DB_NAME]


def utcnow():
    """Naive UTC datetime (PyMongo stores/reads naive datetimes as UTC)."""
    return datetime.utcnow().replace(microsecond=0)
