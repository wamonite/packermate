#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import pytest
from wamopacker.vagrant import *
import json
import os
from semantic_version import Version


@pytest.fixture(
    params = (
        (
            [],  # not dictionary
            False,
        ),
        (
            {},  # no name
            False,
        ),
        (
            {
                'name': 'test'
                # no version list
            },
            False,
        ),
        (
            {
                'name': 'test',
                'versions': []
            },
            True,
        ),
        (
            {
                'name': 'test',
                'versions': [
                    {
                        # 'version': '',
                        'status': 'active',
                        'providers': [
                            {
                                'name': 'virtualbox',
                                'url': '',
                            }
                        ]
                    }
                ]
            },
            False,
        ),
        (
            {
                'name': 'test',
                'versions': [
                    {
                        'version': '',
                        'status': 'unknown',  # invalid status
                        'providers': [
                            {
                                'name': 'virtualbox',
                                'url': '',
                            }
                        ]
                    }
                ]
            },
            False,
        ),
        (
            {
                'name': 'test',
                'versions': [
                    {
                        'version': '0',
                        'status': 'active',
                        'providers': [
                            {
                                'name': 'virtualbox',
                                'url': '',
                            }
                        ]
                    }
                ]
            },
            True,
        ),
    )
)
def vagrant_box_metadata(request, tmpdir):
    data, expected = request.param

    json_text = json.dumps(data)
    temp_file = tmpdir.join("metadata.json")
    temp_file.write(json_text)

    return str(temp_file), expected


def test_vagrant_box_metadata_file_read_write(vagrant_box_metadata):
    file_name, expected = vagrant_box_metadata
    input_file_url = 'file://{}'.format(file_name)
    if expected:
        input_metadata = VagrantBoxMetadata(input_file_url)
        assert input_metadata.name
        assert isinstance(input_metadata.versions, list)

        file_path = os.path.dirname(file_name)
        output_file_name = os.path.join(file_path, 'output.json')
        input_metadata.write(output_file_name)

        with open(file_name, 'r') as input_file_object:
            input_data = json.load(input_file_object)

        with open(output_file_name, 'r') as output_file_object:
            output_data = json.load(output_file_object)

        assert input_data == output_data

    else:
        with pytest.raises(VagrantBoxMetadataException):
            VagrantBoxMetadata(input_file_url)


def test_vagrant_box_metadata_file_write_error():
    metadata = VagrantBoxMetadata(name = 'test')
    with pytest.raises(VagrantBoxMetadataException):
        metadata.write('/path/does/not/exist/metadata.json')


def test_vagrant_box_metadata_file_read_error(tmpdir):
    json_text = "{"
    temp_file = tmpdir.join("metadata.json")
    temp_file.write(json_text)

    file_url = 'file://{}'.format(str(temp_file))
    with pytest.raises(VagrantBoxMetadataException):
        VagrantBoxMetadata(file_url)


@pytest.mark.parametrize(
    'url',
    (
        '',
        'file/does/not/exist',
        '/file/does/not/exist',
        'file://file/does/not/exist',
        'file:///file/does/not/exist',
    )
)
def test_vagrant_box_metadata_url_error(url):
    with pytest.raises(VagrantBoxMetadataException):
        VagrantBoxMetadata(url)


def test_vagrant_box_metadata_create():
    VagrantBoxMetadata(name = 'test')


@pytest.mark.parametrize(
    'version_str,expected',
    (
        ('', None),
        ('a', None),
        (1, None),
        ('0', '0.0.0'),
        ('0.1', '0.1.0'),
        ('0.0.1', '0.0.1'),
        ('01.02.03', '1.2.3'),
        ('1.2.3.4', None),
        ('1.2.3-', None),
        ('1.2.3-4', None),
        ('1.2.3_4', None),
        ('1.2.3+4', None),
        (Version('1.2.3'), '1.2.3'),
        (Version('1.2.3-4'), None),
        (Version('1.2', partial = True), None),
    )
)
def test_vagrant_box_metadata_version(version_str, expected):
    if expected is not None:
        assert str(VagrantBoxMetadata._parse_version(version_str)) == expected

    else:
        with pytest.raises(VagrantBoxMetadataException):
            VagrantBoxMetadata._parse_version(version_str)


@pytest.mark.parametrize(
    'url, expected',
    (
        ('http://does.not.exist', False),
        ('https://github.com/does/not/exist', False),
        ('http://gist.githubusercontent.com/wamonite/e466b76b7c1eb5a38be6/raw/662b52365715722a3d5e7bb4afa948412b9101b7/metadata.json', True),
        ('https://gist.githubusercontent.com/wamonite/e466b76b7c1eb5a38be6/raw/662b52365715722a3d5e7bb4afa948412b9101b7/metadata.json', True),
    )
)
def test_vagrant_box_metadata_download_url(url, expected):
    if expected:
        VagrantBoxMetadata(url)

    else:
        with pytest.raises(VagrantBoxMetadataException):
            VagrantBoxMetadata(url)
