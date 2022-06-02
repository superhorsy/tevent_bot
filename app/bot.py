import configparser
import random
import re
import string
from datetime import datetime, timedelta

import gspread
import messages as msg
import telebot
from logger import get_logger
from users import MongoDBUserAccessor, User, UserNotFoundError

# Config
conf = configparser.ConfigParser()
conf.read("config/config.ini")
mongo_conf = conf["mongo"]

log = get_logger(__name__)

bot = telebot.TeleBot(conf["bot"]["token"])

# GoogleTables
# Open a sheet from a spreadsheet in one go
gc = gspread.service_account(filename="./config/google-service-account-key.json")
sh = gc.open_by_key(conf["google"]["spreadsheet"])
wks = sh.get_worksheet(0)
try:
    promo_wks = sh.get_worksheet(1)
except gspread.WorksheetNotFound:
    promo_wks = sh.add_worksheet("Promocodes", 0, 4, index=1)

# MongoDB
users = MongoDBUserAccessor(
    mongo_conf.get("host", "localhost"),
    int(mongo_conf.get("port", "27017")),
    mongo_conf.get("db", "tevent"),
)

DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"


def _notify(user: User):
    log.info(f"Notifying user {user.chat_id} /{user.phone}/")
    _send(msg.REMINDER, user.chat_id)
    user.notifications.insert(0, datetime.now().strftime(DATETIME_FORMAT))
    users.set(user)
    log.info("User notified")


def remind():
    log.info("Reminder started")
    user_list = users.keys()
    for id in user_list:
        log.info(f"Notifying chat: {id}")
        try:
            user: User = users.get(id)
        except UserNotFoundError as e:
            log.error(e)
            continue

        log.info(f"Notification count: {len(user.notifications)}")
        if len(user.notifications) >= 3:
            continue
        last_promo = Promo.find(user.phone)
        log.info(f"Last promo: {last_promo}")
        if not last_promo:
            continue
        if last_promo.is_valid():
            log.info("Promo is valid")
            continue
        if not user.notifications:
            log.info("Notifying for first time")
            _notify(user)
            continue

        last_notification = datetime.strptime(user.notifications[0], DATETIME_FORMAT)
        log.info(f"Last notification was at {last_notification}")
        log.info(
            f"Next promo will be at {last_promo.next_date().strftime(DATETIME_FORMAT)}"
        )

        if last_notification < last_promo.next_date():
            log.info("Time to notify")
            _notify(user)
            continue
        log.info("Notification not needed")

    log.info("Reminder finished")


def _send(mess: str, chat_id: int):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    if users.exists(chat_id):
        markup.add(telebot.types.KeyboardButton("🎲"))
        markup.add(telebot.types.KeyboardButton("Выйти"), row_width=2)
    markup.add(telebot.types.KeyboardButton("Справка"))
    clear_mess = mess.replace("\n", "")
    log.info(f"Chat: {chat_id}, message: {clear_mess}")
    bot.send_message(chat_id, mess, parse_mode="html", reply_markup=markup)


def main():
    def logout(message):
        users.delete(str(message.chat.id))
        start(message)

    @bot.message_handler(commands=["help"])
    def show_help(message: telebot.types.Message):
        _send(msg.HELP, message.chat.id)

    @bot.message_handler(commands=["start"])
    def start(message: telebot.types.Message):
        if users.exists(message.chat.id):
            _send(msg.EXISTING_USER, message.chat.id)
            return
        _send(
            f"Привет {message.from_user.first_name}! \n{msg.NOT_LOGGED_IN}",
            message.chat.id,
        )

    @bot.message_handler(
        func=lambda message: message.text != "Справка"
        and not users.exists(message.chat.id)
    )
    def login(message: telebot.types.Message):
        input_phone = message.text
        log.info(f"Введено: {input_phone}")
        match = re.match(
            "\+?[7,8]?([\s-]*\d{3}[\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2})",  # noqa:W605
            input_phone,
        )
        if not match:
            _send(
                f"Некорректный номер телефона. \n{msg.NOT_LOGGED_IN}", message.chat.id
            )
            log.info(f"Введен некорректный номер телефона: {message.text}")
            return
        phone = [i for i in match.groups()[0] if str.isdigit(i)]
        search = f"\\+?[7,8]([\\s-]*{''.join(phone[:3])}[\\s-]*{''.join(phone[3:6])}[\\s-]*{''.join(phone[6:8])}[\\s-]*{''.join(phone[8:10])})"

        find = wks.find(in_column=7, query=re.compile(search))
        if find is None:
            _send(f"Номер телефона не найден. \n{msg.NOT_LOGGED_IN}", message.chat.id)
            return
        values: list = wks.row_values(find.row)
        filtered_phone = "".join(phone)

        user = User(message.chat.id, filtered_phone)
        users.set(user)

        _send(
            f"Мы тебя узнали, {values[0]}! Теперь подыщем тебе промокод...",
            user.chat_id,
        )

        get_promo(user)

    def get_promo(user: User):
        log.info(f"User {user.phone} looking for promo")
        promo: Promo = Promo.find(user.phone)

        if promo and promo.is_valid():
            log.info(f"User {user.chat_id} /{user.phone}/ has promo {promo.code}")
            _send(
                f"Текущий промокод: \n"
                f"🎫 Награда - {promo.award} \n"
                f"🏷 Выдан {promo.date.strftime(DATETIME_FORMAT)} (МСК) \n"
                f"🔐 Код {promo.code} \n",
                user.chat_id,
            )
            _send(
                f"Новый промокод будет доступен {promo.next_date().strftime(DATETIME_FORMAT)}.",
                user.chat_id,
            )
            return

        new_promo = Promo.new(user.phone)
        _send(
            f"Поздравляем! Ты выиграл {new_promo.award} 🎉 \n"
            f"🏷 Выдан {new_promo.date.strftime(DATETIME_FORMAT)} (МСК) \n"
            f"🔐 Код {new_promo.code} \n",
            user.chat_id,
        )
        return

    @bot.message_handler(content_types=["text"])
    def text_helper(message: telebot.types.Message):
        log.debug(f"Message is {message}")
        if message.text == "🎲":
            if not users.exists(message.chat.id):
                logout(message)
                return
            get_promo(users.get(message.chat.id))
        elif message.text == "Справка":
            show_help(message)
        elif message.text == "Выйти":
            logout(message)

    bot.infinity_polling(timeout=10, long_polling_timeout=5)


class Promo:
    # promo expiry interval in days
    PROMO_EXPIRY_INTERVAL = 3

    def __init__(
        self,
        phone: str,
        code: str = None,
        award: str = None,
        date: datetime = datetime.now(),
    ) -> None:
        if not award:
            award = Promo.__generate_award()
        self.award = award
        if not code:
            code = Promo.__generate_code()
        self.code = code
        self.date = date
        self.phone = phone

    def __str__(self):
        return f"code: {self.code}, date: {self.date}, phone: {self.phone}"

    def is_valid(self):
        return datetime.now() < self.next_date()

    def next_date(self) -> datetime:
        return self.date + timedelta(days=Promo.PROMO_EXPIRY_INTERVAL)

    @staticmethod
    def find(phone: str):
        """row: 0 - phone, 1 - date, 2 - code, 3 - award"""
        promos_with_phone = [promo for promo in (promo_wks.get()) if promo[0] == phone]
        if not promos_with_phone:
            return None
        promos_with_phone.sort(
            key=lambda x: datetime.strptime(x[1], DATETIME_FORMAT), reverse=True
        )
        last_promo = promos_with_phone[0]

        return Promo(
            code=last_promo[2],
            award=last_promo[3],
            date=datetime.strptime(last_promo[1], DATETIME_FORMAT),
            phone=last_promo[0],
        )

    @staticmethod
    def new(phone: str):
        return Promo(phone=phone).save()

    @staticmethod
    def __generate_code() -> str:
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

    @staticmethod
    def __generate_award() -> str:
        award_40_perc = "1 час"
        award_30_perc = "4 часа"
        award_20_perc = "6 часов"
        award_10_perc = "энергетик"
        return random.choice(
            [
                award_40_perc,
                award_40_perc,
                award_40_perc,
                award_40_perc,
                award_30_perc,
                award_30_perc,
                award_30_perc,
                award_20_perc,
                award_20_perc,
                award_10_perc,
            ]
        )

    def save(self):
        promo_wks.append_row(
            [self.phone, self.date.strftime(DATETIME_FORMAT), self.code, self.award]
        )
        return self
