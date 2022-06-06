import configparser

import pymongo
from model.users import User, UserAccessor, UserNotFoundError
from pymongo.collection import Collection
from pymongo.database import Database

conf = configparser.ConfigParser()
conf.read("config/config.ini")
mongo_conf = conf["mongo"]


class MongoDBUserAccessor(UserAccessor):
    def __init__(self, host: str, port: int, db: str) -> None:
        self.db: Database = pymongo.MongoClient(f"mongodb://{host}:{port}/")[db]
        self.collection: Collection = self.db.get_collection("users")

    def exists(self, chat_id: int) -> bool:
        return self.collection.count_documents({"_id": chat_id}) > 0

    def get(self, chat_id: int) -> User:
        data = self.collection.find_one({"_id": chat_id})
        if not data:
            raise UserNotFoundError(f"Didn't found user by chat_id {chat_id}")
        return User(data["_id"], data["phone"], data["notifications"])

    def set(self, user: User):
        self.collection.replace_one(
            {"_id": int(user.chat_id)},
            {
                "_id": int(user.chat_id),
                "phone": user.phone,
                "notifications": user.notifications,
            },
            upsert=True,
        )

    def delete(self, chat_id):
        self.collection.delete_many({"_id": int(chat_id)})

    def keys(self):
        return [i.get("_id") for i in self.collection.find()]


users = MongoDBUserAccessor(
    mongo_conf.get("host", "localhost"),
    int(mongo_conf.get("port", "27017")),
    mongo_conf.get("db", "tevent"),
)
