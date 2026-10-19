from pymongo import AsyncMongoClient
from core.config import settings

# En aplicaciones como FastAPI, es preferible manejar el cliente dentro del ciclo de vida (lifespan)
client: AsyncMongoClient = AsyncMongoClient(settings.mongo_uri)
database = client[settings.mongo_db_name]

customers_collection = database["customers"]
technicians_collection = database["technicians"]
routes_collection = database["routes"]
admin_collection = database["admins"]