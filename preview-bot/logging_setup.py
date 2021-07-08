import logging
import sys
from logging.handlers import TimedRotatingFileHandler


def init():
    # file_handler = TimedRotatingFileHandler('logs/preview-bot.log', when='midnight')
    formatter = logging.Formatter(
        '%(asctime)s (%(filename)s:%(lineno)d %(threadName)s) %(levelname)s - %(name)s: "%(message)s"')
    # file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    handlers = [stream_handler]
    root = logging.getLogger()
    # setting DEBUG so (almost) everything is logged
    root.setLevel(logging.NOTSET)
    for handler in handlers:
        root.addHandler(handler)
    return handlers

