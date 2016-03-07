#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from copy import deepcopy
import re
import os
import uuid
from .file_utils import read_yaml_file, read_yaml_string
import base64
import tarfile
import logging


CONFIG_DEFAULTS = {
    'shell_command': "{{ .Vars }} bash '{{ .Path }}'",
    'shell_command_sudo': "sudo -H -S {{ .Vars }} bash '{{ .Path }}'",
    'packer_command': 'packer'
}
CONFIG_FILE_NAME_KEY = 'config_file_name'
ENV_VAR_PREFIX = 'WAMOPACKER_'


log = logging.getLogger('wamopacker.config')


__all__ = ['ConfigException', 'ConfigLoadException', 'ConfigValue', 'Config']


class ConfigException(Exception):
    pass


class ConfigLoadException(ConfigException):
    pass


class ConfigLoadFormatException(ConfigLoadException):
    pass


class ConfigValue(object):

    def __init__(self, config, value = None):
        self._config = config
        self._value = value
        self._dynamic = value is None
        self._value_list = []

    def evaluate(self):
        if self._value:
            try:
                self._parse(self._value)

            except ConfigException as e:
                raise ConfigException("Failed to parse: line='{}' reason='{}'".format(self._value, e))

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
                config_value = ConfigValue(self._config)
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

        process_func_list = (
            ((), 1, self._process_name),
            (('env',), 1, get_env_var),
            (('env',), 2, get_env_var),
            (('uuid',), 1, self._config.get_uuid),
            (('base64_encode',), 1, base64.b64encode),
            (('base64_decode',), 1, base64.b64decode),
            (('default',), 2, get_default_value),
            (('lookup',), 2, get_lookup_value),
            (('lookup_optional',), 2, get_lookup_optional_value),
            (('file', 'text'), 1, get_file_text),
            (('file', 'data'), 1, get_file_data),
            (('file', 'tgz'), 2, get_tgz_file_data),
        )
        process_func = None
        process_args = []
        process_key_arg_len = -1
        for process_func_key, func_arg_len, func in process_func_list:
            process_func_key_len = len(process_func_key)
            key_arg_len = process_func_key_len + func_arg_len

            if key_arg_len == value_list_len:
                val_func_key = tuple(value_list[:process_func_key_len])

                if process_func_key == val_func_key and process_key_arg_len < key_arg_len:
                    process_func = func
                    process_args = value_list[process_func_key_len:]
                    process_key_arg_len = value_list_len

        if not process_func:
            raise ConfigException("Unable to find matching parameter method: {}".format(value))

        val_new = process_func(*process_args)

        if not isinstance(val_new, basestring):
            val_new = '{}'.format(val_new)

        return val_new

    def _process_name(self, name):
        if name not in self._config:
            raise ConfigException('Unknown config parameter: {}'.format(name))

        return getattr(self._config, name)


def get_env_var(name, default = None):
    if name in os.environ:
        return os.environ[name]

    if default is None:
        raise ConfigException('Environment variable not found: {}'.format(name))

    return default


def get_default_value(value, default):
    return value or default


def get_lookup_value(file_name, key_name, optional = False):
    lookup = read_yaml_file(file_name)
    if lookup is None:
        if optional:
            return key_name

        raise ConfigException('Unable to load lookup: {}'.format(file_name))

    else:
        if not isinstance(lookup, dict):
            raise ConfigException('Lookup file should be a dictionary: {}'.format(file_name))

        return lookup[key_name] if key_name in lookup else key_name


def get_lookup_optional_value(file_name, key_name):
    return get_lookup_value(file_name, key_name, optional = True)


def get_file_data(file_name, encode = True):
    try:
        with open(file_name, 'rb') as file_object:
            file_data = file_object.read()
            return base64.b64encode(file_data) if encode else file_data

    except IOError as e:
        raise ConfigException("Unable to load file: name='{}' error='{}'".format(file_name, e))


def get_file_text(file_name):
    return get_file_data(file_name, encode = False)


def get_tar_file_data(tar_type, tar_name, file_name):
    tar_type_lookup = {
        'tgz': 'r:gz'
    }
    tar_mode = tar_type_lookup.get(tar_type)
    if tar_mode is None:
        raise ConfigException("Unknown tar type: name='{}' type='{}'".format(tar_name, tar_type))

    try:
        with tarfile.open(name = tar_name, mode = tar_mode) as tar_file:
            for tar_info in tar_file:
                if file_name == tar_info.name:
                    file_object = tar_file.extractfile(tar_info)
                    file_data = file_object.read()
                    return base64.b64encode(file_data)

    except IOError as e:
        raise ConfigException("Unable to load tar file: tar='{}' error='{}'".format(tar_name, e))

    raise ConfigException("Unable to find file: tar='{}' file='{}'".format(tar_name, file_name))


def get_tgz_file_data(tar_name, file_name):
    return get_tar_file_data('tgz', tar_name, file_name)


class ConfigFileLoader(object):

    def __init__(self, file_name):
        self._file_name = file_name

    @property
    def name(self):
        return self._file_name

    def get_data(self):
        config_data = read_yaml_file(self._file_name)
        if config_data is None:
            raise ConfigLoadException("Unable to load config: '{}'".format(self.name))

        if not isinstance(config_data, dict):
            raise ConfigLoadFormatException("Config file should contain a valid YAML dictionary: '{}'".format(self.name))

        return config_data


class ConfigStringLoader(object):

    def __init__(self, config_string):
        self._config_string = config_string

    @property
    def name(self):
        return '<string>'

    def get_data(self):
        config_data = read_yaml_string(self._config_string)
        if config_data is None:
            raise ConfigLoadException("Unable to load config: '{}'".format(self.name))

        if not isinstance(config_data, dict):
            raise ConfigLoadFormatException("Config file should contain a valid YAML dictionary: '{}'".format(self.name))

        return config_data


class ConfigDumper(object):

    @classmethod
    def dump(cls, config):
        out_list = cls._dump_config(config)

        line_list = []
        for out_line in out_list:
            indent_list, out_val = out_line
            line_list.append('{}{}'.format(''.join(indent_list), out_val))

        return '\n'.join(line_list)

    @classmethod
    def _dump_config(cls, entry, indent = 0):
        out_list = []

        if isinstance(entry, dict):
            for key in sorted(entry.keys()):
                val = entry[key]

                key_indent = cls._get_indent(indent)
                key_text = '{}:'.format(key)

                val_list = cls._dump_config(val, indent + 1)
                if len(val_list) == 1:
                    val_text = val_list[0][1]
                    out_list.append((key_indent, '{} {}'.format(key_text, val_text)))

                else:
                    out_list.append((key_indent, key_text))
                    for val_list_pair in val_list:
                        out_list.append(val_list_pair)

        elif isinstance(entry, list):
            for val in entry:
                val_list = cls._dump_config(val, 0)
                for index, val_list_line in enumerate(val_list):
                    val_indent, val_text = val_list_line
                    val_indent = cls._get_indent(indent, is_list = index == 0, extend_with = val_indent)
                    out_list.append((val_indent, val_text))

        else:
            val_indent = cls._get_indent(indent)
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
            if value is None:
                if item in self._config:
                    del self._config[item]

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
                raise ConfigLoadFormatException("Config file includes should contain a valid YAML list: '{}'".format(config_loader.name))

            for include_file_name in config_data['include']:
                include_file_name_full = self.expand_parameters(include_file_name)
                include_config_loader = ConfigFileLoader(include_file_name_full)
                self._read_config(include_config_loader)

                log.info("Included config: '{}'".format(include_file_name_full))

        if 'include_optional' in config_data:
            if not isinstance(config_data['include_optional'], list):
                raise ConfigLoadFormatException("Config file optional includes should contain a valid YAML list: '{}'".format(config_loader.name))

            for include_file_name in config_data['include_optional']:
                include_file_name_full = self.expand_parameters(include_file_name)
                try:
                    include_config_loader = ConfigFileLoader(include_file_name_full)
                    self._read_config(include_config_loader)

                except ConfigLoadFormatException:
                    raise

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
                raise ConfigException("Invalid parameter: '{}'".format(override_text))

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
        return ConfigDumper.dump(self._config)

    def __repr__(self):
        return "{}[\n{}\n]".format(
            self.__class__.__name__,
            str(self)
        )

    def provider(self, provider):
        return ConfigProvider(self, provider)


class ConfigProvider(object):

    def __init__(self, config, provider):
        if not provider:
            raise ConfigException('Config provider not set')

        self._config = config
        self._provider = provider
        self._prefix = self._provider + '_'

    def __getattr__(self, item):
        val = None

        if not item.startswith(self._prefix):
            val = getattr(self._config, self._prefix + item)

        if val is None:
            val = getattr(self._config, item)

        return val

    def __setattr__(self, item, value):
        if item in ('_config', '_provider', '_prefix'):
            super(ConfigProvider, self).__setattr__(item, value)

        else:
            if item.startswith(self._prefix):
                return setattr(self._config, item, value)

            else:
                return setattr(self._config, self._prefix + item, value)

    def __contains__(self, item):
        if item.startswith(self._prefix):
            return item in self._config

        else:
            return self._prefix + item in self._config or item in self._config

    def __delattr__(self, item):
        if not item.startswith(self._prefix):
            if self._prefix + item in self._config:
                delattr(self._config, self._prefix + item)

        if item in self._config:
            delattr(self._config, item)
