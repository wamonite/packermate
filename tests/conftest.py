#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from packermate.script import configure_logging
from packermate.config import Config
import pytest
import os
from tempfile import mkdtemp
from shutil import rmtree
import logging


configure_logging()

log = logging.getLogger('packermate.conftest')


@pytest.fixture()
def config_simple():
    config_str = """---
key1: val1
list1:
- val2
- val3
"""
    return Config(config_string = config_str)


@pytest.fixture()
def temp_dir(request):
    temp_dir_name = mkdtemp(prefix = 'packermate_pytest')
    log.info('created temp dir: {}'.format(temp_dir_name))

    current_dir = os.getcwd()

    def remove_temp_dir():
        if temp_dir_name:
            log.info('removing temp dir: {}'.format(temp_dir_name))
            rmtree(temp_dir_name)

        os.chdir(current_dir)

    request.addfinalizer(remove_temp_dir)

    return temp_dir_name
