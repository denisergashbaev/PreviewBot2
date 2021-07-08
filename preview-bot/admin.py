import datetime
from dateutil import tz

import functools

import pbot
import pbot_utils
import constants
import converter
import os
from config import config
from orm.controllers import RequestController, UserController, session_scope
from telegram.ext.commandhandler import CommandHandler
from telegram.ext.dispatcher import run_async
from telegram.ext.regexhandler import RegexHandler
from telegram.update import Update
from dateutil.parser import parse

command_ping = 'ping'
command_test = 'test'
command_clear_throttle = 'clear_throttle'
command_stats = 'stats'

admin_ids = config.get_int_list('admin_ids')


def startup_msg():
    for admin_id in admin_ids:
        try:
            pbot.updater.bot.send_message(chat_id=admin_id,
                                          text="Admin: starting up the bot (%s)" % datetime.datetime.now().replace(
                                             microsecond=0))
        except Exception:
            # could happen if one of the users has not added/blocked the bot
            pass


def is_admin(update):
    return update.message.from_user.id in admin_ids


# allows only admins to execute certain commands
def auth(func):
    @functools.wraps(func)
    def decorator(*args, **kwargs):
        admin = False
        for arg in args:
            if isinstance(arg, Update):
                admin = is_admin(arg)
                break
        result = func(*args, **kwargs) if admin else pbot.not_supported(*args, **kwargs)
        return result

    return decorator


@run_async
@auth
def test(bot, update):
    dir_name = constants.test_input_dir
    for input_file in os.listdir(dir_name):
        update.message.reply_text("Processing file %s" % input_file)
        output_file_name = converter.process_file(os.path.join(dir_name, input_file))
        # 'r' open file in reading mode, 'b' for binary
        with open(output_file_name, 'rb') as output_file:
            update.message.reply_video(output_file, timeout=bot.message_timeout)


@run_async
@auth
def ping(bot, update):
    update.message.reply_text('pong')


@run_async
@auth
def stats(bot, update):
    with session_scope() as session:
        # so we get the stats command in the following form
        # /stats [date_from] [date_to]
        # therefore trim it firsthand, checking for optional arguments afterdards
        text = update.message.text.strip()
        tokens = text.split(' ')
        d1 = parse(tokens[1]) if len(tokens) >= 2 else datetime.datetime.utcnow().date()
        start = datetime.datetime(d1.year, d1.month, d1.day, tzinfo=tz.tzutc())
        d2 = parse(tokens[2]) if len(tokens) >= 3 else start + datetime.timedelta(days=1)
        finish = datetime.datetime(d2.year, d2.month, d2.day, tzinfo=tz.tzutc())

        limit = 20
        rc = RequestController(session)
        files = rc.get_file_stats(start, finish)
        total_request_count = 0
        msg_requests = []
        start_formatted = start.strftime('%Y-%m-%d %M:%S')
        finish_formatted = finish.strftime('%Y-%m-%d %M:%S')
        for idx, f in enumerate(files):
            request, count = f
            total_request_count += count
            if idx < limit:
                msg_requests.append('/request_%s - count: %s' % (request.id, count))

        msg_summary = 'Total requests between %s and %s: %s' % (start_formatted, finish_formatted, total_request_count)
        uc = UserController(session)
        users = uc.get_user_stats(start, finish)
        msg_users = []
        for idx, u in enumerate(users):
            user, count = u
            if idx < limit:
                msg_users.append('/user_%s - requests: %s' % (user.id, count))

        msg_summary += '\nTotal users between %s and %s: %s' % (start_formatted, finish_formatted, len(users))

        update.message.reply_text(msg_summary)
        if len(msg_requests):
            p = 'Showing first %s items\n' % limit
            update.message.reply_text(p + '\n'.join(msg_requests))
        if len(msg_users):
            p = 'Showing first %s items\n' % limit
            update.message.reply_text(p + '\n'.join(msg_users))


@run_async
@auth
def stats_request(bot, update):
    # sample input: /request_123
    # so we parse this command to determine the request_id and get it from the database
    # input_media_type is needed, because we are sending the video/document by the telegram id (no upload from our side)
    # in this case we can only use the same media type as was originally determined by telegram
    with session_scope() as session:
        message = update.message
        request_id = message.text.split('_')[1]
        request = RequestController(session).get_by_id(request_id)
        if request:
            pbot_utils.send_chat_action(bot, message, request.input_media_type)
            func_name = getattr(message, 'reply_' + request.input_media_type)
            func_name(request.input_file_id)
        else:
            message.reply_text('No info available')


@run_async
@auth
def user_request(bot, update):
    # sample input: /user_123
    # so we parse this command to determine the user_id and get it from the database
    with session_scope() as session:
        message = update.message
        user_id = message.text.split('_')[1]
        user = UserController(session).get_by_id(user_id)
        if user:
            msg = "id: %s\ntg_id: %s \nfirst_name: %s \nlast_name: %s \nusername: @%s \nlang: %s" % (
                user.id, user.telegram_id, user.first_name, user.last_name, user.username if user.username else '',
                user.lang)
        else:
            msg = 'No info available'
        message.reply_text(msg)


@run_async
@auth
def clear_throttle(bot, update):
    with session_scope() as session:
        RequestController(session).clear_throttle(update.message)


def init():
    pbot.updater.dispatcher.add_handler(CommandHandler(command_test, test))
    pbot.updater.dispatcher.add_handler(CommandHandler(command_ping, ping))
    pbot.updater.dispatcher.add_handler(CommandHandler(command_clear_throttle, clear_throttle))
    pbot.updater.dispatcher.add_handler(CommandHandler(command_stats, stats))
    pbot.updater.dispatcher.add_handler(RegexHandler('/request_*', stats_request))
    pbot.updater.dispatcher.add_handler(RegexHandler('/user_*', user_request))
