#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import os
from tempfile import mkdtemp
from shutil import rmtree
from jinja2 import Environment, FileSystemLoader


class TempDir(object):

    def __init__(self):
        self.path = None

    def __enter__(self):
        if self.path:
            raise IOError('temp dir exists')

        self.path = mkdtemp()

        return self

    def __exit__(self, type, value, traceback):
        if self.path and os.path.isdir(self.path):
            rmtree(self.path)
            self.path = None


class Builder(object):

    def __init__(self, config, target_list):
        self._config = config
        self._target_list = target_list

        self._data_path = self._get_data_path()
        self._template_env = self._get_template_env(self._data_path)

    @staticmethod
    def _get_data_path():
        return os.path.join(os.path.dirname(__file__), 'data')

    @staticmethod
    def _get_template_env(data_path):
        template_path = os.path.join(data_path, 'templates')
        return Environment(loader = FileSystemLoader(template_path), trim_blocks = True)

    def build(self):
        with TempDir() as temp_dir:
            template = self._template_env.get_template('preseed.j2')
            print(template.render(title = 'hello'))
