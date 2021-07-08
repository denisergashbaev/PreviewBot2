import datetime

from sqlalchemy import Column, ForeignKey, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import Boolean

db_url = 'sqlite:///data/data.db'

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(String(250), unique=True)
    first_name = Column(String)
    last_name = Column(String)
    username = Column(String)
    lang = Column(String(250))


class Request(Base):
    __tablename__ = 'requests'
    id = Column(Integer, primary_key=True, autoincrement=True)
    hashcode = Column(String(40))
    input_file_id = Column(String(250))
    input_media_type = Column(String(250))
    output_file_name = Column(String(250))
    input_size = Column(Integer)
    output_size = Column(Integer)
    speed_chosen = Column(Float)
    orig_duration = Column(Float)
    # tg file_id if saved on the server
    output_file_id = Column(String(250))
    # either document or video
    output_media_type = Column(String(250))
    with_sound = Column(Boolean, default=False)
    # corresponding file deleted on hd to save space
    archived = Column(Boolean, default=False)


class UserRequest(Base):
    __tablename__ = 'user_requests'
    user_id = Column(String(250), ForeignKey('users.id'), primary_key=True)
    request_id = Column(Integer, ForeignKey('requests.id'), primary_key=True)
    update_date = Column(DateTime, default=datetime.datetime.utcnow)
    processing_time = Column(Float)
    queue_time = Column(Float)
    user = relationship(User)
    request = relationship(Request)


if __name__ == '__main__':
    # from sqlalchemy.engine import create_engine
    # Base.metadata.create_all(create_engine(db_url))
    print('''DO NOT use create_all: db schema created on run.py automatically \
     run ./bin/liquibase.sh instead''')
    exit()
