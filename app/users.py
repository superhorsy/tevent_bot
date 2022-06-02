from abc import ABC

import pymongo
from pymongo.collection import Collection
from pymongo.database import Database


class User:
    chat_id: int
    phone: str
    notifications: list

    def __init__(self, chat_id: int, phone: str, notifications: list = None):
        self.notifications = [] if notifications is None else notifications
        self.chat_id = chat_id
        self.phone = phone


class UserAccessor(ABC):
    def exists(self, chat_id) -> bool:
        pass

    def get(self, chat_id) -> User:
        pass

    def set(self, user: User):
        pass

    def delete(self, chat_id):
        pass

    def keys(self):
        pass


class UserNotFoundError(Exception):
    pass


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
