#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from urlparse import urlparse
import requests
from requests.exceptions import ConnectionError
import json
import semantic_version
from .file_utils import write_json_file
import logging


log = logging.getLogger('wamopacker.version')


__all__ = ['VagrantBoxMetadata', 'VagrantBoxMetadataException']


class VagrantBoxMetadataException(Exception):
    pass


class VagrantBoxMetadata(object):

    def __init__(self, url = None, name = None):
        if url:
            url_data = self._load_url(url)
            try:
                self._metadata = json.loads(url_data)

            except ValueError:
                raise VagrantBoxMetadataException('Failed to decode JSON form metadata file')

        elif name:
            self._metadata = self._create(name)

        else:
            raise VagrantBoxMetadataException('No URL or name specified')

        self._validate()

    @staticmethod
    def _load_url(url):
        result = urlparse(url)

        if result.scheme == 'file':
            try:
                with open(result.path, 'r') as file_object:
                    url_data = file_object.read()

            except IOError as e:
                raise VagrantBoxMetadataException("Failed to load file: file='{}' error='{}'".format(result.path, e))

        elif result.scheme in ('http', 'https'):
            try:
                response = requests.get(url)

                if response.status_code != 200:
                    raise VagrantBoxMetadataException(
                        "Failed to download URL: url='{}' status_code={}".format(url, response.status_code),
                        response.status_code
                    )

                url_data = response.text

            except ConnectionError:
                raise VagrantBoxMetadataException('Failed to download URL: {}'.format(url))

        else:
            raise VagrantBoxMetadataException('Unsupported URL scheme: {}'.format(result.scheme))

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
            raise VagrantBoxMetadataException("Metadata does not contain a dictionary")

        if not self._metadata.get('name'):
            raise VagrantBoxMetadataException("Metadata does not have a name")

        version_list = self._metadata.get('versions')
        if not isinstance(version_list, list):
            raise VagrantBoxMetadataException("Metadata does not have any versions")

        self._parse_version_list(version_list)

    @staticmethod
    def _parse_version_list(version_list):
        parsed_list = []
        for version_lookup in version_list:
            status_str = version_lookup.get('status', '<not present>')
            if status_str not in ('active', 'revoked'):
                raise VagrantBoxMetadataException("Unknown version status: '{}'".format(status_str))

            if 'version' not in version_lookup:
                raise VagrantBoxMetadataException("Version value missing")

            version_str = version_lookup['version']
            version_val = VagrantBoxMetadata._parse_version(version_str)
            provider_lookup_list = version_lookup.get('providers', [])
            provider_list = [provider['name'] for provider in provider_lookup_list if provider.get('name') and provider.get('url')]

            parsed_version = {
                'version_str': version_str,
                'version': version_val,
                'status': status_str,
                'providers': provider_list,
            }
            parsed_list.append(parsed_version)

        return parsed_list

    @staticmethod
    def _parse_version(version_val):
        if not version_val:
            raise VagrantBoxMetadataException("Invalid version value: '{}'".format(version_val))

        elif isinstance(version_val, basestring):
            version_split = version_val.split('.')
            if len(version_split) > 3:
                raise VagrantBoxMetadataException("Invalid number of version elements: '{}'".format(version_val))

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
                    raise VagrantBoxMetadataException("Pre-release and build versions unsupported: '{}'".format(version_val))

            return semantic_version.Version('.'.join(version_parts))

        elif isinstance(version_val, semantic_version.Version):
            if version_val.partial or version_val.prerelease or version_val.build:
                raise VagrantBoxMetadataException("Partial, pre-release and build versions unsupported: '{}'".format(version_val))

            return version_val

        raise VagrantBoxMetadataException("Unsupport version type: '{}'".format(version_val))

    def write(self, file_name):
        try:
            write_json_file(self._metadata, file_name)

        except IOError as e:
            raise VagrantBoxMetadataException("Failed to write metadata: file='{}' error='{}'".format(file_name, e))
