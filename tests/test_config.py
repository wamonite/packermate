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
import yaml
import struct
import base64
import tarfile


log = logging.getLogger('wamopacker.test_config')

TEST_VAR_NAME = 'TEST_ENV_VAR'
TEST_VAR_KEY = ENV_VAR_PREFIX + TEST_VAR_NAME
TEST_VAR_VALUE = 'meh'
YAML_CONFIG_FILE_NAME = 'config.yml'
YAML_LOOKUP_FILE_NAME = 'lookup.yml'
YAML_LIST_FILE_NAME = 'list.yml'
YAML_FILE_DATA = {
    YAML_CONFIG_FILE_NAME: {
        'fizz': 'abc',
        'buzz': 'def'
    },
    YAML_LOOKUP_FILE_NAME: {
        'abc': 'easy as',
        'def': '123'
    },
    YAML_LIST_FILE_NAME: [
        '456',
        'ghi'
    ]
}
YAML_BAD_STRING_LIST = (
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
MISSING_FILE_NAME = '/file/does/not/exist.yml'
TGZ_FILE_NAME = 'data.tgz'


# Config default fixtures

@pytest.fixture()
def no_env_vars():
    if TEST_VAR_KEY in os.environ:
        del(os.environ[TEST_VAR_KEY])


@pytest.fixture()
def with_env_vars():
    os.environ[TEST_VAR_KEY] = TEST_VAR_VALUE


@pytest.fixture()
def config_no_env_vars(no_env_vars):
    return Config()


@pytest.fixture()
def config_with_env_vars(with_env_vars):
    return Config()


# ConfigValue

@pytest.fixture()
def config_value_config(with_env_vars):
    config_str = """---
foo: 123
bar: '456'
ref: foo
empty: ''
"""
    return Config(config_string = config_str)


@pytest.mark.parametrize(
    'config_val_str, expected',
    (
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
        ('((((ref))))', '123'),
        ('(( foo ))(( bar ))', '123456'),
        ('(( foo )) (( bar ))', '123 456'),
        ('(( foo ))  (( bar ))', '123  456'),
        ('test ((foo))', 'test 123'),
        (' test ((foo))', 'test 123'),
        ('test ((foo)) ', 'test 123'),
        ('test  ((foo)) ', 'test  123'),
        ('((foo)) test', '123 test'),
        ('((foo)) test ', '123 test'),
        (' ((foo)) test', '123 test'),
        ('((foo))  test', '123  test'),
        ('test ((foo)) ((bar))', 'test 123 456'),
        ('test  ((foo))  ((bar))', 'test  123  456'),
        ('(( default | foo ))', '123'),
        ('(( default | foo | ))', '123'),
        ('(( default | foo | bar ))', '123'),
        ('(( default | foo | (( bar )) ))', '123'),
        ('(( default | (( ref )) ))', '123'),
        ('(( default | (( ref )) | ))', '123'),
        ('(( default | (( ref )) | bar ))', '123'),
        ('(( default | (( ref )) | (( bar )) ))', '123'),
        ('(( default | empty ))', ''),
        ('(( default | empty | ))', ''),
        ('(( default | empty | bar ))', 'bar'),
        ('(( default | empty | (( bar )) ))', '456'),
        ('(( default | undefined ))', ''),
        ('(( default | undefined | ))', ''),
        ('(( default | undefined | bar ))', 'bar'),
        ('(( default | undefined | (( bar )) ))', '456'),
        ('(( env | {} ))'.format(TEST_VAR_KEY), TEST_VAR_VALUE),
        ('(( lookup_optional | {} | foo ))'.format(MISSING_FILE_NAME), 'foo'),
        ('(( lookup_optional | {} | (( foo )) ))'.format(MISSING_FILE_NAME), '123'),
        ('(( base64_encode | 123 ))', 'MTIz'),
        ('(( base64_decode | (( base64_encode | 123 )) ))', '123'),
    ),
)
def test_config_value(config_value_config, config_val_str, expected):
    config_value = ConfigValue(config_value_config, config_val_str)
    assert config_value.evaluate() == expected


@pytest.mark.parametrize(
    'config_val_str',
    (
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
        '(( default ))',
        '(( default | ))',
        '(( default | | ))',
        '(( default | | 123 ))',
        '(( env | ))',
        '(( env | UNDEFINED_ENV_VAR ))',
        '(( uuid | ))',
        '(( lookup ))',
        '(( lookup | {} ))'.format(MISSING_FILE_NAME),
        '(( lookup | {} | test ))'.format(MISSING_FILE_NAME),
    )
)
def test_config_value_error(config_value_config, config_val_str):
    config_value = ConfigValue(config_value_config, config_val_str)
    with pytest.raises(ConfigException):
        config_value.evaluate()


def _write_file_data(file_object, file_type, file_data):
    if file_type in ('text', 'data'):
        file_object.write(file_data)


@pytest.fixture()
def config_binary_files(temp_dir):
    file_lookup = {
        'text': ('file.txt', '0123456789'),
        'data': ('data.txt', reduce(lambda x, y: x + y, map(lambda x: struct.pack('B', x), range(256)))),
    }

    file_output = {}
    for file_type, file_info in file_lookup.iteritems():
        file_name, file_data = file_info
        file_name_full = os.path.join(temp_dir, file_name)

        with open(file_name_full, 'wb') as file_object:
            _write_file_data(file_object, file_type, file_data)

        file_output[file_type] = (file_name_full, file_data)

    return file_output


@pytest.fixture()
def config_binary_archive(temp_dir, config_binary_files):
    tar_file_name = os.path.join(temp_dir, TGZ_FILE_NAME)
    with tarfile.open(tar_file_name, "w:gz") as tar_file:
        for file_type, file_info in config_binary_files.iteritems():
            file_name, file_data = file_info
            file_name_short = os.path.basename(file_name)
            tar_file.add(file_name, arcname = file_name_short)

    return config_binary_files, tar_file_name


def check_file_content(file_type, result, expected):
    if file_type == 'data':
        result = base64.b64decode(result)

    assert result == expected


def test_config_value_files(config_binary_files):
    for file_type, file_info in config_binary_files.iteritems():
        file_name, file_data = file_info

        config_str = "---\nfile_val: (( file | {} | {} ))".format(file_type, file_name)

        config = Config(config_string = config_str)

        result = config.file_val

        check_file_content(file_type, result, file_data)


def test_config_value_archive(config_binary_archive):
    config_binary_files, tar_file_name = config_binary_archive

    for file_type, file_info in config_binary_files.iteritems():
        file_name, file_data = file_info
        file_name_short = os.path.basename(file_name)

        config_str = "---\nfile_val: (( file | tgz | {} | {} ))".format(tar_file_name, file_name_short)

        config = Config(config_string = config_str)

        result = config.file_val

        check_file_content('data', result, file_data)


def test_config_value_archive_glob(config_binary_archive):
    config_binary_files, tar_file_name = config_binary_archive

    for file_type, file_info in config_binary_files.iteritems():
        file_name, file_data = file_info
        file_name_short = '*' + file_name[-5:]

        config_str = "---\nfile_val: (( file | tgz | {} | {} ))".format(tar_file_name, file_name_short)

        config = Config(config_string = config_str)

        result = config.file_val

        check_file_content('data', result, file_data)


# Config attributes and lookups

def test_config_contains_defaults(config_no_env_vars):
    for key, val in CONFIG_DEFAULTS.iteritems():
        assert config_no_env_vars.expand_parameters(val) == getattr(config_no_env_vars, key)


def test_config_reads_env_vars(config_no_env_vars, config_with_env_vars):
    assert TEST_VAR_NAME not in config_no_env_vars

    assert getattr(config_with_env_vars, TEST_VAR_NAME) == TEST_VAR_VALUE
    assert TEST_VAR_NAME in config_with_env_vars


@pytest.mark.parametrize(
    'override_list, key, val',
    (
        (['{}={}'.format(TEST_VAR_NAME, TEST_VAR_VALUE)], TEST_VAR_NAME, TEST_VAR_VALUE),
    )
)
def test_config_reads_override_list(override_list, key, val):
    config = Config(override_list = override_list)

    assert getattr(config, key) == val
    assert key in config


@pytest.mark.parametrize(
    'override_list',
    (
        ['test'],
    )
)
def test_config_reads_override_list_error(override_list):
    with pytest.raises(ConfigException):
        Config(override_list = override_list)


def test_config_can_set_attribute(config_no_env_vars):
    key, val = 'foo', 'bar'
    assert key not in config_no_env_vars
    setattr(config_no_env_vars, key, val)
    assert key in config_no_env_vars
    assert getattr(config_no_env_vars, key) == val


def test_config_can_delete_attribute(config_no_env_vars):
    key, val = 'foo', 'bar'
    setattr(config_no_env_vars, key, val)
    assert key in config_no_env_vars
    assert getattr(config_no_env_vars, key) == val
    delattr(config_no_env_vars, key)
    assert key not in config_no_env_vars


def test_config_set_none_deletes_attribute(config_no_env_vars):
    key, val = 'foo', 'bar'
    setattr(config_no_env_vars, key, val)
    assert key in config_no_env_vars
    assert getattr(config_no_env_vars, key) == val
    setattr(config_no_env_vars, key, None)
    assert key not in config_no_env_vars


def test_config_uuid(config_no_env_vars):
    config_value_a1 = ConfigValue(config_no_env_vars, '(( uuid | a ))')
    config_value_a2 = ConfigValue(config_no_env_vars, '(( uuid |  a  ))')
    config_value_b = ConfigValue(config_no_env_vars, '(( uuid | b ))')

    assert config_value_a1.evaluate()
    assert config_value_b.evaluate()
    assert config_value_a1.evaluate() == config_value_a2.evaluate()
    assert config_value_a1.evaluate() != config_value_b.evaluate()


def test_config_env_var(config_with_env_vars):
    config_value = ConfigValue(config_with_env_vars, '(( env | {} ))'.format(TEST_VAR_KEY))
    assert config_value.evaluate() == TEST_VAR_VALUE


def test_config_env_var_missing(config_no_env_vars):
    config_value = ConfigValue(config_no_env_vars, '(( env | {} ))'.format(TEST_VAR_KEY))
    with pytest.raises(ConfigException):
        config_value.evaluate()


def test_config_env_var_default(config_with_env_vars):
    default_val = 'default'
    config_value = ConfigValue(config_with_env_vars, '(( env | {} | {} ))'.format(TEST_VAR_KEY, default_val))
    assert config_value.evaluate() == TEST_VAR_VALUE


def test_config_env_var_missing_default(config_no_env_vars):
    default_val = 'default'
    config_value = ConfigValue(config_no_env_vars, '(( env | {} | {} ))'.format(TEST_VAR_KEY, default_val))
    assert config_value.evaluate() == default_val


# Config from file

@pytest.fixture()
def yaml_file_lookup(temp_dir):
    file_name_lookup = {}
    for file_name, file_data in YAML_FILE_DATA.iteritems():
        file_name_full = os.path.join(temp_dir, file_name)
        file_name_lookup[file_name] = file_name_full

        with open(file_name_full, 'w') as file_object:
            yaml.safe_dump(file_data, file_object, default_flow_style = False)

    os.chdir(temp_dir)

    return file_name_lookup


@pytest.fixture()
def config_with_files(yaml_file_lookup):
    return Config(config_file_name = yaml_file_lookup[YAML_CONFIG_FILE_NAME])


def test_config_file_missing():
    with pytest.raises(ConfigLoadException):
        Config(config_file_name = MISSING_FILE_NAME)


@pytest.mark.parametrize(
    'include_str',
    (
        'include_optional:\n- {MISSING_FILE_NAME}',
        'include:\n- {YAML_LOOKUP_FILE_NAME}',
        'include_optional:\n- {YAML_LOOKUP_FILE_NAME}',
    )
)
def test_config_file_include(yaml_file_lookup, include_str):
    config_file_name = yaml_file_lookup[YAML_CONFIG_FILE_NAME]
    with open(config_file_name, 'a') as file_object:
        file_object.write(include_str.format(**(globals())))

    Config(config_file_name = config_file_name)


@pytest.mark.parametrize(
    'include_str',
    (
        'include:',
        'include: {MISSING_FILE_NAME}',
        'include:\n- {MISSING_FILE_NAME}',
        'include_optional:',
        'include_optional: {MISSING_FILE_NAME}',
        'include:\n- {YAML_LIST_FILE_NAME}',
        'include_optional:\n- {YAML_LIST_FILE_NAME}',
    )
)
def test_config_file_include_errors(yaml_file_lookup, include_str):
    config_file_name = yaml_file_lookup[YAML_CONFIG_FILE_NAME]
    with open(config_file_name, 'a') as file_object:
        file_object.write(include_str.format(**(globals())))

    with pytest.raises(ConfigException):
        Config(config_file_name = config_file_name)


def test_config_include_missing(config_with_files):
    with pytest.raises(ConfigLoadException):
        Config(config_file_name = MISSING_FILE_NAME)


def test_config_files(config_with_files):
    for key, value in YAML_FILE_DATA[YAML_CONFIG_FILE_NAME].iteritems():
        assert getattr(config_with_files, key) == value


@pytest.mark.parametrize(
    'lookup_str, expected',
    (
        ('(( lookup | {YAML_LOOKUP_FILE_NAME} | def ))', '123'),
        ('(( lookup_optional | {YAML_LOOKUP_FILE_NAME} | def ))', '123'),
    )
)
def test_config_files_lookup(config_with_files, lookup_str, expected):
    lookup_key = 'lookup_key'
    setattr(config_with_files, lookup_key, lookup_str.format(**(globals())))
    assert getattr(config_with_files, lookup_key) == expected


@pytest.mark.parametrize(
    'lookup_str',
    (
        '(( lookup | {YAML_LOOKUP_FILE_NAME}))',
        '(( lookup | {YAML_LIST_FILE_NAME} | test ))',
        '(( lookup_optional | {YAML_LIST_FILE_NAME} | test ))',
    )
)
def test_config_files_lookup_error(config_with_files, lookup_str):
    lookup_key = 'lookup_key'
    setattr(config_with_files, lookup_key, lookup_str.format(**(globals())))
    with pytest.raises(ConfigException):
        getattr(config_with_files, lookup_key)


@pytest.fixture(
    params = YAML_BAD_STRING_LIST
)
def yaml_file_with_bad_data(request, temp_dir):
    file_data = request.param
    file_name_full = os.path.join(temp_dir, YAML_CONFIG_FILE_NAME)
    with open(file_name_full, 'w') as file_object:
        file_object.write(file_data)

    return file_name_full


def test_config_file_bad_data(yaml_file_with_bad_data):
    with pytest.raises(ConfigLoadException):
        Config(config_file_name = yaml_file_with_bad_data)


# Config from string

@pytest.mark.parametrize(
    'config_data',
    (
        {
            'a': 1,
            'b': 2,
        },
        {
            'a': [
                1,
                2,
                {
                    'b': 3,
                    'c': 'def'
                }
            ],
        },
    )
)
def test_config_from_string(config_data):
    config_data_string = yaml.safe_dump(config_data, default_flow_style = False)
    config = Config(config_string = config_data_string)
    for key, val in config_data.iteritems():
        check_expected(getattr(config, key), val)


def check_expected(data, expected):
    if isinstance(expected, dict):
        for key, val in expected.iteritems():
            check_expected(data[key], val)

    elif isinstance(expected, list):
        for data_val, expected_val in zip(data, expected):
            check_expected(data_val, expected_val)

    else:
        assert data == expected


@pytest.mark.parametrize(
    'yaml_bad_str',
    YAML_BAD_STRING_LIST
)
def test_config_from_string_bad(yaml_bad_str):
    with pytest.raises(ConfigLoadException):
        Config(config_string = yaml_bad_str)


@pytest.mark.parametrize(
    'config_str, expected_str',
    (
        (
            """---
key1:
  - key2: val1
    key3:
      - key4: val2
        key5: val3
""",
            '\n'.join([
                'key1:',
                '  - key2: val1',
                '    key3:',
                '      - key4: val2',
                '        key5: val3',
            ])
        ),
    )
)
def test_config_print(config_str, expected_str):
    config = Config(config_string = config_str)
    for default_key in CONFIG_DEFAULTS:
        delattr(config, default_key)

    config_dump = str(config)

    assert config_dump == expected_str

    config_repr = repr(config)
    expected_repr = '\n'.join([
        'Config[',
        config_dump,
        ']'
    ])
    assert config_repr == expected_repr


@pytest.mark.parametrize(
    'provider, key, expected',
    (
        ('', 'key1', None),
        (None, 'key1', 'val1'),
        (None, 'key2', None),
        ('aws', 'key1', 'val1'),
        ('aws', 'key2', None),
        (None, 'key3', 'val3'),
        ('aws', 'key3', 'val4'),
        ('virtualbox', 'key3', 'val3'),
    )
)
def test_config_provider_get(provider, key, expected):
    config_str = """---
key1: val1
key3: val3
aws_key3: val4
"""
    config = Config(config_string = config_str)
    if provider is not None:
        if provider:
            config = config.provider(provider)

        else:
            with pytest.raises(ConfigException):
                config.provider(provider)

            return

    assert getattr(config, key) == expected


def test_config_provider_set():
    config_str = """---
key1: val1
"""
    config = Config(config_string = config_str)
    config_provider = config.provider('aws')

    assert 'key2' not in config
    assert 'key2' not in config_provider

    config.key2 = 'val2'
    assert 'key2' in config
    assert 'key2' in config_provider

    del config_provider.key2
    assert 'key2' not in config
    assert 'key2' not in config_provider

    config_provider.key2 = 'val2'
    assert 'key2' not in config
    assert 'key2' in config_provider

    del config_provider.key2
    assert 'key2' not in config
    assert 'key2' not in config_provider

    config_provider.aws_key2 = 'val2'
    assert 'aws_key2' in config
    assert 'aws_key2' in config_provider

    del config_provider.aws_key2
    assert 'aws_key2' not in config
    assert 'aws_key2' not in config_provider
