# ----------------
# dont forget 'pip install requests' first
# ----------------
# usage example:
#
# import botan
#
# print botan.track(1111, 1, {'text':2}, 'Search')

import requests
import json
from config import config
import logging

TRACK_URL = 'https://api.botan.io/track'
SHORTENER_URL = 'https://api.botan.io/s/'

logger = logging.getLogger(__name__)


def _track(token, uid, message, name='Message'):
    try:
        requests.post(
            TRACK_URL,
            params={"token": token, "uid": uid, "name": name},
            data=json.dumps(message),
            headers={'Content-type': 'application/json'},
        )
        # don't use 'grequests'!!! it leads to the following error on video conversion OR /test:
        # 2016-11-01T20:50:08 preview-bot docker/preview-bot[24292]:
        # TypeError: child watchers are only available on the default loop
        #
        # http://stackoverflow.com/questions/16015749/in-what-way-is-grequests-asynchronous
        # grequests.send(req, grequests.Pool(1))
    except Exception as e:
        logger.exception(e)


def shorten_url(url, user_id):
    """
    Shorten URL for specified user of a bot
    """
    try:
        return requests.get(SHORTENER_URL, params={
            'token': config.get_str('botan_token'),
            'url': url,
            'user_ids': str(user_id),
        }).text
    except Exception as e:
        logger.exception(e)
        return url


def track_action(msg, event):
    """
    Use track_action as the last call, because it's synchronous
    """
    def user2dic(msg, field):
        return const_dict(msg, field,  ['id', 'first_name', 'last_name', 'username'])

    def const_dict(msg, key, args):
        d = {}
        t = getattr(msg, key)
        if not t:
            return d
        for arg in args:
            d[arg] = getattr(t, arg) if t else None
        return d

    _track(config.get_str('botan_token'), msg.from_user.id, {
        'message_id': msg.message_id,
        'from_user': user2dic(msg, 'from_user'),
        'chat': const_dict(msg, 'chat',  ['id', 'type', 'last_name', 'first_name', 'username', 'title']),
        'forward_from': user2dic(msg, 'forward_from'),
        'forward_date': str(msg.forward_date),
        'document': const_dict(msg, 'document', ['file_id', 'file_name', 'mime_type', 'file_size']),
        'video': const_dict(msg, 'video', ['file_id', 'width', 'height', 'duration', 'mime_type', 'file_size']),
    }, event)
