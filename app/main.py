import signal
import sys
import threading
import traceback

import bot
from logger import get_logger

log = get_logger("main_thr")

REMIND_TIME_INTERVAL = 60 * 60 * 1.0
# REMIND_TIME_INTERVAL = 20


def run_bot():
    try:
        log.info("Application started")
        bot.main()
    except KeyboardInterrupt:
        log.warning("Application interrupted")
        exit(0)
    except Exception:
        traceback.print_exc()
        run_bot()
    log.info("Application stopped")


def repeatedly_notify_users():
    t_notifier = threading.Timer(REMIND_TIME_INTERVAL, repeatedly_notify_users)
    t_notifier.daemon = True
    t_notifier.start()
    bot.remind()


def signal_handler(signal, _):
    log.info(f"Application exited with signal {str(signal)}")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    t_bot = threading.Thread(target=run_bot, name="Bot")
    t_bot.start()
    threads_arr = [t_bot]
    t_notification = threading.Thread(target=repeatedly_notify_users, name="Notifier")
    t_notification.start()
    threads_arr.append(t_notification)

    # let them all start before joining
    for thr in threads_arr:
        thr.join()
