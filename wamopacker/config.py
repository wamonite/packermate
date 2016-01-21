#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from yaml import safe_load, SafeLoader
from yaml.scanner import ScannerError
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


__all__ = ['ConfigException', 'ConfigLoadException', 'ConfigValue', 'Config']


# https://stackoverflow.com/questions/2890146/how-to-force-pyyaml-to-load-strings-as-unicode-objects

def construct_yaml_str(self, node):
    # Override the default string handling function
    # to always return unicode objects
    return self.construct_scalar(node)

SafeLoader.add_constructor(u'tag:yaml.org,2002:str', construct_yaml_str)


class ConfigException(Exception):
    pass


class ConfigLoadException(ConfigException):
    pass


class ConfigValue(object):

    def __init__(self, config, value = None, dynamic = False):
        self._config = config
        self._value = value
        self._dynamic = dynamic
        self._value_list = []

    def evaluate(self):
        if self._value:
            try:
                self._parse(self._value)

            except ConfigException as e:
                if not self._dynamic:
                    raise ConfigException("Failed to parse: line='{}' reason='{}'".format(self._value, e))

                else:
                    raise

            self._value = None

        out_list = []
        for value in self._value_list:
            if isinstance(value, ConfigValue):
                out_list.append(value.evaluate())

            else:
                out_list.append(value)

        bracket_value = ''.join(out_list)
        return self._process(bracket_value) if self._dynamic else bracket_value.strip()

    def _parse(self, value):
        lookup_start = value.find('((')
        lookup_end = value.find('))')

        if lookup_start >= 0 > lookup_end:
            raise ConfigException('Missing end brackets')

        if 0 <= lookup_start < lookup_end:
            val_before = value[:lookup_start]
            val_after = value[lookup_start + 2:]

            if val_before and not val_before.isspace():
                self._value_list.append(val_before)

            if val_after:
                config_value = ConfigValue(self._config, dynamic = True)
                self._value_list.append(config_value)

                val_left = config_value._parse(val_after)
                if val_left and not val_left.isspace():
                    self._parse(val_left)

        elif lookup_end >= 0:
            if not self._dynamic:
                raise ConfigException('Missing start brackets')

            val_before = value[:lookup_end]
            val_after = value[lookup_end + 2:]

            if val_before and not val_before.isspace():
                self._value_list.append(val_before)

            return val_after if val_after and not val_after.isspace() else ''

        else:
            if value and not value.isspace():
                self._value_list.append(value)

        return ''

    def _process(self, value):
        value_list = map(lambda val_str: val_str.strip(), value.split('|'))
        value_list_len = len(value_list)
        val_new = None

        if value_list_len == 3:
            val_type, val_name, val_extra = value_list

            if val_type == 'env':
                try:
                    val_new = self._get_env_var(val_name)

                except ConfigException:
                    val_new = val_extra

            elif val_type == 'lookup':
                try:
                    with open(val_name, 'r') as file_object:
                        lookup = safe_load(file_object)

                except IOError:
                    raise ConfigException('Unable to load lookup: {}'.format(val_name))

                else:
                    if not isinstance(lookup, dict):
                        raise ConfigException('Lookup file should be a dictionary: {}'.format(val_name))

                    val_new = lookup[val_extra] if val_extra in lookup else val_extra

            elif val_type == 'lookup_optional':
                try:
                    with open(val_name, 'r') as file_object:
                        lookup = safe_load(file_object)

                except IOError:
                    val_new = val_extra

                else:
                    if not isinstance(lookup, dict):
                        raise ConfigException('Lookup file should be a dictionary: {}'.format(val_name))

                    val_new = lookup[val_extra] if val_extra in lookup else val_extra

            elif val_type == 'default':
                try:
                    val_new = val_name or val_extra

                except ConfigException:
                    val_new = val_extra

        if value_list_len == 2:
            val_type, val_name = value_list

            if val_type == 'env':
                val_new = self._get_env_var(val_name)

            elif val_type == 'uuid':
                val_new = self._config.get_uuid(val_name)

        elif value_list_len == 1:
            val_name = value_list[0]

            if val_name not in self._config:
                raise ConfigException('Unknown config parameter: {}'.format(val_name))

            val_new = getattr(self._config, val_name)

        if val_new is None:
            raise ConfigException('Invalid config parameter substitution')

        if not isinstance(val_new, basestring):
            val_new = '{}'.format(val_new)

        return val_new

    @staticmethod
    def _get_env_var(var_name):
        if var_name in os.environ:
            return os.environ[var_name]

        raise ConfigException("Environment variable not found: {}".format(var_name))


class ConfigFileLoader(object):

    def __init__(self, file_name):
        self._file_name = file_name

    @property
    def name(self):
        return self._file_name

    def get_data(self):
        try:
            with open(self._file_name) as file_object:
                config_data = safe_load(file_object)

        except (IOError, ScannerError):
            raise ConfigLoadException("Unable to load config: '{}'".format(self.name))

        if not isinstance(config_data, dict):
            raise ConfigLoadException("Config file should contain a valid YAML dictionary: '{}'".format(self.name))

        return config_data


class ConfigStringLoader(object):

    def __init__(self, config_string):
        self._config_string = config_string

    @property
    def name(self):
        return '<string>'

    def get_data(self):
        try:
            config_data = safe_load(self._config_string)

        except ScannerError:
            raise ConfigLoadException("Unable to load config: '{}'".format(self.name))

        if not isinstance(config_data, dict):
            raise ConfigLoadException("Config file should contain a valid YAML dictionary: '{}'".format(self.name))

        return config_data


class Config(object):

    def __init__(self, config_file_name = None, config_string = None, override_list = None):
        self._config = deepcopy(CONFIG_DEFAULTS)
        self._re = re.compile('^(.*)\(\(\s*([^\)\s]+)\s*\)\)(.*)$')
        self._uuid_cache = {}

        if config_file_name is not None:
            config_loader = ConfigFileLoader(config_file_name)
            self._config[CONFIG_FILE_NAME_KEY] = config_file_name
            self._read_config(config_loader, initial_config = True)

        if config_string is not None:
            config_loader = ConfigStringLoader(config_string)
            self._read_config(config_loader, initial_config = True)

        if isinstance(override_list, list):
            override_lookup = self._parse_overrides(override_list)
            self._config.update(override_lookup)

        var_lookup = self._parse_env_vars()
        if var_lookup:
            self._config.update(var_lookup)

    def expand_parameters(self, value):
        if isinstance(value, basestring):
            config_value = ConfigValue(self, value)
            return config_value.evaluate()

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

    def get_uuid(self, name):
        if not name:
            raise ConfigException('UUID requires a name')

        return self._uuid_cache.setdefault(name, uuid.uuid4().hex)

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

    def __delattr__(self, item):
        if item in self._config:
            del(self._config[item])

    def _read_config(self, config_loader, initial_config = False):
        self._read_config_core(config_loader)

        if initial_config:
            log.info("Loaded config: '{}'".format(config_loader.name))

        self._read_config_includes(config_loader)

    def _read_config_core(self, config_loader):
        config_data = config_loader.get_data()

        if 'include' in config_data:
            del(config_data['include'])

        if 'include_optional' in config_data:
            del(config_data['include_optional'])

        self._config.update(config_data)

    def _read_config_includes(self, config_loader):
        config_data = config_loader.get_data()

        if 'include' in config_data:
            if not isinstance(config_data['include'], list):
                raise ConfigException("Config file includes should contain a valid YAML list: '{}'".format(config_loader.name))

            for include_file_name in config_data['include']:
                include_file_name_full = self.expand_parameters(include_file_name)
                include_config_loader = ConfigFileLoader(include_file_name_full)
                self._read_config(include_config_loader)

                log.info("Included config: '{}'".format(include_file_name_full))

        if 'include_optional' in config_data:
            if not isinstance(config_data['include_optional'], list):
                raise ConfigException("Config file optional includes should contain a valid YAML list: '{}'".format(config_loader.name))

            for include_file_name in config_data['include_optional']:
                include_file_name_full = self.expand_parameters(include_file_name)
                try:
                    include_config_loader = ConfigFileLoader(include_file_name_full)
                    self._read_config(include_config_loader)

                except ConfigLoadException:
                    log.info("Skipped optional config: '{}'".format(include_file_name_full))

                else:
                    log.info("Included optional config: '{}'".format(include_file_name_full))

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

    def __str__(self):
        return unicode(self).decode('utf-8')

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
