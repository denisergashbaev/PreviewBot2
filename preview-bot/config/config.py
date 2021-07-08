import ConfigParser
from ConfigParser import NoOptionError

import os

_CONFIG = ConfigParser.ConfigParser()
# set to 'prod' on the prod server in ~/.bashrc
_ENV = os.environ.get('PREVIEWBOT_ENV', 'dev')
filename = 'config/config.ini'
if not _CONFIG.read(filename):
    exit(filename + ' is missing. See wiki for instructions')


def get_token():
    return _CONFIG.get('telegram', _ENV + '.api_token')


def get_str(attr_name):
    try:
        ret = _CONFIG.get('telegram', _ENV + '.' + attr_name)
    except NoOptionError:
        ret = _CONFIG.get('telegram', attr_name)
    return ret


def get_int(attr_name):
    return int(get_str(attr_name))


def get_bool(attr_name):
    return get_str(attr_name).lower() == 'true'


def get_int_list(attr_name):
    return map(int, get_str(attr_name).split(','))
