#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import pytest
from wamopacker.file_utils import *
import uuid
from string import Template


# TempDir

def test_temp_dir_create():
    temp_dir = TempDir()
    assert temp_dir.path is None

    with temp_dir:
        temp_path = temp_dir.path
        assert os.path.exists(temp_path)
        assert os.path.isdir(temp_path)
        assert os.access(temp_path, os.W_OK)

        with temp_dir as temp_dir_sub:
            assert temp_dir == temp_dir_sub

    assert temp_dir.path is None
    assert not os.path.exists(temp_path)


def test_temp_dir_create_root():
    with TempDir() as temp_dir_root:
        with TempDir(root_dir = temp_dir_root.path) as temp_dir:
            assert temp_dir.path.startswith(temp_dir_root.path)


class TempDirException(Exception):
    pass


def test_temp_dir_exception():
    with pytest.raises(TempDirException):
        with TempDir() as temp_dir:
            temp_path = temp_dir.path
            assert os.path.exists(temp_path)

            raise TempDirException('message')

    assert temp_path and not os.path.exists(temp_path)


# DataDir

def test_data_dir_template_root():
    with TempDir() as temp_dir:
        template_path = os.path.join(temp_dir.path, 'templates')
        os.makedirs(template_path)

        data = uuid.uuid4().hex
        with open(os.path.join(template_path, 'test.template'), 'w') as file_object:
            file_object.write(data)

        data_dir = DataDir(root_dir = temp_dir.path)
        template_file_data = data_dir.read_template('test')

        assert template_file_data.substitute() == data


def test_data_dir_template_existing():
    data_dir = DataDir()
    template_file_data = data_dir.read_template('preseed.cfg')
    assert isinstance(template_file_data, Template)


def test_data_dir_json_read_write():
    with TempDir() as temp_dir:
        temp_path = temp_dir.path

        data = {
            'val': uuid.uuid4().hex
        }
        write_json_file(data, os.path.join(temp_path, 'test.json'))

        data_dir = DataDir(root_dir = temp_dir.path)
        file_data = data_dir.read_json('test')

        assert file_data == data


# get_md5_sum

def test_md5_sum():
    with TempDir() as temp_dir:
        temp_path = temp_dir.path

        file_name = os.path.join(temp_path, 'test_data')
        file_data = '0123456789\nabcdef'
        with open(file_name, 'wb') as file_object:
            file_object.write(file_data)

        assert get_md5_sum(file_name) == 'efc666baad0a87908227c9eb5564dd56'
