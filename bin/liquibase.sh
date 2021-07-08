#!/usr/bin/env bash
$PREVIEWBOT_HOME/preview-bot/libs/liquibase/liquibase \
--driver=org.sqlite.JDBC \
--url="jdbc:sqlite:$PREVIEWBOT_HOME/preview-bot/data/data.db" \
--changeLogFile=$PREVIEWBOT_HOME/preview-bot/orm/changelog.sql \
migrate