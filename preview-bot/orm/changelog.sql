--liquibase formatted sql

--changeset ergashbaev:1
CREATE TABLE requests
(
    id INTEGER PRIMARY KEY NOT NULL,
    hashcode TEXT,
    output_file_name TEXT,
    input_size INTEGER,
    output_size INTEGER,
    speed_chosen REAL,
    orig_duration REAL,
    with_sound INTEGER,
    archived INTEGER
);
CREATE TABLE user_requests
(
    user_id TEXT NOT NULL,
    request_id INTEGER NOT NULL,
    update_date TEXT,
    PRIMARY KEY (user_id, request_id),
    FOREIGN KEY (request_id) REFERENCES requests (id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (user_id) REFERENCES users (id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE users
(
    id INTEGER NOT NULL,
    telegram_id TEXT,
    first_name TEXT,
    last_name TEXT,
    username TEXT,
    PRIMARY KEY (id), UNIQUE (telegram_id)
);

--changeset ergashbaev:2
ALTER TABLE users ADD COLUMN lang TEXT;

--changeset ergashbaev:3
ALTER TABLE requests ADD COLUMN output_file_id TEXT;

--changeset ergashbaev:4
ALTER TABLE requests ADD COLUMN output_media_type TEXT;

--changeset ergashbaev:5
CREATE INDEX hashcode_index ON requests (hashcode);

--changeset abdullaev:6
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_ureqs_update_date ON user_requests(update_date);

--changeset abdullaev:7
ALTER TABLE user_requests ADD processing_time REAL;

--changeset abdullaev:8
ALTER TABLE user_requests ADD queue_time REAL;

--changeset ergashbaev:9
ALTER TABLE requests ADD COLUMN input_file_id TEXT;
CREATE INDEX input_file_id_index ON requests (input_file_id);

--changeset ergashbaev:10
ALTER TABLE requests ADD COLUMN input_media_type TEXT;

--changeset ergashbaev:11
CREATE INDEX IF NOT EXISTS idx_requests_with_sound ON requests(with_sound);
CREATE INDEX IF NOT EXISTS idx_requests_archived ON requests(archived);