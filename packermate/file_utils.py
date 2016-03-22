#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import os
from tempfile import mkdtemp
from shutil import rmtree
import json
from string import Template
import yaml
import yaml.scanner
import hashlib
from .process import run_command, ProcessException
from .exception import PackermateException


# https://stackoverflow.com/questions/2890146/how-to-force-pyyaml-to-load-strings-as-unicode-objects

def construct_yaml_str(self, node):
    # Override the default string handling function
    # to always return unicode objects
    return self.construct_scalar(node)

yaml.SafeLoader.add_constructor(u'tag:yaml.org,2002:str', construct_yaml_str)


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
            return json.load(file_object)


class UnarchiveException(PackermateException):
    pass


def unarchive_file(box_file_name, temp_dir):
    try:
        command = "tar -xzvf '{}' -C '{}'".format(box_file_name, temp_dir)
        run_command(command, quiet = True)

    except ProcessException as e:
        raise UnarchiveException("Failed to unarchive file: file='{}' error='{}'".format(box_file_name, e))

    file_list = os.listdir(temp_dir)

    return dict([(file_name, os.path.join(temp_dir, file_name)) for file_name in file_list])


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


def read_yaml_file(file_name):
    try:
        with open(file_name, 'r') as file_object:
            return yaml.safe_load(file_object)

    except (IOError, yaml.scanner.ScannerError):
        return None


def read_yaml_string(data):
    try:
        return yaml.safe_load(data)

    except yaml.scanner.ScannerError:
        return None


def write_json_file(data, file_name):
    with open(file_name, 'w') as file_object:
        json.dump(data, file_object, indent = 4, sort_keys = True)


def get_path_names(file_name, path_list):
    if file_name and file_name[0] == os.path.sep:
        return [file_name]

    return [os.path.join(path, file_name) for path in path_list]
