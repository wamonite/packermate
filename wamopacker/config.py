#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from yaml import safe_load
from copy import deepcopy
import re
import os
import uuid
import logging


CONFIG_DEFAULTS = {
    'virtualbox_iso_checksum_type': 'md5',
    'virtualbox_password': '',
    'virtualbox_shutdown_command': "echo '(( virtualbox_password ))' | sudo -S shutdown -P now",
    'virtualbox_guest_os_type': 'Ubuntu_64',
    'virtualbox_packer_http_dir': 'packer_http',
    'virtualbox_vagrant_box_version': '0',
    'aws_ami_name': 'wamopacker {{ isotime \"2006-01-02 15-04\" }}',
    'aws_ami_force_deregister': False,
    'aws_vagrant_box_version': '0',
    'shell_command': "{{ .Vars }} bash '{{ .Path }}'",
    'shell_command_sudo': "sudo -H -S {{ .Vars }} bash '{{ .Path }}'",
    'packer_command': 'packer'
}
CONFIG_FILE_NAME_KEY = 'config_file_name'
ENV_VAR_PREFIX = 'WAMOPACKER_'


log = logging.getLogger('wamopacker.config')


__all__ = ['ConfigException', 'ConfigLoadException', 'Config']


class ConfigException(Exception):
    pass


class ConfigLoadException(ConfigException):
    pass


class Config(object):

    def __init__(self, config_file_name = None, override_list = None):
        self._config = deepcopy(CONFIG_DEFAULTS)
        self._re = re.compile('^(.*)\(\(\s*([^\)\s]+)\s*\)\)(.*)$')
        self._uuid_cache = {}

        if config_file_name:
            self._config[CONFIG_FILE_NAME_KEY] = config_file_name
            config_file = self._read_config_file(config_file_name)
            self._config.update(config_file)

            log.info("Loaded config file='{}'".format(config_file_name))

            config_file_includes = self._read_config_includes(config_file_name)
            self._config.update(config_file_includes)

        if isinstance(override_list, list):
            override_lookup = self._parse_overrides(override_list)
            self._config.update(override_lookup)

        var_lookup = self._parse_env_vars()
        if var_lookup:
            self._config.update(var_lookup)

    def __getattr__(self, item):
        if item in self._config:
            return self.expand_parameters(self._config[item])

    def __setattr__(self, item, value):
        if item in ('_config', '_re', '_uuid_cache'):
            super(Config, self).__setattr__(item, value)

        else:
            self._config[item] = value

    def __contains__(self, item):
        return item in self._config

    @staticmethod
    def _read_config_file(file_name):
        try:
            with open(file_name) as file_object:
                config = safe_load(file_object)

        except IOError:
            raise ConfigLoadException("Unable to load config: file_name='{}'".format(file_name))

        if not config:
            return {}

        if not isinstance(config, dict):
            raise ConfigException("Config file should contain a valid YAML dictionary: file_name='{}'".format(file_name))

        if 'include' in config:
            del(config['include'])

        if 'include_optional' in config:
            del(config['include_optional'])

        return config

    def _read_config_includes(self, file_name):
        try:
            with open(file_name) as file_object:
                config = safe_load(file_object)

        except IOError:
            raise ConfigLoadException("Unable to load config: file_name='{}'".format(file_name))

        if not config:
            return {}

        if not isinstance(config, dict):
            raise ConfigException("Config file should contain a valid YAML dictionary: file_name='{}'".format(file_name))

        config_includes = {}

        if 'include' in config:
            if not isinstance(config['include'], list):
                raise ConfigException("Config file includes should contain a valid YAML list: file_name='{}'".format(file_name))

            for include_file_name in config['include']:
                include_file_name_full = self.expand_parameters(include_file_name)
                include_data = self._read_config_file(include_file_name_full)

                config_includes.update(include_data)

                log.info("Included config file='{}'".format(include_file_name_full))

        if 'include_optional' in config:
            if not isinstance(config['include_optional'], list):
                raise ConfigException("Config file optional includes should contain a valid YAML list: file_name='{}'".format(file_name))

            for include_file_name in config['include_optional']:
                include_file_name_full = self.expand_parameters(include_file_name)
                try:
                    include_data = self._read_config_file(include_file_name_full)

                except ConfigLoadException:
                    log.info("Skipped optional config file='{}'".format(include_file_name_full))

                else:
                    config_includes.update(include_data)

                    log.info("Included config file='{}'".format(include_file_name_full))

        return config_includes

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

                val_key_list = map(lambda val_str: val_str.strip(), val_key.split('|'))
                if len(val_key_list) == 3:
                    # special parameter prefix
                    val_key_type, val_key_name, val_key_extra = val_key_list
                    if val_key_type == 'env':
                        try:
                            val_new = self._get_env_var(val_key_name)

                        except ConfigException:
                            val_new = val_key_extra

                    else:
                        raise ConfigException("Unknown parameter combination: type='{}' extra='{}'".format(val_key_type, val_key_extra))

                elif len(val_key_list) == 2:
                    # special parameter prefix
                    val_key_type, val_key_name = val_key_list
                    if val_key_type == 'env':
                        val_new = self._get_env_var(val_key_name)

                    elif val_key_type == 'file':
                        val_new = self._get_file_content(val_key_name)

                    elif val_key_type == 'uuid':
                        val_new = self._get_uuid(val_key_name)

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

    def _get_uuid(self, uuid_key):
        return self._uuid_cache.setdefault(uuid_key, uuid.uuid4().hex)

    def __unicode__(self):
        out_list = self._print_config(self._config)

        line_list = []
        for out_line in out_list:
            indent_list, out_val = out_line
            line_list.append('{}{}'.format(''.join(indent_list), out_val))

        return '\n'.join(line_list)

    def _print_config(self, entry, indent = 0):
        out_list = []

        if isinstance(entry, dict):
            for key in sorted(entry.keys()):
                val = entry[key]

                key_indent = self._get_indent(indent)
                key_text = '{}:'.format(key)

                val_list = self._print_config(val, indent + 1)
                if len(val_list) == 1:
                    val_text = val_list[0][1]
                    out_list.append((key_indent, '{} {}'.format(key_text, val_text)))

                else:
                    out_list.append((key_indent, key_text))
                    for val_list_pair in val_list:
                        out_list.append(val_list_pair)

        elif isinstance(entry, list):
            for val in entry:
                val_list = self._print_config(val, 0)
                for index, val_list_line in enumerate(val_list):
                    val_indent, val_text = val_list_line
                    val_indent = self._get_indent(indent, is_list = index == 0, extend_with = val_indent)
                    out_list.append((val_indent, val_text))

        else:
            val_indent = self._get_indent(indent)
            val_text = '{}'.format(entry)

            out_list.append((val_indent, val_text))

        return out_list

    @staticmethod
    def _get_indent(indent, is_list = False, extend_with = None):
        if is_list:
            indent_list = (indent - 1 if indent > 1 else 0) * ['    ']
            indent_list.append('  - ')

        else:
            indent_list = indent * ['    ']

        if extend_with:
            indent_list.extend(extend_with)

        return indent_list
