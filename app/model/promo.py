import random
import string
from datetime import datetime, timedelta

import gspread
from retry import retry
from utils.google_tables import promo_wks

PROMO_EXPIRY_INTERVAL = 3
DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"


class Promo:
    def __init__(
        self,
        phone: str,
        code: str = None,
        award: str = None,
        date: datetime = None,
    ) -> None:
        if not award:
            award = Promo.__generate_award()
        self.award = award
        if not code:
            code = Promo.__generate_code()
        self.code = code
        if not date:
            date = datetime.now()
        self.date = date
        self.phone = phone

    def __str__(self):
        return f"code: {self.code}, date: {self.date}, phone: {self.phone}"

    def is_valid(self):
        return datetime.now() < self.next_date()

    def next_date(self) -> datetime:
        return self.date + timedelta(days=PROMO_EXPIRY_INTERVAL)

    @staticmethod
    @retry(exceptions=gspread.exceptions.APIError, tries=5, delay=10)
    def find(phone: str):
        """row: 0 - phone, 1 - date, 2 - code, 3 - award"""
        all_promos = promo_wks.get()
        promos_with_phone = [promo for promo in all_promos if promo[0] == phone]
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
