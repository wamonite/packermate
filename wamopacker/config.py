#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from yaml import safe_load
from copy import deepcopy


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
        self._config = read_config_file(config_file_name)
        from pprint import pprint
        pprint(self._config)

    def __getattr__(self, name):
        if name not in self._config:
            raise ConfigException("Config attribute not found: name=%s" % name)

        return deepcopy(self._config[name])
