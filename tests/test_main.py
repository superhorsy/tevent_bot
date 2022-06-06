import os
from datetime import datetime

from app.utils.logger import get_logger


def test_logger():
    log = get_logger("test_log")
    log.info("tests")
    assert os.path.exists(f'../log/{datetime.now().strftime("%Y%m%d")}-test_log.log')
