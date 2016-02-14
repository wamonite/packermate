#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import pytest
from wamopacker.vagrant import (
    BoxMetadata,
    BoxMetadataException,
    parse_version,
    BoxVersionException,
    BoxInventory,
    BoxInventoryException,
)
import json
import os
from semantic_version import Version
from mock import patch, Mock
from wamopacker.process import ProcessException


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


def test_box_metadata_file_read_write(vagrant_box_metadata):
    file_name, expected = vagrant_box_metadata
    input_file_url = 'file://{}'.format(file_name)
    if expected:
        input_metadata = BoxMetadata(input_file_url)
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
        with pytest.raises(BoxMetadataException):
            BoxMetadata(input_file_url)


def test_box_metadata_file_write_error():
    metadata = BoxMetadata(name = 'test')
    with pytest.raises(BoxMetadataException):
        metadata.write('/path/does/not/exist/metadata.json')


def test_box_metadata_file_read_error(tmpdir):
    json_text = "{"
    temp_file = tmpdir.join("metadata.json")
    temp_file.write(json_text)

    file_url = 'file://{}'.format(str(temp_file))
    with pytest.raises(BoxMetadataException):
        BoxMetadata(file_url)


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
def test_box_metadata_url_error(url):
    with pytest.raises(BoxMetadataException):
        BoxMetadata(url)


def test_box_metadata_create():
    BoxMetadata(name = 'test')


@pytest.mark.parametrize(
    'version_str, expected',
    (
        ('', None),
        ('a', None),
        ('0', '0.0.0'),
        ('0.1', '0.1.0'),
        ('0.0.1', '0.0.1'),
        ('01.02.03', '1.2.3'),
        (1, '1.0.0'),
        (1.02, '1.2.0'),
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
def test_box_metadata_version(version_str, expected):
    if expected is not None:
        assert str(parse_version(version_str)) == expected

    else:
        with pytest.raises(BoxVersionException):
            parse_version(version_str)


@pytest.mark.parametrize(
    'url, expected',
    (
        ('http://does.not.exist', False),
        ('https://github.com/does/not/exist', False),
        ('http://gist.githubusercontent.com/wamonite/e466b76b7c1eb5a38be6/raw/662b52365715722a3d5e7bb4afa948412b9101b7/metadata.json', True),
        ('https://gist.githubusercontent.com/wamonite/e466b76b7c1eb5a38be6/raw/662b52365715722a3d5e7bb4afa948412b9101b7/metadata.json', True),
    )
)
def test_box_metadata_download_url(url, expected):
    if expected:
        BoxMetadata(url)

    else:
        with pytest.raises(BoxMetadataException):
            BoxMetadata(url)


@pytest.mark.parametrize(
    'version, version_list, insert_expected, match_expected',
    (
        ('1.0.0', [], None, None),
        ('1.0.0', ['0.1.0'], 0, None),
        ('0.1.0', ['1.0.0'], None, None),
        ('1.1.1', ['1.2.0', '1.0.0'], 1, None),
        ('1.2.0', ['1.2.0', '1.1.1', '1.0.0'], None, 0),
        ('1.1.1', ['1.2.0', '1.1.1', '1.0.0'], None, 1),
        ('1.0.0', ['1.2.0', '1.1.1', '1.0.0'], None, 2),
    )
)
def test_box_metadata_get_add_index(version, version_list, insert_expected, match_expected):
    test_version = parse_version(version)
    test_version_list = [Version(val) for val in version_list]
    insert_at, match_at = BoxMetadata._get_version_index(test_version, test_version_list)
    assert insert_at == insert_expected
    assert match_at == match_expected


@pytest.mark.parametrize(
    'provider_name, provider_list, expected_info, expected_list',
    (
        (
            'aws',
            [],
            {'name': 'aws'},
            [{'name': 'aws'}],
        ),
        (
            'aws',
            [{'name': 'aws'}],
            {'name': 'aws'},
            [{'name': 'aws'}],
        ),
        (
            'virtualbox',
            [{'name': 'aws'}],
            {'name': 'virtualbox'},
            [{'name': 'aws'}, {'name': 'virtualbox'}],
        ),
        (
            'virtualbox',
            [{'name': 'aws'}, {'name': 'virtualbox'}],
            {'name': 'virtualbox'},
            [{'name': 'aws'}, {'name': 'virtualbox'}],
        ),
    )
)
def test_box_metadata_get_provider(provider_name, provider_list, expected_info, expected_list):
    provider_new = BoxMetadata._get_provider(provider_name, provider_list)
    assert provider_new == expected_info
    assert provider_list == expected_list


@pytest.mark.parametrize(
    'version_list, version_order',
    (
        (['1.0.0'], ['1.0.0']),
        (['1.0.0', '1.0.0'], ['1.0.0']),
        (['1.1.0', '1.0.0'], ['1.1.0', '1.0.0']),
        (['1.0.0', '1.1.0'], ['1.1.0', '1.0.0']),
    )
)
@pytest.mark.parametrize(
    'provider, url, checksum, checksum_type',
    (
        ('virtualbox', 'test1', None, None),
        ('aws', 'test2', '123', None),
        ('vmware', 'test3', '456', 'md5'),
    )
)
def test_box_metadata_add_version(version_list, version_order, provider, url, checksum, checksum_type):
    metadata = BoxMetadata(name = 'test')
    for version_val in [parse_version(val) for val in version_list]:
        metadata.add_version(version_val, provider, url, checksum, checksum_type)

    for index, version_info in enumerate(metadata.versions):
        assert version_order[index] == str(version_info['version'])
        provider_info = {
            'name': provider,
            'url': url,
        }
        if checksum and checksum_type:
            provider_info['checksum'] = checksum
            provider_info['checksum_type'] = checksum_type

        assert version_info['providers'] == [provider_info]


@pytest.fixture(
    params = (
        (
            None,
            None
        ),
        (
            '',
            {}
        ),
        (
            'vagrant-box',
            {}
        ),
        (
            'vagrant-box ()',
            {}
        ),
        (
            'vagrant-box (aws,)',
            {}
        ),
        (
            'vagrant-box (aws, abc)',
            {}
        ),
        (
            'vagrant-box (aws, 0)',
            {
                'vagrant-box': {
                    'aws': [Version('0.0.0')]
                }
            }
        ),
        (
            'vagrant-box (aws, 0)\nvagrant-box (virtualbox, 1.2)',
            {
                'vagrant-box': {
                    'aws': [Version('0.0.0')],
                    'virtualbox': [Version('1.2.0')]
                }
            }
        ),
        (
            'vagrant-box (aws, 0)\nanother-box (virtualbox, 1.2)',
            {
                'vagrant-box': {
                    'aws': [Version('0.0.0')],
                },
                'another-box': {
                    'virtualbox': [Version('1.2.0')]
                }
            }
        ),
    )
)
def mock_box_list(request):
    command_output, expected = request.param

    def run_command_side_effect(run_command):
        if run_command.startswith('vagrant box list'):
            if command_output is None:
                raise ProcessException('error')

            else:
                return command_output.splitlines()

        else:
            raise ValueError(run_command)

    mock_run_command = Mock(side_effect = run_command_side_effect)
    patcher = patch('wamopacker.vagrant.run_command', mock_run_command)
    patcher.start()

    def stop_patcher():
        patcher.stop()

    request.addfinalizer(stop_patcher)

    return expected


def test_box_inventory(mock_box_list):
    inventory = BoxInventory()
    if mock_box_list is not None:
        assert inventory.list == mock_box_list

    else:
        with pytest.raises(BoxInventoryException):
            inventory.list


def test_box_inventory_installed(mock_box_list):
    if mock_box_list is None:
        return

    inventory = BoxInventory()
    for box_name, box_lookup in mock_box_list.iteritems():
        for provider in ('aws', 'virtualbox', 'unknown'):
            print('check installed: missing-box {}'.format(provider))

            assert inventory.installed('missing-box', provider) == False

            print('check installed: {} {}'.format(box_name, provider))

            result = inventory.installed(box_name, provider)
            version_list = box_lookup.get(provider, [])
            assert result == bool(version_list)

            for version in (Version('0.0.0'), Version('1.0.0'), 'test', 123):
                print('check installed: {} {} {}'.format(box_name, provider, version))

                try:
                    parse_version(version)

                except BoxVersionException:
                    with pytest.raises(BoxVersionException):
                        inventory.installed(box_name, provider, version)

                else:
                    result = version in version_list
                    assert result == inventory.installed(box_name, provider, version)


@pytest.fixture(
    params = (True, False)
)
def mock_box_add(request):
    run_ok = request.param

    class LocalInventory(object):

        def __init__(self):
            self._line_list = []

        def get_text(self):
            return self._line_list

        def add_line(self, line):
            self._line_list.append(line)

        def run_command_side_effect(self, run_command):
            if run_command.startswith('vagrant box add'):
                if run_ok:
                    command_split = run_command.split(' ')
                    if len(command_split) > 6:
                        self.add_line('{}    ({}, {})'.format(command_split[5], command_split[4], command_split[7]))

                    else:
                        self.add_line('{}  ({}, 0)'.format(command_split[5], command_split[4]))

                else:
                    raise ProcessException('error')

            elif run_command.startswith('vagrant box list'):
                return self.get_text()

            else:
                raise ValueError(run_command)

    local_inventory = LocalInventory()
    mock_run_command = Mock(side_effect = local_inventory.run_command_side_effect)
    patcher = patch('wamopacker.vagrant.run_command', mock_run_command)
    patcher.start()

    def stop_patcher():
        patcher.stop()

    request.addfinalizer(stop_patcher)

    return run_ok


@pytest.mark.parametrize(
    'name, provider, version, expected',
    (
        (
            'vagrant-box',
            'aws',
            None,
            {
                'vagrant-box': {
                    'aws': [Version('0.0.0')]
                }
            }
        ),
        (
            'vagrant-box',
            'aws',
            '1.2.3',
            {
                'vagrant-box': {
                    'aws': [Version('1.2.3')]
                }
            }
        ),
    )
)
def test_box_inventory_add(mock_box_add, name, provider, version, expected):
    inventory = BoxInventory()
    if mock_box_add:
        inventory.install(name, provider, version)

        assert inventory.list == expected

    else:
        with pytest.raises(BoxInventoryException):
            inventory.install(name, provider, version)
