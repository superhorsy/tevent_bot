import signal
import sys
import threading
import traceback

import bot

from app.logger import get_logger

log = get_logger(__name__)


def run_bot():
    try:
        bot.main()
    except KeyboardInterrupt:
        print("Application interrupted")
        return
    except Exception:
        traceback.print_exc()
        run_bot()
    print("Application stopped")


def repeatedly_notify_users():
    t_notifier = threading.Timer(60 * 60 * 1.0, repeatedly_notify_users)
    t_notifier.daemon = True
    t_notifier.start()
    bot.remind()


def signal_handler(signal, frame):
    print("Application exited with signal " + str(signal))
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    threads_arr = []

    t_bot = threading.Thread(target=run_bot)
    t_bot.start()
    threads_arr.append(t_bot)

    t_notification = threading.Thread(target=repeatedly_notify_users)
    t_notification.start()
    threads_arr.append(t_notification)

    # let them all start before joining
    for thr in threads_arr:
        thr.join()
