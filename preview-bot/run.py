# -*- coding: utf-8 -*-
import getopt
import logging
import os
import sys

import pbot
import constants

logger = logging.getLogger(__name__)


def main():
    opts, _ = getopt.getopt(sys.argv[1:], "hl:", ["help"])
    for opt, arg in opts:
        if opt in ['-h', '--help']:
            logging.info("run.py -h [--help]")
            quit()
    housekeeping()
    pbot.init(start=True)


def housekeeping():
    # create db schema with liquibase
    this_dir = os.path.dirname(os.path.realpath(__file__))
    os.system((this_dir + '/libs/liquibase/liquibase'
               ' --driver=org.sqlite.JDBC'
               ' --url="jdbc:sqlite:' + this_dir + '/data/data.db"'
               ' --changeLogFile=' + this_dir + '/orm/changelog.sql migrate'))

    # create required directories for the output
    for d in [constants.output_dir, constants.downloads_dir, constants.err_input_dir]:
        if not os.path.exists(d):
            os.makedirs(d)


# TODO: resources cleanup when exiting process: database, etc
# make sure this method is called somehow too
def shutdown():
    logging.shutdown()


if __name__ == "__main__":
    main()
