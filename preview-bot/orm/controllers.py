import hashlib
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta

import classes
import pbot_utils
import constants
import os
from classes import UserRequest, User, Request
from config import config
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy.engine import create_engine
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.sql.elements import Tuple, and_
from sqlalchemy.sql.expression import update

logger = logging.getLogger(__name__)

# http://docs.sqlalchemy.org/en/latest/core/pooling.html
# See db session pool discussion here:
# http://stackoverflow.com/questions/40141515/sqlalchemy-pytelegrambotapi-sqlite-objects-created-in-a-thread-can-only-be-us
Session = sessionmaker(bind=create_engine(classes.db_url, poolclass=NullPool))


def get_message_media(message):
    return (message.document, 'document') if message.document else (message.video, 'video')


# from: http://docs.sqlalchemy.org/en/latest/orm/session_basics.html#session-faq-whentocreate
@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


class RequestController(object):
    # this should manage requests as messages
    def __init__(self, dbsession):
        self.session = dbsession
        self.user_mgr = UserController(dbsession)

    @staticmethod
    def _throttle_subquery(query, msg):
        throttle_time = datetime.utcnow() - timedelta(hours=config.get_int('throttle_timeout'))
        query = query.join(UserRequest.user).filter(
            User.telegram_id == msg.from_user.id,
            UserRequest.update_date > throttle_time)
        return query

    def is_throttle_reached(self, msg):
        # ignore throttling for admins
        if str(msg.from_user.id) in config.get_str("admin_ids"): return False

        reqs_limit = config.get_int('throttle_num_requests')
        # select count(*) from user_requests join user on user_requests.user_id=users.id
        # where users.telegram_id='[telegram_id]' and user_requests.update_date>'[throttle_time]';
        reqs_total = RequestController._throttle_subquery(self.session.query(func.count(UserRequest.user_id)),
                                                          msg).scalar()
        return reqs_total >= reqs_limit

    def clear_throttle(self, msg):
        # select * from user_requests join user on user_requests.user_id=users.id
        # where users.telegram_id='[telegram_id]' and user_requests.update_date>'[throttle_time]';
        user_requests = RequestController._throttle_subquery(self.session.query(UserRequest), msg).all()
        for u_r in user_requests:
            u_r.update_date = datetime.min
            self.session.commit()

    # this returns a 40-char hash digest for any file
    @staticmethod
    def digest(file_path):
        blocksize = 2 ** 16
        hasher = hashlib.sha1()
        with open(file_path, 'rb') as f:
            buf = f.read(blocksize)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(blocksize)
        return hasher.hexdigest()

    def get_by_id(self, id):
        return self.session.query(Request).filter(Request.id == id).first()

    def get_cached_by_input_file_id(self, input_file_id, with_sound, real_user=True):
        result = self.session.query(Request).filter(
            and_(Request.input_file_id == input_file_id, Request.with_sound == with_sound,
                 Request.archived == False)).first()
        return RequestController._safe_return(result, real_user)

    def get_cached_by_hash(self, file_path, with_sound, real_user=True):
        result = self.session.query(Request).filter(and_(Request.hashcode == RequestController.digest(file_path),
                                                         Request.with_sound == with_sound,
                                                         Request.archived == False)).first()
        return RequestController._safe_return(result, real_user)

    def get_by_output_file_name(self, file_name):
        return self.session.query(Request).filter(Request.output_file_name == file_name).first()

    def get_file_stats(self, start_date, finish_date):
        # SELECT requests.id AS requests_id,
        # requests.hashcode AS requests_hashcode, requests.input_file_id AS requests_input_file_id,
        # requests.input_media_type AS requests_input_media_type,
        # requests.output_file_name AS requests_output_file_name,
        # requests.input_size AS requests_input_size, requests.output_size AS requests_output_size,
        # requests.speed_chosen AS requests_speed_chosen, requests.orig_duration AS requests_orig_duration,
        # requests.output_file_id AS requests_output_file_id, requests.output_media_type AS requests_output_media_type,
        # count(requests.id) AS count_1
        # FROM requests JOIN user_requests ON requests.id = user_requests.request_id
        # WHERE user_requests.update_date >= :update_date_1 AND user_requests.update_date < :update_date_2
        # GROUP BY requests.id ORDER BY count(requests.id) DESC, requests.id DESC
        files = self.session.query(Request, func.count(Request.id)).join(UserRequest). \
            filter(UserRequest.update_date >= start_date).filter(UserRequest.update_date < finish_date).group_by(
            Request.id).order_by(desc(func.count(Request.id)), desc(Request.id)).all()
        return files

    # return file _only_ if present both in db AND on the disk
    @staticmethod
    def _safe_return(result, real_user):
        return result if real_user and result and os.path.isfile(constants.output_dir + result.output_file_name) \
            else None

    def add(self, msg, input_file_id, file_name, with_sound):
        message_media, media_type = get_message_media(msg)
        ipath = constants.downloads_dir + file_name
        opath = constants.output_dir + file_name
        # duration and chosen speed are not set, need to make corresponding
        # data available in moviepy-based compressor
        request = Request(input_file_id=input_file_id,
                          input_media_type=media_type,
                          hashcode=RequestController.digest(ipath),
                          output_file_name=file_name,
                          input_size=os.path.getsize(ipath),
                          output_size=os.path.getsize(opath),
                          with_sound=with_sound)

        self.session.add(request)
        self.session.commit()
        return request

    def add_user_request(self, message, request, processing_time, queue_time):
        user = self.user_mgr.update_user(message.from_user)
        user_request = self.session.query(UserRequest).filter(UserRequest.user_id == user.id,
                                                              UserRequest.request_id == request.id).first()
        if not user_request:
            user_request = UserRequest(request=request, user=user)

        user_request.update_date = datetime.utcnow()
        user_request.processing_time = processing_time
        user_request.queue_time = queue_time

        # .add() also updates: https://groups.google.com/forum/#!topic/sqlalchemy/ukM3UbHI5KA
        self.session.add(user_request)
        self.session.commit()

    def set_output_file_id(self, request_id, output_msg):
        message_media, media_type = get_message_media(output_msg)
        self.session.execute(
            update(Request).where(Request.id == request_id).values(output_file_id=message_media.file_id,
                                                                   output_media_type=media_type)
        )
        self.session.commit()

    # implements LRU cleanup for requests
    def cleanup(self):
        cache_to_clean = 2 ** 30 * 2  # 2 GBs, int(config.get('cache_to_clean'))
        cache_threshold = 2 ** 30 * 5  # 5 GBs, int(config.get('cache_threshold'))

        total_size_bytes = pbot_utils.get_dir_size(constants.output_dir)

        if total_size_bytes > cache_threshold:
            deleted_size = 0
            # clean the 'orphan' files that may have resulted due to container restarts
            # http://stackoverflow.com/questions/237079/how-to-get-file-creation-modification-date-times-in-python
            for file_name in (f for f in os.listdir(constants.output_dir)
                              if os.path.isfile(os.path.join(constants.output_dir, f))):
                if not self.get_by_output_file_name(file_name):
                    try:
                        file_path = os.path.join(constants.output_dir, file_name)
                        deleted_size += os.path.getsize(file_path)
                        os.remove(file_path)
                        logger.warning('Cleaning orphan file %s' % file_path)
                    except OSError, e:
                        logger.exception(e)
            lru_reqs = self.session.query(Request, func.max(UserRequest.update_date)). \
                filter(and_(Request.id == UserRequest.request_id, Request.archived is False)). \
                group_by(Request). \
                order_by(UserRequest.update_date). \
                all()

            for r in lru_reqs:
                if deleted_size >= cache_to_clean:
                    break
                request = r[0]
                try:
                    # mark as archived and commit from db first,
                    # so that the next request does not try to search for a file
                    # that is in the database but not on disk
                    # (archiving instead of deleting so that pk allocation does not start anew, temp solution)
                    # if we're gonna delete/move the requests in the future, user_requests MUST be synced as well
                    request.archived = True
                    self.session.add(request)
                    os.remove(os.path.join(constants.output_dir, request.output_file_name))
                    deleted_size += request.output_size
                    self.session.commit()
                except OSError, e:
                    logger.exception(e)


class UserController(object):
    def __init__(self, dbsession):
        self.session = dbsession

    def get_by_id(self, user_id):
        return self.session.query(User).filter(User.id == user_id).first()

    def get_by_tg_id(self, tg_user_id):
        return self.session.query(User).filter(User.telegram_id == tg_user_id).first()

    def add_user(self, tg_user_id):
        user = self.get_by_tg_id(tg_user_id)
        if not user:
            user = User(telegram_id=tg_user_id)
            self.session.add(user)
            self.session.commit()
        return user

    def update_user(self, from_user):
        user = self.add_user(from_user.id)
        user.first_name = from_user.first_name
        user.last_name = from_user.last_name
        user.username = from_user.username
        # .add() also updates: https://groups.google.com/forum/#!topic/sqlalchemy/ukM3UbHI5KA
        self.session.add(user)
        self.session.commit()
        return user

    def get_user_stats(self, start_date, finish_date):
        users = self.session.query(User, func.count(UserRequest.user_id)).join(UserRequest). \
            filter(UserRequest.update_date >= start_date).filter(UserRequest.update_date < finish_date).group_by(
            User.id).order_by(desc(func.count(UserRequest.user_id)), desc(User.id)).all()
        return users

    def get_lang(self, tg_user_id):
        user = self.get_by_tg_id(tg_user_id)
        return user.lang if user else None

    def set_lang(self, tg_user_id, lang):
        user = self.add_user(tg_user_id)
        user.lang = lang
        self.session.add(user)
        self.session.commit()
