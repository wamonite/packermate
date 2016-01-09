#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import pytest
from wamopacker.config import (
    Config, ConfigValue,
    ConfigException, ConfigLoadException,
    CONFIG_DEFAULTS, ENV_VAR_PREFIX
)
import logging
import os
from tempfile import mkdtemp
from shutil import rmtree
from yaml import safe_dump


log = logging.getLogger('wamopacker.test_config')

TEST_VAR_NAME = 'TEST_ENV_VAR'
TEST_VAR_KEY = ENV_VAR_PREFIX + TEST_VAR_NAME
TEST_VAR_VALUE = 'meh'
YAML_CONFIG_FILE_NAME = 'config.yml'
YAML_LOOKUP_FILE_NAME = 'lookup.yml'
YAML_FILE_DATA = {
    YAML_CONFIG_FILE_NAME: {
        'fizz': 'abc',
        'buzz': 'def'
    },
    YAML_LOOKUP_FILE_NAME: {
        'abc': 'easy as',
        'def': '123'
    }
}
MISSING_FILE_NAME = '/file/does/not/exist.yml'


@pytest.fixture()
def no_env_var():
    if TEST_VAR_KEY in os.environ:
        del(os.environ[TEST_VAR_KEY])


@pytest.fixture()
def env_var():
    os.environ[TEST_VAR_KEY] = TEST_VAR_VALUE


@pytest.fixture()
def config(no_env_var):
    return Config()


@pytest.fixture()
def config_with_env(env_var):
    return Config()


@pytest.fixture()
def config_with_override_list(no_env_var):
    override_list = ['{}={}'.format(TEST_VAR_NAME, TEST_VAR_VALUE)]
    return Config(override_list = override_list)


@pytest.fixture()
def config_with_data(env_var):
    conf = Config()
    conf.foo = '123'
    conf.bar = '456'
    conf.empty = ''
    return conf


def config_values_id_func(fixture_value):
    return "'{}' == '{}'".format(*fixture_value)


@pytest.fixture(
    params = [
        ('', ''),
        (' ', ''),
        ('  ', ''),
        ('test', 'test'),
        (' test', 'test'),
        ('  test', 'test'),
        ('test ', 'test'),
        ('test  ', 'test'),
        (' test ', 'test'),
        ('  test  ', 'test'),
        ('((foo))', '123'),
        ('(( foo))', '123'),
        ('((foo ))', '123'),
        ('(( foo ))', '123'),
        (' (( foo ))', '123'),
        ('(( foo )) ', '123'),
        ('(( foo ))(( bar ))', '123456'),
        ('test ((foo))', 'test 123'),
        (' test ((foo))', 'test 123'),
        ('test ((foo)) ', 'test 123'),
        ('test  ((foo)) ', 'test  123'),
        ('((foo)) test', '123 test'),
        ('((foo)) test ', '123 test'),
        (' ((foo)) test', '123 test'),
        ('((foo))  test', '123  test'),
        ('(( default | foo | bar ))', 'foo'),
        ('(( default || bar ))', 'bar'),
        ('(( default | | bar ))', 'bar'),
        ('(( default | (( foo )) | bar ))', '123'),
        ('(( default | (( empty )) | bar ))', 'bar'),
        ('(( env | {} ))'.format(TEST_VAR_KEY), TEST_VAR_VALUE),
    ],
    ids = config_values_id_func
)
def config_values(request, config_with_data):
    value, expected = request.param
    config_value = ConfigValue(config_with_data, value)
    return config_value, expected


@pytest.fixture(
    params = [
        '((',
        ' ((',
        '  ((',
        '(( ',
        '((  ',
        ' (( ',
        '  ((  ',
        '))',
        ' ))',
        '  ))',
        ')) ',
        '))  ',
        ' )) ',
        '  ))  ',
        '(( undefined ))',
        '(((( foo ))))',
        '(( | ))',
        '(( undefined | ))',
        '(( env | ))',
        '(( env | UNDEFINED_ENV_VAR ))',
        '(( uuid | ))',
    ]
)
def config_values_bad(request, config_with_data):
    return ConfigValue(config_with_data, request.param)


@pytest.fixture()
def temp_dir(request):
    temp_dir_name = mkdtemp(prefix = 'wamopacker_pytest')
    log.info('created temp dir: {}'.format(temp_dir))

    def remove_temp_dir():
        if temp_dir_name:
            log.info('removing temp dir: {}'.format(temp_dir_name))
            rmtree(temp_dir_name)

    request.addfinalizer(remove_temp_dir)

    return temp_dir_name


@pytest.fixture()
def config_with_files(temp_dir):
    for file_name, file_data in YAML_FILE_DATA.iteritems():
        file_name_full = os.path.join(temp_dir, file_name)
        with open(file_name_full, 'w') as file_object:
            safe_dump(file_data, file_object)

    os.chdir(temp_dir)

    config_file_name_full = os.path.join(temp_dir, YAML_CONFIG_FILE_NAME)
    return Config(config_file_name = config_file_name_full)


@pytest.fixture(
    params = (
        "",
        "a=b",
        "foo: bar: bam",
        """---
string
""",
        """---
- list
""",
        """---
123
""",
    )
)
def config_file_name_bad_data(request, temp_dir):
    file_data = request.param
    file_name_full = os.path.join(temp_dir, YAML_CONFIG_FILE_NAME)
    with open(file_name_full, 'w') as file_object:
        file_object.write(file_data)

    return file_name_full


def test_config_contains_defaults(config):
    for key, val in CONFIG_DEFAULTS.iteritems():
        assert config.expand_parameters(val) == getattr(config, key)


def test_config_reads_env_vars(config, config_with_env):
    assert getattr(config_with_env, TEST_VAR_NAME) == TEST_VAR_VALUE
    assert TEST_VAR_NAME in config_with_env
    assert TEST_VAR_NAME not in config


def test_config_reads_override_list(config, config_with_override_list):
    assert getattr(config_with_override_list, TEST_VAR_NAME) == TEST_VAR_VALUE
    assert TEST_VAR_NAME in config_with_override_list
    assert TEST_VAR_NAME not in config


def test_config_can_set_attribute(config):
    key, val = 'foo', 'bar'
    assert key not in config
    setattr(config, key, val)
    assert key in config
    assert getattr(config, key) == val


def test_config_can_delete_attribute(config):
    key, val = 'foo', 'bar'
    setattr(config, key, val)
    assert key in config
    assert getattr(config, key) == val
    delattr(config, key)
    assert key not in config


def test_config_values(config_values):
    config_value, expected = config_values
    assert config_value.evaluate() == expected


def test_config_values_bad(config_values_bad):
    with pytest.raises(ConfigException):
        config_values_bad.evaluate()


def test_config_uuid(config):
    config_value_a1 = ConfigValue(config, '(( uuid | a ))')
    config_value_a2 = ConfigValue(config, '(( uuid |  a  ))')
    config_value_b = ConfigValue(config, '(( uuid | b ))')

    assert config_value_a1.evaluate()
    assert config_value_b.evaluate()
    assert config_value_a1.evaluate() == config_value_a2.evaluate()
    assert config_value_a1.evaluate() != config_value_b.evaluate()


def test_config_env_var(config_with_env):
    config_value = ConfigValue(config_with_env, '(( env | {} ))'.format(TEST_VAR_KEY))
    assert config_value.evaluate() == TEST_VAR_VALUE


def test_config_env_var_missing(config):
    config_value = ConfigValue(config, '(( env | {} ))'.format(TEST_VAR_KEY))
    with pytest.raises(ConfigException):
        config_value.evaluate()


def test_config_env_var_default(config_with_env):
    default_val = 'default'
    config_value = ConfigValue(config_with_env, '(( env | {} | {} ))'.format(TEST_VAR_KEY, default_val))
    assert config_value.evaluate() == TEST_VAR_VALUE


def test_config_env_var_missing_default(config):
    default_val = 'default'
    config_value = ConfigValue(config, '(( env | {} | {} ))'.format(TEST_VAR_KEY, default_val))
    assert config_value.evaluate() == default_val


@pytest.mark.files
def test_config_files(config_with_files):
    for key, value in YAML_FILE_DATA[YAML_CONFIG_FILE_NAME].iteritems():
        assert getattr(config_with_files, key) == value


@pytest.mark.files
def test_config_files_lookup(config_with_files):
    for key, value in YAML_FILE_DATA[YAML_CONFIG_FILE_NAME].iteritems():
        lookup_key = 'lookup_{}'.format(key)
        setattr(config_with_files, lookup_key, '(( lookup | {} | (( {} )) ))'.format(YAML_LOOKUP_FILE_NAME, key))
        assert getattr(config_with_files, lookup_key) == YAML_FILE_DATA[YAML_LOOKUP_FILE_NAME][value]


@pytest.mark.files
def test_config_files_lookup_missing(config_with_files):
    for key, value in YAML_FILE_DATA[YAML_CONFIG_FILE_NAME].iteritems():
        lookup_key = 'lookup_{}'.format(key)
        setattr(config_with_files, lookup_key, '(( lookup | {} | (( {} )) ))'.format(MISSING_FILE_NAME, key))
        with pytest.raises(ConfigException):
            getattr(config_with_files, lookup_key)


@pytest.mark.files
def test_config_file_missing():
    with pytest.raises(ConfigLoadException):
        Config(config_file_name = MISSING_FILE_NAME)


@pytest.mark.files
def test_config_file_bad_data(config_file_name_bad_data):
    with pytest.raises(ConfigLoadException):
        Config(config_file_name = config_file_name_bad_data)
