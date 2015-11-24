#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from yaml import safe_load
from copy import deepcopy
import re


CONFIG_DEFAULTS = {
    'virtualbox_iso_checksum_tyoe': 'md5',
    'virtualbox_user': 'ubuntu',
    'virtualbox_password': 'ubuntu',
    'virtualhox_shutdown_command': "echo '(( virtualbox_password ))' | sudo -S shutdown -P now",
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
        self._re = re.compile('^(.*)\(\(([^\)]+)\)\)(.*)$')

    def __getattr__(self, item):
        if item in self._config:
            return self._replace_values(self._config[item])

    def __setattr__(self, item, value):
        if item in ('_config', '_re'):
            super(Config, self).__setattr__(item, value)

        else:
            self._config[item] = value

    def __contains__(self, item):
        return item in self._config

    def _replace_values(self, value):
        if isinstance(value, basestring):
            return self._replace_value(value)

        elif isinstance(value, list):
            out_list = []
            for item in value:
                out_list.append(self._replace_values(item))

            return out_list

        elif isinstance(value, dict):
            out_dict = {}
            for key in value.iterkeys():
                out_dict[key] = self._replace_values(value[key])

            return out_dict

    def _replace_value(self, value):
        while True:
            match = self._re.match(value)
            if match:
                val_before, val_key, val_after = match.groups()
                val_key = val_key.strip()
                if val_key in self._config:
                    value = val_before + self._config[val_key] + val_after
                else:
                    raise ConfigException("replacement parameter not found: name='%s'" % match.group(2))

            else:
                break

        return value
