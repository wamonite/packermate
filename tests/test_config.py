#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import pytest
from wamopacker.config import (Config, CONFIG_DEFAULTS, ENV_VAR_PREFIX)
import logging
import os


log = logging.getLogger('wamopacker.test_config')

TEST_VAR_NAME = 'TEST_ENV_VAR'
TEST_VAR_KEY = ENV_VAR_PREFIX + TEST_VAR_NAME
TEST_VAR_VALUE = 'blah'


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
