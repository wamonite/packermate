#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from copy import deepcopy
import re
import os
import uuid
from .file_utils import read_yaml_file, read_yaml_string, get_path_names
import base64
import tarfile
from collections import namedtuple
from fnmatch import fnmatch
from .exception import PackermateException
import logging

try:
    import boto3
    from botocore.exceptions import BotoCoreError
    BOTO3_AVAILABLE = True

except ImportError:
    BOTO3_AVAILABLE = False


CONFIG_DEFAULTS = {
    'shell_command': "{{ .Vars }} bash '{{ .Path }}'",
    'shell_command_sudo': "sudo -H -S {{ .Vars }} bash '{{ .Path }}'",
    'packer_command': 'packer',
    'vagrant_command': 'vagrant',
}
CONFIG_FILE_NAME_KEY = 'config_file_name'
ENV_VAR_PREFIX = 'PACKERMATE_'


log = logging.getLogger('packermate.config')


__all__ = ['ConfigException', 'ConfigLoadException', 'ConfigValue', 'Config']


class ConfigException(PackermateException):
    pass


class ConfigLoadException(ConfigException):
    pass


class ConfigLoadFormatException(ConfigLoadException):
    pass


def get_aws_caller_identity(key, default = None):
    try:
        sts_client = boto3.client('sts')
        return sts_client.get_caller_identity()[key]

    except BotoCoreError as e:
        if default is not None:
            return default

        raise ConfigException('AWS error ({}) {}'.format(e.__class__.__name__, e))


class ConfigValue(object):

    ProcessFuncInfo = namedtuple('ProcessFuncInfo', ('key', 'argument_count', 'function'))

    def __init__(self, config, value = None, path_list = None):
        self._config = config
        self._value = value
        self._path_list = path_list or ['']
        self._line = value
        self._dynamic = value is None
        self._value_list = []

    def evaluate(self):
        try:
            return self._evaluate().strip()

        except ConfigException as e:
            raise ConfigException(e.message + "\n  line='{}'".format(self._line))

    def _evaluate(self):
        if self._value:
            self._parse(self._value)

            self._value = None

        out_list = []
        for value in self._value_list:
            if isinstance(value, ConfigValue):
                out_list.append(value._evaluate())

            else:
                out_list.append(value)

        bracket_value = ''.join(out_list)
        return self._process(bracket_value) if self._dynamic else bracket_value

    def _parse(self, value):
        lookup_start = value.find('((')
        lookup_end = value.find('))')

        if lookup_start >= 0 > lookup_end:
            raise ConfigException('Missing end brackets')

        if 0 <= lookup_start < lookup_end:
            val_before = value[:lookup_start]
            val_after = value[lookup_start + 2:]

            if val_before:
                self._value_list.append(val_before)

            if val_after:
                config_value = ConfigValue(self._config, path_list = self._path_list)
                self._value_list.append(config_value)

                val_left = config_value._parse(val_after)
                if val_left:
                    self._parse(val_left)

        elif lookup_end >= 0:
            if not self._dynamic:
                raise ConfigException('Missing start brackets')

            val_before = value[:lookup_end]
            val_after = value[lookup_end + 2:]

            if val_before:
                self._value_list.append(val_before)

            return val_after or ''

        else:
            if value:
                self._value_list.append(value)

        return ''

    def _process(self, value):
        value_list = map(lambda val_str: val_str.strip(), value.split('|'))
        value_list_len = len(value_list)

        process_func_list = []

        if BOTO3_AVAILABLE:
            process_func_list += [
                self.ProcessFuncInfo(('aws_account',), 1, self._get_aws_account),
                self.ProcessFuncInfo(('aws_account',), 2, self._get_aws_account),
                self.ProcessFuncInfo(('aws_user',), 1, self._get_aws_user),
                self.ProcessFuncInfo(('aws_user',), 2, self._get_aws_user),
                self.ProcessFuncInfo(('aws_arn',), 1, self._get_aws_arn),
                self.ProcessFuncInfo(('aws_arn',), 2, self._get_aws_arn),
            ]

        process_func_list += [
            self.ProcessFuncInfo((), 1, self._process_name),
            self.ProcessFuncInfo(('env',), 2, get_env_var),
            self.ProcessFuncInfo(('env',), 3, get_env_var),
            self.ProcessFuncInfo(('uuid',), 2, self._config.get_uuid),
            self.ProcessFuncInfo(('base64_encode',), 2, base64.b64encode),
            self.ProcessFuncInfo(('base64_decode',), 2, base64.b64decode),
            self.ProcessFuncInfo(('default',), 2, self._process_default_value),
            self.ProcessFuncInfo(('default',), 3, self._process_default_value),
            self.ProcessFuncInfo(('lookup',), 3, self._get_lookup_value),
            self.ProcessFuncInfo(('lookup_optional',), 3, self._get_lookup_optional_value),
            self.ProcessFuncInfo(('file', 'text'), 3, self._get_file_text),
            self.ProcessFuncInfo(('file', 'data'), 3, self._get_file_data),
            self.ProcessFuncInfo(('file', 'tgz'), 4, self._get_tgz_file_data),
        ]

        process_func_found = None
        for process_func_info in process_func_list:
            if process_func_info.argument_count == value_list_len:
                process_func_key_len = len(process_func_info.key)
                val_func_key = tuple(value_list[:process_func_key_len])

                if process_func_info.key == val_func_key and (process_func_found is None or process_func_info.argument_count > process_func_found.argument_count):
                    process_func_found = process_func_info

        if not process_func_found:
            raise ConfigException("Unable to find matching parameter method: {}".format(value))

        process_func_found_key_len = len(process_func_found.key)
        process_func_args = value_list[process_func_found_key_len:]
        val_new = process_func_found.function(*process_func_args)

        if not isinstance(val_new, basestring):
            val_new = '{}'.format(val_new)

        return val_new

    def _process_name(self, name):
        if name not in self._config:
            raise ConfigException('Unknown config parameter: {}'.format(name))

        return getattr(self._config, name)

    def _process_default_value(self, value, default = ''):
        if not value:
            raise ConfigException('Default parameter not set')

        try:
            return self._process_name(value) or default

        except ConfigException:
            return default

    def _get_lookup_value(self, file_name, key_name, optional = False):
        lookup = None

        for file_name_full in get_path_names(file_name, self._path_list):
            lookup = read_yaml_file(file_name_full)

            if lookup:
                break

        if lookup is None:
            if optional:
                return key_name

            raise ConfigException('Unable to load lookup: {}'.format(file_name))

        else:
            if not isinstance(lookup, dict):
                raise ConfigException('Lookup file should be a dictionary: {}'.format(file_name))

            return lookup[key_name] if key_name in lookup else key_name

    def _get_lookup_optional_value(self, file_name, key_name):
        return self._get_lookup_value(file_name, key_name, optional = True)

    def _get_file_data(self, file_name, encode = True):
        data = None
        for file_name_full in get_path_names(file_name, self._path_list):
            try:
                with open(file_name_full, 'rb') as file_object:
                    file_data = file_object.read()
                    data = base64.b64encode(file_data) if encode else file_data

                    break

            except IOError:
                pass

        if data is None:
            raise ConfigException("Unable to load file: '{}'".format(file_name))

        return data

    def _get_file_text(self, file_name):
        return self._get_file_data(file_name, encode = False)

    def _get_tar_file_data(self, tar_type, tar_name, file_name):
        tar_type_lookup = {
            'tgz': 'r:gz'
        }
        tar_mode = tar_type_lookup.get(tar_type)
        if tar_mode is None:
            raise ConfigException("Unknown tar type: name='{}' type='{}'".format(tar_name, tar_type))

        data = None
        for tar_name_full in get_path_names(tar_name, self._path_list):
            try:
                with tarfile.open(name = tar_name_full, mode = tar_mode) as tar_file:
                    for tar_info in tar_file:
                        if fnmatch(tar_info.name, file_name):
                            file_object = tar_file.extractfile(tar_info)
                            file_data = file_object.read()
                            return base64.b64encode(file_data)

            except IOError:
                pass

        if data is None:
            raise ConfigException("Unable to find file: tar='{}' file='{}'".format(tar_name, file_name))

        return data

    def _get_tgz_file_data(self, tar_name, file_name):
        return self._get_tar_file_data('tgz', tar_name, file_name)

    @staticmethod
    def _get_aws_account(default = None):
        return get_aws_caller_identity('Account', default)

    @staticmethod
    def _get_aws_user(default = None):
        return get_aws_caller_identity('UserId', default)

    @staticmethod
    def _get_aws_arn(default = None):
        return get_aws_caller_identity('Arn', default)


def get_env_var(name, default = None):
    if name in os.environ:
        return os.environ[name]

    if default is None:
        raise ConfigException('Environment variable not found: {}'.format(name))

    return default


class ConfigFileLoader(object):

    def __init__(self, file_name, path_list = None):
        self._file_name = file_name
        self._path_list = path_list if path_list else ['']
        self._loaded_file_list = []

    @property
    def name_list(self):
        return self._loaded_file_list or [self._file_name]

    @property
    def names(self):
        return ', '.join(["'{}'".format(name) for name in self.name_list])

    @property
    def path_list(self):
        return self._path_list

    def get_data(self):
        config_data_list = []

        self._loaded_file_list = []
        for path in reversed(self._path_list):
            file_name = os.path.join(path, self._file_name)
            config_data = read_yaml_file(file_name)

            if config_data:
                if not isinstance(config_data, dict):
                    raise ConfigLoadFormatException("Config file should contain a valid YAML dictionary: '{}'".format(file_name))

                config_data_list.append(config_data)
                self._loaded_file_list.append(file_name)

        if not config_data_list:
            raise ConfigLoadException("Unable to load config: '{}'".format(self._file_name))

        return config_data_list


class ConfigStringLoader(object):

    CONFIG_NAME = '<string>'

    def __init__(self, config_string, path_list = None):
        self._config_string = config_string
        self._path_list = path_list if path_list else ['']

    @property
    def name_list(self):
        return [self.CONFIG_NAME]

    @property
    def names(self):
        return self.CONFIG_NAME

    @property
    def path_list(self):
        return self._path_list

    def get_data(self):
        config_data = read_yaml_string(self._config_string)
        if config_data is None:
            raise ConfigLoadException("Unable to load config: {}".format(self.CONFIG_NAME))

        if not isinstance(config_data, dict):
            raise ConfigLoadFormatException("Config file should contain a valid YAML dictionary: {}".format(self.CONFIG_NAME))

        return [config_data]


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

    def __init__(self, config_file_name = None, config_string = None, override_list = None, path_list = None):
        self._path_list = path_list

        self._config = deepcopy(CONFIG_DEFAULTS)
        self._re = re.compile('^(.*)\(\(\s*([^\)\s]+)\s*\)\)(.*)$')
        self._uuid_cache = {}

        if config_file_name is not None:
            config_loader = ConfigFileLoader(config_file_name, path_list = path_list)
            self._config[CONFIG_FILE_NAME_KEY] = config_file_name
            self._read_config(config_loader, initial_config = True)

        if config_string is not None:
            config_loader = ConfigStringLoader(config_string, path_list = path_list)
            self._read_config(config_loader, initial_config = True)

        if isinstance(override_list, list):
            override_lookup = self._parse_overrides(override_list)
            self._config.update(override_lookup)

        var_lookup = self._parse_env_vars()
        if var_lookup:
            self._config.update(var_lookup)

    def expand_parameters(self, value):
        if isinstance(value, basestring):
            config_value = ConfigValue(self, value = value, path_list = self._path_list)
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
        if item in ('_path_list', '_config', '_re', '_uuid_cache'):
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

    def __iter__(self):
        for item in self._config.keys():
            yield item

    def _read_config(self, config_loader, initial_config = False):
        self._read_config_core(config_loader)

        if initial_config:
            log.info("Loaded config: {}".format(config_loader.names))

        self._read_config_includes(config_loader)

    def _read_config_core(self, config_loader):
        config_data_list = config_loader.get_data()

        for config_data in config_data_list:
            if 'include' in config_data:
                del(config_data['include'])

            if 'include_optional' in config_data:
                del(config_data['include_optional'])

            self._config.update(config_data)

    def _read_config_includes(self, config_loader):
        config_data_list = config_loader.get_data()

        for config_data in config_data_list:
            if 'include' in config_data:
                if not isinstance(config_data['include'], list):
                    raise ConfigLoadFormatException("Config file includes should contain a valid YAML list: {}".format(config_loader.names))

                for include_file_name in config_data['include']:
                    include_file_name_full = self.expand_parameters(include_file_name)
                    include_config_loader = ConfigFileLoader(include_file_name_full, path_list = config_loader.path_list)
                    self._read_config(include_config_loader)

                    log.info("Included config: {} into {}".format(include_config_loader.names, config_loader.names))

            if 'include_optional' in config_data:
                if not isinstance(config_data['include_optional'], list):
                    raise ConfigLoadFormatException("Config file optional includes should contain a valid YAML list: {}".format(config_loader.names))

                for include_file_name in config_data['include_optional']:
                    include_file_name_full = self.expand_parameters(include_file_name)
                    try:
                        include_config_loader = ConfigFileLoader(include_file_name_full, path_list = config_loader.path_list)
                        self._read_config(include_config_loader)

                    except ConfigLoadFormatException:
                        raise

                    except ConfigLoadException:
                        log.debug("Skipped optional config: '{}'".format(include_file_name_full))

                    else:
                        log.info("Included optional config: {} into {}".format(include_config_loader.names, config_loader.names))

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
