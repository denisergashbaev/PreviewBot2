from __future__ import division
import Queue
import threading

import time

import pbot

import os
import constants
from telebot.types import Message
# not in subpackage because of import problems. refactoring later...


class MyThread (threading.Thread):
    def __init__(self, message, queue):
        threading.Thread.__init__(self)
        self.message = message
        self.queue = queue

    def run(self):
        # http://stackoverflow.com/questions/5478351/python-time-measure-function
        start_time_sec = time.time()
        pbot.convert_video(self.message)
        self.queue.put(time.time() - start_time_sec)

if __name__ == '__main__':
    pbot.init(start=False)
    dir_name = constants.test_input_dir
    queue = Queue.Queue()
    threads = []
    for i, file_name in enumerate(os.listdir(dir_name)):
        file_id = constants.test_dont_cache_file_id if i % 10 == 0 else file_name
        for _ in range(10):
            json = {u'message': {
                u'date': 1478371511,
                u'document': {
                    u'file_name': file_name,
                    u'file_id': file_id,
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
            t = MyThread(message, queue)
            t.start()
            threads.append(t)

    for t in threads:
        t.join()

    for i, q in enumerate(queue.queue):
        print "request %s -> %s (s)" % (i, q)
    res = float(sum(queue.queue))
    requests_count = len(queue.queue)
    print "requests count %s" % requests_count
    print "total time (s): %s " % res
    print "average time (s): %s" % (res / requests_count)
    quit()
