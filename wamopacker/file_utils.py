#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import os
from tempfile import mkdtemp
from shutil import rmtree
from json import load, dump
from string import Template
import hashlib


class TempDir(object):

    def __init__(self, root_dir = None):
        self._path = None
        self._root_dir = root_dir

    @property
    def path(self):
        return self._path

    def __enter__(self):
        if not self.path:
            self._path = mkdtemp(dir = self._root_dir)

        return self

    def __exit__(self, type, value, traceback):
        if self._path and os.path.isdir(self._path):
            rmtree(self._path)
            self._path = None

        # ensure any exception is reraised
        return False


class DataDir(object):

    def __init__(self, root_dir = None):
        if root_dir:
            self._root_dir = root_dir
        else:
            self._root_dir = os.path.join(os.path.dirname(__file__), 'data')

    def read_template(self, file_name):
        template_path = os.path.join(self._root_dir, 'templates')
        template_file_name = os.path.join(template_path, '{}.template'.format(file_name))
        with open(template_file_name, 'rb') as file_object:
            return Template(file_object.read())

    def read_json(self, file_name):
        file_name = os.path.join(self._root_dir, '{}.json'.format(file_name))
        with open(file_name, 'r') as file_object:
            return load(file_object)


def get_md5_sum(file_name):
    md5 = hashlib.md5()
    with open(file_name, 'rb') as file_object:
        while True:
            data = file_object.read(1024 * 1024)
            if len(data) > 0:
                md5.update(data)

            else:
                break

    return md5.hexdigest()


def write_json_file(json_object, file_name):
    with open(file_name, 'w') as file_object:
        dump(json_object, file_object, indent = 4, sort_keys = True)
