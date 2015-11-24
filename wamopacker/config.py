#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from yaml import safe_load
from copy import deepcopy


CONFIG_DEFAULTS = {
    'virtualbox_iso_checksum_tyoe': 'md5',
    'virtualbox_user': 'ubuntu',
    'virtualbox_password': 'ubuntu',
    'virtualbox_guest_os_type': 'Ubuntu_64',
    'virtualbox_packer_http_dir': 'packer_http',
    'virtualbox_vagrant_box_version': '0'
}


def read_config_file(file_name):
    try:
        with open(file_name) as file_object:
            config = safe_load(file_object)

    except IOError:
        raise ConfigException("Unable to load config: file_name='%s'" % file_name)

    if not config:
        return {}

    if not isinstance(config, dict):
        raise ConfigException("Config file should contain a valid YAML dictionary: file_name='%s'" % file_name)

    return config


class ConfigException(Exception):
    pass


class Config(object):

    def __init__(self, config_file_name):
        self._config = deepcopy(CONFIG_DEFAULTS)
        config_file = read_config_file(config_file_name)
        self._config.update(config_file)

    def __getattr__(self, item):
        return deepcopy(self._config[item]) if item in self._config else None

    def __setattr__(self, item, value):
        if item == '_config':
            super(Config, self).__setattr__(item, value)

        else:
            self._config[item] = value

    def __contains__(self, item):
        return item in self._config
