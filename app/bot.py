import configparser
import random
import re
import string
from datetime import datetime, timedelta

import gspread
import telebot
from users import PickleDBUserAccessor, User, UserNotFoundError

from app.logger import get_logger

conf = configparser.ConfigParser()
conf.read("config/config.ini")

log = get_logger(__name__)

bot = telebot.TeleBot(conf["bot"]["token"])

gc = gspread.service_account(filename="./config/google-service-account-key.json")
# Open a sheet from a spreadsheet in one go
sh = gc.open_by_key(conf["google"]["spreadsheet"])
wks = sh.get_worksheet(0)
users = PickleDBUserAccessor()

try:
    promo_wks = sh.get_worksheet(1)
except gspread.WorksheetNotFound:
    promo_wks = sh.add_worksheet("Promocodes", 0, 4, index=1)

DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"
NOT_LOGGED_IN = "Введи свой номер телефона"


def remind():
    def _notify(chat_id, user):
        user.notifications.insert(0, datetime.now().strftime(DATETIME_FORMAT))
        users.set(chat_id, user)
        _send(
            "3 суток прошли и ты снова можешь забрать свой бонус 1 час, пакет 4 часа, энергетик, Ягуар XF. Просто "
            "нажимай на 🎲 внизу экрана",
            chat_id,
        )

    user_list = users.get_all_chat_ids()
    for chat_id in user_list:
        print("Notifying chat: " + chat_id)
        try:
            user: User = users.get(chat_id)
        except UserNotFoundError as e:
            log.error(e)
            continue

        print("Notification count: " + str(len(user.notifications)))
        if len(user.notifications) >= 3:
            continue
        last_promo = Promo.find_promo(user.phone)
        if last_promo.is_valid():
            continue
        if not user.notifications:
            print("notify for first time")
            _notify(chat_id, user)
            continue

        last_notification = datetime.strptime(user.notifications[0], DATETIME_FORMAT)
        print(user.notifications[0] + " last notification")
        print(last_promo.next_date().strftime(DATETIME_FORMAT) + " next promo")
        if last_notification < last_promo.next_date():
            print("Time to notify")
            _notify(chat_id, user)
            continue
        print("No time to notify")


def _send(mess: str, chat_id):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    if users.get(str(chat_id)):
        item_roll = telebot.types.KeyboardButton("🎲")
        markup.add(item_roll)
    item_help = telebot.types.KeyboardButton("Справка")
    if users.get(str(chat_id)):
        item_logout = telebot.types.KeyboardButton("Выйти")
        markup.add(item_logout, row_width=2)
    markup.add(item_help)
    bot.send_message(chat_id, mess, parse_mode="html", reply_markup=markup)


def main():
    def logout(message):
        users.delete(str(message.chat.id))
        start(message)

    @bot.message_handler(commands=["help"])
    def show_help(message: telebot.types.Message):
        _send(
            "📍 Участвовать в игре можно один раз в 72 часа.\n"
            "📍 Подарок можно забрать в течении суток со дня получения сообщения.\n"
            "📍 На входе в клуб необходимо предоставить менеджеру сообщение в переписке с данным чат-ботом.\n"
            "⛔️ Скриншоты и переотправленные сообщения в другие диалоги засчитаны не будут!",
            message.chat.id,
        )

    @bot.message_handler(commands=["start"])
    def start(message: telebot.types.Message):
        if users.get(str(message.chat.id)):
            _send(
                "Привет! Жми на 🎲, чтобы проверить, нет ли для тебя приза",
                message.chat.id,
            )
            return
        _send(
            f"Привет {message.from_user.first_name}! \n{NOT_LOGGED_IN}", message.chat.id
        )

    @bot.message_handler(
        func=lambda message: not users.get(str(message.chat.id))
        and message.text != "Справка"
    )
    def login(message: telebot.types.Message):
        input_phone = message.text
        print(f"Введено: {input_phone}")
        match = re.match(
            "\+?[7,8]?([\s-]*\d{3}[\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2})",  # noqa:W605
            input_phone,
        )
        if not match:
            _send(f"Некорректный номер телефона. \n{NOT_LOGGED_IN}", message.chat.id)
            print("Введен некорректный номер телефона: " + message.text)
            return
        phone = [i for i in match.groups()[0] if str.isdigit(i)]
        search = f"\+?[7,8]([\s-]*{''.join(phone[0:3])}[\s-]*{''.join(phone[3:6])}[\s-]*{''.join(phone[6:8])}[\s-]*{''.join(phone[8:10])})"  # noqa:W605
        find = wks.find(in_column=7, query=re.compile(search))
        if find is None:
            _send(f"Номер телефона не найден. \n{NOT_LOGGED_IN}", message.chat.id)
            return
        values: list = wks.row_values(find.row)
        filtered_phone = "".join(phone)

        users.set(str(message.chat.id), User(filtered_phone))

        _send(
            f"Мы тебя узнали, {values[0]}! Теперь подыщем тебе промокод...",
            message.chat.id,
        )
        get_promo(message)

    def get_promo(message: telebot.types.Message):
        user: User = users.get(str(message.chat.id))
        promo: Promo = Promo.find(user.phone)

        if promo and promo.is_valid():
            _send(
                f"Текущий промокод: \n"
                f"🎫 Награда - {promo.award} \n"
                f"🏷 Выдан {promo.date.strftime(DATETIME_FORMAT)} (МСК) \n"
                f"🔐 Код {promo.code} \n",
                message.chat.id,
            )
            _send(
                f"Новый промокод будет доступен {promo.next_date().strftime(DATETIME_FORMAT)}.",
                message.chat.id,
            )
            return

        new_promo = Promo.new(user.phone)
        _send(
            f"Поздравляем! Ты выиграл {new_promo.award} 🎉 \n"
            f"🏷 Выдан {new_promo.date.strftime(DATETIME_FORMAT)} (МСК) \n"
            f"🔐 Код {new_promo.code} \n",
            message.chat.id,
        )
        return

    @bot.message_handler(content_types=["text"])
    def text_helper(message: telebot.types.Message):
        if message.text == "🎲":
            get_promo(message)
        elif message.text == "Справка":
            show_help(message)
        elif message.text == "Выйти":
            logout(message)

    bot.infinity_polling(timeout=10, long_polling_timeout=5)


class Promo:
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

    def is_valid(self):
        if datetime.now() < self.next_date():
            return True
        return False

    def next_date(self) -> datetime:
        return self.date + timedelta(days=3)

    @staticmethod
    def find_promo(phone: str):
        """row: 0 - phone, 1 - date, 2 - code, 3 - award"""
        promo_rows: list = promo_wks.findall(in_column=1, query=phone)
        if not promo_rows:
            return None

        promo_values: list = list(
            map(lambda x: promo_wks.row_values(x.row), promo_rows)
        )
        promo_values.sort(
            key=lambda x: datetime.strptime(x[1], DATETIME_FORMAT), reverse=True
        )

        date: datetime = datetime.strptime(promo_values[0][1], DATETIME_FORMAT)
        promo = Promo(
            code=promo_values[0][2],
            award=promo_values[0][3],
            date=date,
            phone=promo_values[0][0],
        )

        return promo

    @staticmethod
    def find(phone: str):
        find = Promo.find_promo(phone)
        if find:
            return find
        return None

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
        awards = [
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
        return random.choice(awards)

    def save(self):
        promo_wks.append_row(
            [self.phone, self.date.strftime(DATETIME_FORMAT), self.code, self.award]
        )
        return self
