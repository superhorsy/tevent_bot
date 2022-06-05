from abc import ABC


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
