#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from yaml import safe_load
from copy import deepcopy
import re
import os


CONFIG_DEFAULTS = {
    'virtualbox_iso_checksum_tyoe': 'md5',
    'virtualbox_shutdown_command': "echo '(( virtualbox_password ))' | sudo -S shutdown -P now",
    'virtualbox_guest_os_type': 'Ubuntu_64',
    'virtualbox_packer_http_dir': 'packer_http',
    'virtualbox_vagrant_box_version': '0',
    'aws_ami_name': 'wamopacker {{ isotime \"2006-01-02 15-04\" }}',
    'aws_vagrant_box_version': '0',
    'shell_command': "{{ .Vars }} bash '{{ .Path }}'",
    'shell_command_sudo': "sudo -H -S {{ .Vars }} bash '{{ .Path }}'",
}
ENV_VAR_PREFIX = 'WAMOPACKER_'


class ConfigException(Exception):
    pass


class Config(object):

    def __init__(self, config_file_name, override_list = None):
        self._config = deepcopy(CONFIG_DEFAULTS)

        config_file = self._read_config_file(config_file_name)
        self._config.update(config_file)

        if isinstance(override_list, list):
            override_lookup = self._parse_overrides(override_list)
            self._config.update(override_lookup)

        var_lookup = self._parse_env_vars()
        if var_lookup:
            self._config.update(var_lookup)

        self._re = re.compile('^(.*)\(\(\s*([^\)\s]+)\s*\)\)(.*)$')

    def __getattr__(self, item):
        if item in self._config:
            return self.expand_parameters(self._config[item])

    def __setattr__(self, item, value):
        if item in ('_config', '_re'):
            super(Config, self).__setattr__(item, value)

        else:
            self._config[item] = value

    def __contains__(self, item):
        return item in self._config

    def _read_config_file(self, file_name):
        try:
            with open(file_name) as file_object:
                config = safe_load(file_object)

        except IOError:
            raise ConfigException("Unable to load config: file_name='{}'".format(file_name))

        if not config:
            return {}

        if not isinstance(config, dict):
            raise ConfigException("Config file should contain a valid YAML dictionary: file_name='{}'".format(file_name))

        if 'include' in config:
            if not isinstance(config['include'], list):
                raise ConfigException("Config file includes should contain a valid YAML list: file_name='{}'".format(file_name))

            for include_file_name in config['include']:
                config_include = self._read_config_file(include_file_name)

                config.update(config_include)

            del(config['include'])

        return config

    @staticmethod
    def _parse_overrides(override_list):
        override_lookup = dict()
        for override_text in override_list:
            val_list = override_text.split('=')
            if len(val_list) != 2:
                raise ConfigException("Invalid parameter: value='{}'".format(override_text))

            override_lookup[val_list[0]] = val_list[1]

        return override_lookup

    @staticmethod
    def _parse_env_vars():
        var_lookup = dict()

        for var_name in os.environ.keys():
            if var_name.startswith(ENV_VAR_PREFIX):
                var_key = var_name[len(ENV_VAR_PREFIX):]
                var_lookup[var_key] = os.environ[var_name]

        return var_lookup

    def expand_parameters(self, value):
        if isinstance(value, basestring):
            return self._expand_parameter(value)

        elif isinstance(value, list):
            out_list = []
            for item in value:
                out_list.append(self.expand_parameters(item))

            return out_list

        elif isinstance(value, dict):
            out_dict = {}
            for key in value.iterkeys():
                out_dict[key] = self.expand_parameters(value[key])

            return out_dict

        return value

    def _expand_parameter(self, value):
        while True:
            match = self._re.match(value)
            if match:
                val_before, val_key, val_after = match.groups()

                val_key_list = val_key.split('|')
                if len(val_key_list) == 2:
                    # special parameter prefix
                    val_key_type, val_key_name = val_key_list
                    if val_key_type == 'env':
                        val_new = self._get_env_var(val_key_name)

                    elif val_key_type == 'file':
                        val_new = self._get_file_content(val_key_name)

                    else:
                        raise ConfigException("Unknown parameter prefix: type='{}'".format(val_key_type))

                else:
                    # existing parameter
                    if val_key in self._config:
                        val_new = self._config[val_key]

                    else:
                        raise ConfigException("Parameter not found: name='{}'".format(match.group(2)))

                value = '{}{}{}'.format(val_before, val_new, val_after)

            else:
                break

        return value

    @staticmethod
    def _get_env_var(var_name):
        # environment variable
        if var_name in os.environ:
            return os.environ[var_name]

        raise ConfigException("Environment variable not found: name='{}'".format(var_name))

    @staticmethod
    def _get_file_content(file_name):
        try:
            with open(file_name, 'r') as file_object:
                return file_object.read()

        except IOError:
            raise ConfigException("Error reading file: name='{}'".format(file_name))
