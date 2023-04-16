import pymongo

client = pymongo.MongoClient()
db = client["projet"]
poe_collection = db["poe"]