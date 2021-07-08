# -*- coding: utf-8 -*-
from __future__ import division

import admin
import time
import functools
import logging
from shutil import copyfile

import constants
import converter
import logging_setup
import os
import telegram
from botan import botan
from cachetools.ttl import TTLCache
from concurrent.futures.thread import ThreadPoolExecutor
from concurrent.futures import TimeoutError

import psutil

import pbot_utils

from config import config
from i18n import i18n
from orm.controllers import RequestController, UserController, session_scope, get_message_media
from telegram.chataction import ChatAction
from telegram.ext import Updater, CommandHandler
from telegram.ext.callbackqueryhandler import CallbackQueryHandler
from telegram.ext.dispatcher import run_async
from telegram.ext.filters import Filters
from telegram.ext.messagehandler import MessageHandler
from telegram.ext.regexhandler import RegexHandler
from telegram.inlinekeyboardbutton import InlineKeyboardButton
from telegram.inlinekeyboardmarkup import InlineKeyboardMarkup
from telegram.update import Update

# convention
_ = i18n.ugettext

bot_name = 'PreviewRobot'
command_start = 'start'
command_language = 'language'
command_help = 'help'

logger = logging.getLogger(__name__)

API_TOKEN = config.get_token()
WEBHOOK_HOST = config.get_str('webhook_host')
WEBHOOK_PORT = config.get_str('webhook_port')  # 443, 80, 88 or 8443 (port needs to be 'open')
WEBHOOK_LISTEN = '0.0.0.0'  # In some VPS you may need to put here the IP address
WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/%s/" % API_TOKEN
WEBHOOK_SSL_CERT = constants.cert_dir + config.get_str('webhook_cert_public')
WEBHOOK_SSL_PRIV = constants.cert_dir + config.get_str('webhook_cert_private')

UPLOAD_LIMIT = 2e+7  # telegram getFile method allows only 20MB download
UPLOAD_LIMIT_TEXT = "%dMB" % (UPLOAD_LIMIT / 1000000)

workers = config.get_int('workers')
# same amount of threads for light and heavy methods
updater = Updater(API_TOKEN, workers=workers)
thread_pool_executor = ThreadPoolExecutor(max_workers=workers)

# to avoid following messages
# (connectionpool.py:667 54247b48-2055-4118-9e9e-3fa9b30c8472_3) WARNING - urllib3.connectionpool:
# "Retrying (Retry(total=2, connect=None, read=None, redirect=None)) after connection broken by
# 'ProtocolError('Connection aborted.', error(104, 'Connection reset by peer'))':
# /bot/getFile"
message_timeout = 120


def init(start):
    logging_setup.init()
    logger.setLevel(logging.DEBUG)

    admin.init()
    # initialize these handlers only after the admin handlers, so that the not_supported is not prioritized over
    # the admin ones (there is also another way to do that -> set priorities when adding the handlers)
    updater.dispatcher.add_handler(CommandHandler(command_start, send_welcome))
    updater.dispatcher.add_handler(CommandHandler(command_help, help_msg))
    updater.dispatcher.add_handler(CommandHandler(command_language, lang_prompt))
    for lang_command in i18n.lang_dict.values():
        updater.dispatcher.add_handler(RegexHandler(lang_command, select_lang))
    updater.dispatcher.add_handler(CallbackQueryHandler(evaluate_sound_option))
    updater.dispatcher.add_handler(MessageHandler(Filters.document | Filters.video, display_sound_option))
    updater.dispatcher.add_handler(MessageHandler(Filters.all, not_supported))

    if start:
        webhook = config.get_bool('webhook')
        logger.info('starting ' + 'webhook' if webhook else 'polling' + ' ...')
        if webhook:
            # https://github.com/python-telegram-bot/python-telegram-bot/wiki/Webhooks#the-integrated-webhook-server
            updater.start_webhook(listen=WEBHOOK_LISTEN,
                                  port=config.get_int('webhook_port'),
                                  url_path=API_TOKEN,
                                  key=WEBHOOK_SSL_PRIV,
                                  cert=WEBHOOK_SSL_CERT,
                                  webhook_url=WEBHOOK_URL_BASE + '/' + API_TOKEN)

            # monkey patching for the webhook server as per
            # http://stackoverflow.com/questions/40593043/add-custom-request-mapping-in-python-telegram-bot-embedded-httpserver-httpserver
            while updater.httpd is None:
                # since the webhook server is started in an extra thread, it's not available immediately
                pass
            handler = updater.httpd.RequestHandlerClass

            # wrapper for original do_GET
            def patch(get_func):
                def wrapper(self):
                    # the '/heartbeat' url is used to check if the conversion still works.
                    # for now this url can be checked with the android app called 'Network Tools'
                    # or via curl. For instance:
                    # curl --insecure -i https://lk7xficmlnz54han.myfritz.net:8443/heartbeat
                    if self.path == '/heartbeat':
                        response_code = 200 if check_status() else 500
                        self.send_response(response_code)
                        self.end_headers()
                        self.wfile.write('OK')
                    elif self.path == '/ping':
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write('pong')
                    elif self.path == '/ffmpeg-binary':
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(converter.get_ffmpeg_info())
                    elif self.path == '/ffmpeg-version':
                        import commands
                        import moviepy.config as cf
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(commands.getstatusoutput(cf.get_setting("FFMPEG_BINARY") + ' -version'))
                    else:
                        return get_func(self)

                return wrapper

            # monkey patching
            handler.do_GET = patch(handler.do_GET)
        else:
            updater.start_polling()

        admin.startup_msg()

    updater.idle()


def check_status():
    try:
        file_name = 'very_small_video.mp4'
        json = {u'message': {
            u'date': 1478371511,
            u'document': {
                u'file_name': file_name,
                u'file_id': constants.test_dont_cache_file_id,
                u'mime_type': u'video/whatever',
                u'file_size': 4731772
            },
            u'from': {
                u'username': u'test_user',
                u'first_name': u'test_user',
                u'last_name': u'test_user',
                u'id': constants.test_user_id
            },
            u'message_id': 1054,
            u'chat': {
                u'username': u'test_user',
                u'first_name': u'test_user',
                u'last_name': u'test_user',
                u'type': u'private',
                u'id': constants.test_user_id
            }
        },
            u'update_id': 100
        }
        ret_val = False
        update = Update.de_json(json, updater.bot)
        timeout = 60
        # we submit _convert_video also as a task in order to get a future which can be asked for with a timout arg
        # this way, if something goes wrong in the _convert_video (db error, deadlock, etc) we will also get notified
        # if not, then we operate on the future of the _convert_video_heavy
        future = ThreadPoolExecutor(max_workers=1).submit(_convert_video, updater.bot, update, True).result(
            timeout=timeout)
        # wait maximum 1 min for a response
        if future and future.exception(timeout=timeout) is None:
            ret_val = True
    except Exception as e:
        logger.exception(e)
        ret_val = False
    return ret_val


def log_msg(func):
    @functools.wraps(func)
    def decorator(*args, **kwargs):
        s = ' '.join(map(str, args))
        logger.debug('Entered ' + func.__name__ + '. Args: ' + s)
        result = func(*args, **kwargs)
        logger.debug('Exited ' + func.__name__ + '. Args: ' + s)
        return result

    return decorator


screencast_tg_file_id = None


@run_async
@log_msg
def send_welcome(bot, update):
    # i know it's a sin, but it's not possible to _write_ (not read) into the variable for some pythonian reason
    global screencast_tg_file_id
    message = update.message
    with session_scope() as session:
        lang = user_lang(message, session)
        if not lang:
            return _lang_prompt(bot, update)

        logger.info("sending welcome")
        # use last commit id to know which version is running
        # http://stackoverflow.com/questions/14989858/get-the-current-git-hash-in-a-python-script
        # don't access git repo cause not working in production docker
        # version = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).strip()

        # did not find out how to create newline in resource bundle
        welcome = _(lang, "welcome1") % bot_name
        welcome += '\n\n' + _(lang, "welcome2") % UPLOAD_LIMIT_TEXT
        welcome += '\n\n' + _(lang, "help") % '/' + command_help

        try:
            message.reply_text(welcome, parse_mode=telegram.ParseMode.MARKDOWN)
        except Exception as e:
            logger.exception(e)
            # there is an exception in logs, but i cannot trace it down, therefore more logging here
            logger.error("translation used for language %s: %s" % (lang, welcome))
        caption = _(lang, "screencastDesc")
        if screencast_tg_file_id:
            message.reply_video(video=screencast_tg_file_id, caption=caption)
        else:
            with open('how-to-vid.mp4', 'rb') as v:
                msg = message.reply_video(video=v, caption=caption)
                # after having sent the video, we want to persist its tg id and media type
                # to not have to send it next time
                for mt in ['document', 'video']:
                    if getattr(msg, mt):
                        screencast_tg_file_id = getattr(msg, mt).file_id
                        break


@run_async
@log_msg
def help_msg(bot, update):
    message = update.message
    with session_scope() as session:
        lang = user_lang(message, session)
        msg = _(lang, "support") % "previewrobot@gmail.com".encode('utf8')
        msg += '\n' + _(lang, "start") % '/' + command_start.encode('utf8')
        msg += '\n' + _(lang, "languageSelection") % '/' + command_language.encode('utf8')
        message.reply_text(msg)
    botan.track_action(update.message, '/' + command_help)


@run_async
@log_msg
def lang_prompt(bot, update):
    _lang_prompt(bot, update)


# to avoid double @run_async
def _lang_prompt(bot, update):
    custom_keyboard = [[]]
    for i, v in enumerate(i18n.lang_dict.values()):
        try:
            # 2 langs per row
            custom_keyboard[int(i / 2)].append(v)
        except IndexError:
            custom_keyboard.append([v])
    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True, one_time_keyboard=True)
    msgs = []
    # show this message in all available languages
    for k in i18n.lang_dict.keys():
        v = _(k, 'selectLanguage')
        if v not in msgs:
            msgs.append(v)
    update.message.reply_text('\n'.join(msgs), reply_markup=reply_markup)


@run_async
@log_msg
def select_lang(bot, update):
    message = update.message
    with session_scope() as session:
        user_ctr = UserController(session)
        tg_user_id = message.from_user.id
        new_user = user_ctr.get_by_tg_id(tg_user_id) is None
        for lang_code, lang in i18n.lang_dict.items():
            if lang == message.text:
                user_ctr.set_lang(tg_user_id, lang_code)
                update.message.reply_text(_(lang_code, 'languageSelected'))
                break
        # put the lang codes, so that it's properly visible in botan
        botan.track_action(message, 'Lang: ' + i18n.inverse_lang_dict[message.text])
        # show welcome message for first-time customers, otherwise it's just a user changing their language
        if new_user:
            send_welcome(bot, update)


def get_file(bot, message_media, tg_file_id, real_user):
    """
    This method is used to get file info for real telegram users and also test cases
    :param message_media: either document or video
    :param tg_file_id: telegram unique identification
    :param real_user: True means that we a dealing with a real file upload/forward
    and fetching the file info (url, name) via the telegram API. Otherwise, the user is fake (that is created for the
    test), and, therefore, the API cannot be used and we just give back the provided file name and file url with the
    same value
    :return: file url, file name
    """
    if real_user:
        file_url = bot.get_file(tg_file_id, timeout=message_timeout).file_path
        file_name = os.path.basename(file_url)
    else:
        file_name = file_url = message_media.file_name
    return file_url, file_name


@run_async
@log_msg
def convert_document(bot, update, with_sound):
    message = update.message
    doc = message.document
    if doc:
        # we should limit this list as we test more file formats
        # ['video/quicktime', 'video/mp4', 'video/3gpp'] -- tried these ones
        # endsWith because of test/test_input/walking.MOV (telegram does not identify it's mime_type)
        extensions = ('.mov')
        if doc.mime_type and doc.mime_type.startswith('video/') \
                or doc.file_name.lower().endswith(extensions):
            return _convert_video(bot, update, with_sound)
    return not_supported(bot, update)


# keep items for 10 mins in cache
cache = TTLCache(10000, ttl=60 * 10)


def display_sound_option(bot, update):
    update_id = str(update.update_id)
    cache[update_id] = update
    with session_scope() as session:
        lang = user_lang(update.message, session)
        button_list = [
            [InlineKeyboardButton(_(lang, 'sound.without_sound'), callback_data='sound.without_sound:' + update_id),
             InlineKeyboardButton(_(lang, 'sound.with_sound'), callback_data='sound.with_sound:' + update_id)]
        ]
        reply_markup = InlineKeyboardMarkup(button_list, n_cols=2)
        update.message.reply_text(_(lang, 'sound.question'), reply_markup=reply_markup)


def forward_to_convert(bot, update, with_sound):
    convert_video(bot, update, with_sound) if update.message.video else convert_document(bot, update, with_sound)


def evaluate_sound_option(bot, update):
    sound_option, prev_update_id = update.callback_query.data.split(':')
    with session_scope() as session:
        lang = user_lang(update.callback_query, session)
        try:
            prev_update = cache[prev_update_id]
            update.callback_query.edit_message_text(_(lang, sound_option))
            return forward_to_convert(bot, prev_update, 'sound.with_sound' == sound_option)
        except KeyError:
            # cache item expired
            update.callback_query.edit_message_text(_(lang, 'sound.expired'))


@run_async
@log_msg
def convert_video(bot, update, with_sound):
    # initially, support all video types. may be changed later
    _convert_video(bot, update, with_sound)


@log_msg
def _convert_video(bot, update, with_sound):
    future = None
    try:
        tic = time.time()
        message = update.message
        real_user = message.from_user.id != constants.test_user_id
        with session_scope() as session:
            lang = user_lang(message, session)
            # short names so that the legend is visible in botan
            track_msg = 'r'
            message_media = get_message_media(message)[0]
            input_file_id = message_media.file_id
            logger.debug("received video: " + input_file_id)
            if message_media.file_size <= UPLOAD_LIMIT:
                reply_msg = None
                # special request controller which returns cached results
                req_ctr = RequestController(session)
                # first check if file is cached by url
                # (no need to download the original file in case of forwards).
                # If not, download the file and check if it is cached by hashcode
                # (no need to process the file in case of same uploads).
                request = req_ctr.get_cached_by_input_file_id(input_file_id, with_sound=with_sound, real_user=real_user)
                if real_user:
                    reply_msg = message.reply_text(_(lang, 'status.downloading' if request else 'status.inQueue'),
                                                   disable_notification=True)
                if request:
                    logger.debug(cached_prefix(request) + "downloading video " + input_file_id)
                    req_ctr.add_user_request(message, request, time.time() - tic, 0)
                    send_file(bot, real_user, message_media, lang, message, reply_msg, request, req_ctr)
                    track_convert_file(message, track_msg, real_user)
                else:
                    # since it's a long-running task. submit it to a ThreadPool. This way the bot stays responsive
                    # for all other lightweight commands while taking care of the heavy tasks
                    future = thread_pool_executor.submit(_convert_video_heavy, bot, update, with_sound, reply_msg,
                                                         real_user,
                                                         tic)
            else:
                logger.warn("Upload file is %s " % message_media.file_size)
                if real_user:
                    message.reply_text(_(lang, 'error.filesize') % UPLOAD_LIMIT_TEXT)
                    track_convert_file(message, 'too_large', real_user)

    except Exception as e:
        # just in case an exception happens somewhere in except block or afterwards (ie, on file deletion)
        logger.exception(e)
    return future


@log_msg
def _convert_video_heavy(bot, update, with_sound, reply_msg, real_user, queue_time):
    try:
        message = update.message
        tic = time.time()
        queue_time = time.time() - queue_time
        bot = updater.bot
        message_media = get_message_media(message)[0]
        input_file_id = message_media.file_id
        track_msg = 'r-d'
        input_file_path = None
        output_file_name = None

        with session_scope() as session:
            lang = user_lang(message, session)
            try:
                req_ctr = RequestController(session)

                if real_user:
                    if req_ctr.is_throttle_reached(message):
                        bot.edit_message_text(_(lang, 'status.throttled'), message.chat.id, reply_msg.message_id)
                        logger.debug("throttled this request: " + input_file_id)
                        botan.track_action(message, 'throttled')
                        return
                    bot.edit_message_text(_(lang, 'status.downloading'), message.chat.id,
                                          reply_msg.message_id)
                furl, fname = get_file(bot, message_media, input_file_id, real_user=real_user)
                input_file_path = converter.download_and_save(furl, fname, real_user=real_user)
                request = req_ctr.get_cached_by_hash(input_file_path, with_sound=with_sound, real_user=real_user)
                output_file_name = os.path.basename(input_file_path)
                logger.debug(cached_prefix(request) + "processing video " + input_file_id)
                if request:
                    output_file_name = request.output_file_name
                else:
                    track_msg += '-c'
                    if real_user:
                        bot.edit_message_text(_(lang, 'status.processing'), message.chat.id,
                                              reply_msg.message_id)
                    # use ThreadPoolExecutor with one thread in a blocking manner in order to enforce a timeout
                    # increased timeout because of the errors in logs and a coming cc docker image
                    ThreadPoolExecutor(max_workers=1).submit(converter.process_file, input_file_path,
                                                             with_sound).result(timeout=180)
                    if real_user:
                        request = req_ctr.add(message, input_file_id, output_file_name, with_sound)

                if real_user:
                    req_ctr.add_user_request(message, request, time.time() - tic, queue_time)
                    send_file(bot, real_user, message_media, lang, message, reply_msg, request, req_ctr)
                    req_ctr.cleanup()  # this cleans the cache if the threshold is reached.

            except Exception as e:
                if isinstance(e, TimeoutError):
                    for proc in psutil.process_iter():
                        if input_file_path in proc.cmdline():
                            proc.kill()
                            break

                # copy files that could not be converted for later analysis
                dir_size_mb = pbot_utils.get_dir_size(constants.err_input_dir) // 1000 // 1000
                if input_file_path and dir_size_mb < 1000:
                    copyfile(input_file_path, constants.err_input_dir + os.path.basename(input_file_path))

                if real_user:
                    message.reply_text(_(lang, 'error.processing') % output_file_name)
                # http://stackoverflow.com/questions/5191830/best-way-to-log-a-python-exception
                logger.error("Problematic message: " + str(message))
                logger.exception(e)
                track_msg += '-e'

        track_convert_file(message, track_msg, real_user)
        botan.track_action(update.message, 'with_sound' if with_sound else 'without_sound')
        if input_file_path:
            os.remove(input_file_path)
        if output_file_name and not real_user:
            os.remove(constants.output_dir + output_file_name)
        for f in os.listdir(constants.downloads_dir):
            f_path = os.path.join(constants.downloads_dir, f)
            # remove all files older than 1 day
            # (the downloads folder may get trashed in case the container is restarted prior to clean-up)
            if os.stat(f_path).st_mtime < time.time() - 86400:
                os.remove(f_path)

    except Exception as e:
        logger.exception(e)
        # reraise the exception so that it lands inside of the future
        raise


def track_convert_file(msg, track_msg, real_user):
    if real_user:
        botan.track_action(msg,
                           str(msg.from_user.id) + ':' + msg.from_user.username if msg.from_user else 'unknown_user')
        botan.track_action(msg, track_msg)
        botan.track_action(msg, 'forward' if msg.forward_from or msg.forward_from_chat else 'upload')


def user_lang(message, session):
    return UserController(session).get_lang(message.from_user.id)


def cached_prefix(request):
    return "(cached) " if request else ""


def send_file(bot, real_user, message_media, lang, message, reply_msg, request, req_ctr):
    if real_user:
        vfile_path = str(constants.output_dir + request.output_file_name)
        compressed_times = str(int(message_media.file_size / os.stat(vfile_path).st_size))
        vfile_caption = _(lang, "doneBy") % ('@' + bot_name, compressed_times)
        bot.edit_message_text(_(lang, 'status.done'), message.chat.id, reply_msg.message_id)

        send_cached = request and request.output_media_type

        if send_cached:
            try:
                media_type = request.output_media_type
                pbot_utils.send_chat_action(bot, message, media_type)
                func_name = getattr(bot, 'send_' + media_type)
                func_name(message.chat.id, request.output_file_id, caption=vfile_caption)
            except Exception as e:
                logger.exception(e)
                send_cached = False

        if not send_cached:
            with open(vfile_path, 'rb') as vfile:
                pbot_utils.send_chat_action(bot, message, 'video')
                msg = bot.send_video(chat_id=message.chat.id, video=vfile, timeout=message_timeout,
                                     caption=vfile_caption)
                # after having sent the video, we want to persist its tg id and media type
                # to not have to send it next time
                req_ctr.set_output_file_id(request.id, msg)


@run_async
@log_msg
def not_supported(bot, update):
    message = update.message
    with session_scope() as session:
        lang = user_lang(message, session)
        message.reply_text(_(lang, 'error.unsupported'))
    botan.track_action(update.message, not_supported.__name__)
