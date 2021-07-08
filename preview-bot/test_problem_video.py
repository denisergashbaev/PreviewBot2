from __future__ import division
import pbot

import constants
from telebot.types import Message
# not in subpackage because of import problems. refactoring later...

def test_conversion():
    pbot.init(start=False)
    dir_name = constants.test_input_dir
    file_name = "cars.mp4"
    json = {u'message': {
        u'date': 1478371511,
        u'document': {
            u'file_name': file_name,
            u'file_id': file_name,
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

    message = Message.de_json(json[u'message'])
    pbot.convert_video(message)