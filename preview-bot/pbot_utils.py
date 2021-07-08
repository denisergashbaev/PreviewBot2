import os


# http://stackoverflow.com/questions/1392413/calculating-a-directory-size-using-python
from telegram.chataction import ChatAction


def get_dir_size(start_path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size


# give the user some feedback that video/document is being sent (good for slow connections)
def send_chat_action(bot, message, media_type):
    chat_action = ChatAction.UPLOAD_VIDEO if media_type == 'video' else ChatAction.UPLOAD_DOCUMENT
    bot.send_chat_action(message.chat.id, chat_action)
