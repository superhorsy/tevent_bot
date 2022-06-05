import configparser
import re
from datetime import datetime

from telebot import TeleBot, apihelper, types

import app.bot.messages as msg
from app.bot.antispam_middlware import antispam_func
from app.model.promo import DATETIME_FORMAT, Promo
from app.model.users import User, UserNotFoundError
from app.utils.google_tables import users_wks
from app.utils.logger import get_logger
from app.utils.mongo_db import users

# Logger
log = get_logger(__name__)
# Bot
apihelper.ENABLE_MIDDLEWARE = True
# Config
conf = configparser.ConfigParser()
conf.read("config/config.ini")
bot = TeleBot(conf["bot"]["token"], num_threads=5)
# Middlewares
bot.register_middleware_handler(antispam_func, update_types=["message"])


def _notify(user: User):
    log.info(f"Notifying user {user.chat_id} /{user.phone}/")
    _send(msg.REMINDER, user.chat_id)
    user.notifications.insert(0, datetime.now().strftime(DATETIME_FORMAT))
    users.set(user)
    log.info("User notified")


def remind():
    log.info("Reminder started")
    user_list = users.keys()
    for user_id in user_list:
        log.info(f"Notifying chat: {user_id}")
        try:
            user: User = users.get(user_id)
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
        log.info(
            f"Current date is {datetime.now()}, next date is {last_promo.next_date()}"
        )
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
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if users.exists(chat_id):
        markup.add(types.KeyboardButton("🎲"))
        markup.add(types.KeyboardButton("Выйти"), row_width=2)
    markup.add(types.KeyboardButton("Справка"))
    clear_mess = mess.replace("\n", "")
    log.info(f"Chat: {chat_id}, message: {clear_mess}")
    bot.send_message(chat_id, mess, parse_mode="html", reply_markup=markup)


def main():
    def logout(message):
        users.delete(str(message.chat.id))
        start(message)

    @bot.message_handler(commands=["help"])
    def show_help(message: types.Message):
        _send(msg.HELP, message.chat.id)

    @bot.message_handler(commands=["start"])
    def start(message: types.Message):
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
    def login(message: types.Message):
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

        find = users_wks.find(in_column=7, query=re.compile(search))
        if find is None:
            _send(f"Номер телефона не найден. \n{msg.NOT_LOGGED_IN}", message.chat.id)
            return
        values: list = users_wks.row_values(find.row)
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
        last_promo: Promo = Promo.find(user.phone)

        if last_promo and last_promo.is_valid():
            log.info(
                f"User {user.chat_id} /{user.phone}/ has valid promo {last_promo.code}"
            )
            _send(
                f"Текущий промокод: \n"
                f"🎫 Награда - {last_promo.award} \n"
                f"🏷 Выдан {last_promo.date.strftime(DATETIME_FORMAT)} (МСК) \n"
                f"🔐 Код {last_promo.code} \n",
                user.chat_id,
            )
            _send(
                f"Новый промокод будет доступен {last_promo.next_date().strftime(DATETIME_FORMAT)}.",
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
    def text_helper(message: types.Message):
        if bot.temp_data and bot.temp_data.get(message.from_user.id) != "OK":
            return
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
