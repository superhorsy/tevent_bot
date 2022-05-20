import os
from datetime import datetime


def test_logger():
    from app.logger import get_logger

    log = get_logger("test_log")
    log.info("test")
    assert os.path.exists(f'../log/{datetime.now().strftime("%Y%m%d")}-test_log.log')
