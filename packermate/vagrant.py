#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from urlparse import urlparse
import requests
from requests.exceptions import ConnectionError
import json
from semantic_version import Version
from .file_utils import write_json_file, get_md5_sum
from datetime import datetime
from .process import run_command, ProcessException
import re
import os
from .exception import PackermateException
import logging


REPACKAGED_VAGRANT_BOX_FILE_NAME = 'package.box'


log = logging.getLogger('packermate.vagrant')


__all__ = [
    'BoxMetadata',
    'BoxMetadataException',
    'parse_version',
    'BoxInventory',
    'BoxInventoryException',
    'parse_vagrant_export',
    'PublishException',
    'publish_vagrant_box',
]


class BoxVersionException(PackermateException):
    pass


def parse_version(version_val):
    if not version_val:
        raise BoxVersionException("Invalid version value: '{}'".format(version_val))

    elif isinstance(version_val, Version):
        if version_val.partial or version_val.prerelease or version_val.build:
            raise BoxVersionException("Partial, pre-release and build versions unsupported: '{}'".format(version_val))

        return version_val

    else:
        if not isinstance(version_val, basestring):
            version_val = str(version_val)

        version_split = version_val.split('.')
        if len(version_split) > 3:
            raise BoxVersionException("Invalid number of version elements: '{}'".format(version_val))

        # strip leading zeroes and ensure not a partial version
        version_parts = map(
            lambda val: val.lstrip('0') if len(val) > 1 else val,
            map(
                lambda element, default: element or default,
                version_split[:3],
                ['0'] * 3
            )
        )
        for version_part in version_parts:
            if not version_part.isdigit():
                raise BoxVersionException("Pre-release and build versions unsupported: '{}'".format(version_val))

        return Version('.'.join(version_parts))


def get_version_index(version_val, version_list):
    assert isinstance(version_val, Version)

    insert_at = None
    match_at = None
    for index, list_val in enumerate(version_list):
        assert isinstance(list_val, Version)

        if version_val == list_val:
            match_at = index
            break

        if version_val > list_val:
            insert_at = index
            break

    return insert_at, match_at


class BoxMetadataException(PackermateException):
    pass


class BoxMetadata(object):

    def __init__(self, url = None, name = None):
        if url:
            url_data = self._load_url(url)
            try:
                self._metadata = json.loads(url_data)

            except ValueError:
                raise BoxMetadataException('Failed to decode JSON form metadata file')

        elif name:
            self._metadata = self._create(name)

        else:
            raise BoxMetadataException('No URL or name specified')

        self._validate()

    @staticmethod
    def _load_url(url):
        result = urlparse(url)

        if result.scheme == 'file':
            try:
                with open(result.path, 'r') as file_object:
                    url_data = file_object.read()

            except IOError as e:
                raise BoxMetadataException("Failed to load file: file='{}' error='{}'".format(result.path, e))

        elif result.scheme in ('http', 'https'):
            try:
                response = requests.get(url)

                if response.status_code != 200:
                    raise BoxMetadataException(
                        "Failed to download URL: url='{}' status_code={}".format(url, response.status_code),
                        response.status_code
                    )

                url_data = response.text

            except ConnectionError:
                raise BoxMetadataException('Failed to download URL: {}'.format(url))

        else:
            raise BoxMetadataException('Unsupported URL scheme: {}'.format(result.scheme))

        return url_data

    @staticmethod
    def _create(name):
        return {
            'name': name,
            'versions': [],
        }

    @property
    def name(self):
        return self._metadata['name']

    @property
    def versions(self):
        return self._parse_version_list(self._metadata['versions'])

    def _validate(self):
        if not isinstance(self._metadata, dict):
            raise BoxMetadataException("Metadata does not contain a dictionary")

        if not self._metadata.get('name'):
            raise BoxMetadataException("Metadata does not have a name")

        version_list = self._metadata.get('versions')
        if not isinstance(version_list, list):
            raise BoxMetadataException("Metadata does not have any versions")

        self._parse_version_list(version_list)

    @staticmethod
    def _parse_version_list(version_list):
        parsed_list = []
        for version_lookup in version_list:
            status_str = version_lookup.get('status', '<not present>')
            if status_str not in ('active', 'revoked'):
                raise BoxMetadataException("Unknown version status: '{}'".format(status_str))

            if 'version' not in version_lookup:
                raise BoxMetadataException("Version value missing")

            version_str = version_lookup['version']
            version_val = parse_version(version_str)
            provider_info_list = version_lookup.get('providers', [])

            parsed_version = {
                'version_str': version_str,
                'version': version_val,
                'status': status_str,
                'providers': provider_info_list,
            }

            parsed_list.append(parsed_version)

        return parsed_list

    @staticmethod
    def _get_provider(provider_name, provider_list):
        provider_new = None
        for provider_info in provider_list:
            if provider_info['name'] == provider_name:
                provider_new = provider_info

                break

        if not provider_new:
            provider_new = {
                'name': provider_name,
            }
            provider_list.append(provider_new)

        return provider_new

    def add_version(self, version, provider, url, checksum = None, checksum_type = None):
        version_val = parse_version(version)

        version_list = [val['version'] for val in self.versions]
        insert_at, match_at = get_version_index(version_val, version_list)

        time_now = datetime.utcnow()
        time_str = time_now.strftime('%Y-%m-%dT%H:%M:%S.000Z')

        if match_at is None:
            version_new = {
                'version': str(version_val),
                'created_at': time_str,
                'updated_at': time_str,
                'status': 'active',
                'providers': [],
            }
            if insert_at is not None:
                self._metadata['versions'].insert(insert_at, version_new)

            else:
                self._metadata['versions'].append(version_new)

        else:
            version_new = self._metadata['versions'][match_at]
            version_new['updated_at'] = time_str

        provider_new = self._get_provider(provider, version_new['providers'])

        provider_new['url'] = url
        if checksum and checksum_type:
            provider_new['checksum'] = checksum
            provider_new['checksum_type'] = checksum_type

    def write(self, file_name):
        try:
            write_json_file(self._metadata, file_name)

        except IOError as e:
            raise BoxMetadataException("Failed to write metadata: file='{}' error='{}'".format(file_name, e))


class BoxInventoryException(PackermateException):
    pass


class BoxInventory(object):

    def __init__(self, vagrant_command = 'vagrant'):
        self._box_lookup = None
        self._vagrant_command = vagrant_command

    @property
    def list(self):
        self._refresh()

        return self._box_lookup or {}

    def _refresh(self):
        if self._box_lookup is None:
            try:
                box_lines = run_command('{} box list'.format(self._vagrant_command), quiet = True)

            except ProcessException as e:
                raise BoxInventoryException("Failed to query installed Vagrant boxes: error='{}'".format(e))

            self._box_lookup = {}
            for box_line in box_lines:
                match = re.search('^([^\s]+)\s+\(([^,]+),\s+([^\)]+)\)', box_line)
                if match:
                    installed_name, installed_provider, installed_version_str = match.groups()

                    try:
                        installed_version = parse_version(installed_version_str)

                    except BoxVersionException:
                        pass

                    else:
                        provider_lookup = self._box_lookup.setdefault(installed_name, {})
                        version_list = provider_lookup.setdefault(installed_provider, [])
                        insert_at, match_at = get_version_index(installed_version, version_list)
                        if not match_at:
                            if insert_at is not None:
                                version_list.insert(insert_at, installed_version)

                            else:
                                version_list.append(installed_version)

    def _reset(self):
        self._box_lookup = None

    def installed(self, name, provider, version = None):
        self._refresh()

        provider_lookup = self._box_lookup.get(name, {})
        version_list = provider_lookup.get(provider, [])

        if version is None:
            return version_list[0] if version_list else None

        version_val = parse_version(version)
        return version_val if version_val in version_list else None

    def install(self, name, provider, version = None):
        if self.installed(name, provider, version) is None:
            command = '{} box add --provider {} {}'.format(self._vagrant_command, provider, name)
            if version:
                command += ' --box-version {}'.format(version)

            try:
                run_command(command)

            except ProcessException as e:
                raise BoxInventoryException("Failed to install Vagrant box: name={} provider={} error='{}'".format(
                    name,
                    provider,
                    e
                ))

            finally:
                self._reset()

    def uninstall(self, name, provider, version = None):
        if self.installed(name, provider, version):
            command = '{} box remove --force --provider {} {}'.format(self._vagrant_command, provider, name)
            if version:
                command += ' --box-version {}'.format(version)

            try:
                run_command(command)

            except ProcessException as e:
                raise BoxInventoryException("Failed to remove Vagrant box: name={} provider={} error='{}'".format(
                    name,
                    provider,
                    e
                ))

            finally:
                self._reset()

    def install_from_config(self, config, provider):
        if 'vagrant_box_name' not in config:
            return

        box_url = config.vagrant_box_url or config.vagrant_box_name
        box_version = config.vagrant_box_version

        log.info('Checking for local Vagrant box: {} {}'.format(config.vagrant_box_name, box_version or ''))
        if not self.installed(config.vagrant_box_name, provider, box_version):
            log.info('Installing Vagrant box: {} {}'.format(box_url, box_version or ''))
            self.install(box_url, provider, box_version)

    def export(self, temp_dir, name, provider, version = None):
        if self.installed(name, provider, version):
            command = "{} box repackage {} {} {}".format(self._vagrant_command, name, provider, version)

            try:
                run_command(command, working_dir = temp_dir)

            except ProcessException as e:
                raise BoxInventoryException("Failed to export Vagrant box: name={} provider={} error='{}'".format(
                    name,
                    provider,
                    e
                ))

            return os.path.join(temp_dir, REPACKAGED_VAGRANT_BOX_FILE_NAME)

        else:
            raise BoxInventoryException("Vagrant box is not installed: name={} provider={}".format(name, provider))

    def export_from_config(self, config, provider, temp_dir):
        if 'vagrant_box_name' not in config:
            return

        box_version = config.vagrant_box_version
        if not box_version:
            box_version = self.installed(config.vagrant_box_name, provider)

        log.info('Exporting installed Vagrant box: {} {}'.format(config.vagrant_box_name, box_version or ''))

        return self.export(
            temp_dir,
            config.vagrant_box_name,
            provider,
            box_version
        )


def parse_vagrant_export(config, packer_config):
    if config.vagrant:
        vagrant_config = {
            'type': 'vagrant'
        }

        if config.vagrant_output:
            vagrant_config['output'] = config.vagrant_output

        if config.vagrant_keep_inputs:
            vagrant_config['keep_input_artifact'] = True

        packer_config.add_post_processor(vagrant_config)


class PublishException(PackermateException):
    pass


def publish_vagrant_box(config, target_list, box_inventory):
    if not config.vagrant_output:
        return

    if config.vm_version is None:
        log.info('Unable to publish Vagrant version file as vm_version parameter not set.')
        return

    box_metadata_file_name, target_file_lookup = get_vagrant_output_file_names(config, target_list)

    box_metadata = get_or_create_vagrant_box_metadata(config, box_metadata_file_name)

    add_vagrant_files_to_box_metadata(config, box_metadata, target_file_lookup, box_inventory)

    log.info('Writing updated Vagrant box metadata: {}'.format(box_metadata_file_name))
    box_metadata.write(box_metadata_file_name)

    if 'vagrant_publish_copy_command' in config:
        copy_published_file(config, box_metadata_file_name)

    log.info('Publish complete')


def get_vagrant_output_file_names(config, target_list, check_file = True):
    target_file_lookup = {}
    box_metadata_file_name = None

    if config.vagrant_output is not None:
        match = re.search('^(.+)\{\{\s*\.Provider\s*\}\}(.+)$', config.vagrant_output)
        if match:
            file_format_name = match.group(1) + '{}' + match.group(2)

            vagrant_output_path = os.path.dirname(file_format_name)
            box_metadata_file_name = os.path.join(vagrant_output_path, '{}.json'.format(config.vm_name))

            for target_name in target_list:
                provider_file_name = file_format_name.format(target_name)

                if check_file and not os.path.exists(provider_file_name):
                    raise PublishException('Unable to find Vagrant box file: {}'.format(provider_file_name))

                target_file_lookup[target_name] = provider_file_name

    if not box_metadata_file_name:
        raise PublishException('Unable to determine Vagrant box metadata output file name')

    if not target_file_lookup:
        raise PublishException('No Vagrant box files found')

    return box_metadata_file_name, target_file_lookup


def get_vagrant_box_metadata(config, box_metadata_file_name):
    box_metadata = None
    if box_metadata is None and config.vagrant_publish_url_prefix:
        box_url = '{}{}.json'.format(config.vagrant_publish_url_prefix, config.vm_name)

        try:
            log.info('Attemping to retrieve Vagrant box metadata: {}'.format(box_url))
            box_metadata = BoxMetadata(url = box_url)

        except BoxMetadataException:
            log.warning('Failed to download Vagrant box metadata: {}'.format(box_url))

    if box_metadata is None and os.path.exists(box_metadata_file_name):
        box_url = 'file://{}'.format(os.path.abspath(box_metadata_file_name))
        log.info('Loading Vagrant box metadata: {}'.format(box_url))

        box_metadata = BoxMetadata(url = box_url)

    return box_metadata


def get_or_create_vagrant_box_metadata(config, box_metadata_file_name):
    box_metadata = get_vagrant_box_metadata(config, box_metadata_file_name)

    if box_metadata is None:
        log.info('Creating new Vagrant box metadata: {}'.format(box_metadata_file_name))
        box_metadata = BoxMetadata(name = config.vm_name)

    return box_metadata


def add_vagrant_files_to_box_metadata(config, box_metadata, target_file_lookup, box_inventory):
    for provider_name, provider_file_name in target_file_lookup.iteritems():
        if 'vagrant_publish_copy_command' in config:
            copy_published_file(config, provider_file_name, provider_name)

        if config.vagrant_publish_url_prefix:
            box_url = '{}{}'.format(
                config.vagrant_publish_url_prefix,
                os.path.basename(provider_file_name),
            )

        else:
            box_url = 'file://{}'.format(os.path.abspath(provider_file_name))

        box_checksum = get_md5_sum(provider_file_name)
        box_checksum_type = 'md5'

        box_metadata.add_version(config.vm_version, provider_name, box_url, box_checksum, box_checksum_type)

        if 'vagrant_uninstall_outdated_box' in config and config.vagrant_uninstall_outdated_box:
            log.info('Uninstalling outdated Vagrant box: name={} provider={} version={}'.format(config.vm_name, provider_name, config.vm_version))
            box_inventory.uninstall(config.vm_name, provider_name, config.vm_version)


def copy_published_file(config, file_name, provider_name = None):
    tmp_path = config.FILE_PATH
    tmp_name = config.FILE_NAME
    tmp_provider = config.FILE_PROVIDER

    config.FILE_PATH = file_name
    config.FILE_NAME = os.path.basename(file_name)
    config.FILE_PROVIDER = provider_name

    copy_cmd = config.vagrant_publish_copy_command

    log.info('Executing Vagrant publish copy command: {}'.format(copy_cmd))
    run_command(copy_cmd)

    config.FILE_PATH = tmp_path
    config.FILE_NAME = tmp_name
    config.FILE_PROVIDER = tmp_provider
