import threading
from abc import ABC
from typing import Optional

import pickledb


class User:
    def __init__(self, phone, notifications=None):
        if notifications is None:
            notifications = []
        self.notifications = notifications
        self.phone = phone


class UserAccessor(ABC):
    def get(self, chat_id) -> Optional[User]:
        pass

    def set(self, chat_id, user: User):
        pass

    def delete(self, chat_id):
        pass

    def get_all_chat_ids(self):
        pass


class UserNotFoundError(Exception):
    pass


class PickleDBUserAccessor(UserAccessor):
    def __init__(self):
        self.db = pickledb.load("db/users.db", True)
        self.lock = threading.Lock()

    def get_all_chat_ids(self) -> list:
        with self.lock:
            data = self.db.getall()
        if not data:
            return []
        return data

    def get(self, chat_id) -> User:
        with self.lock:
            data = self.db.get(str(chat_id))
        if not data:
            raise UserNotFoundError("Didn't found user by chat_id " + chat_id)
        return User(data["phone"], data["notifications"])

    def set(self, chat_id, user: User):
        with self.lock:
            self.db.set(
                str(chat_id), {"phone": user.phone, "notifications": user.notifications}
            )

    def delete(self, chat_id):
        with self.lock:
            self.db.rem(str(chat_id))
