#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from wamopacker.script import configure_logging
from wamopacker.config import Config
import pytest


configure_logging()


@pytest.fixture()
def config_simple():
    config_str = """---
key1: val1
list1:
- val2
- val3
"""
    return Config(config_string = config_str)
