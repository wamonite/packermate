#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import os
from .process import run_command, ProcessException
from .file_utils import TempDir, DataDir, write_json_file
from .vagrant import BoxMetadata, parse_vagrant_export
from .virtualbox import TargetVirtualBox
from .aws import TargetAWS
from .provisioner import parse_provisioners
import logging


log = logging.getLogger('wamopacker.command')


__all__ = ['Builder', 'BuilderException']


class PackerConfig(object):

    PACKER_CONFIG_FILE_NAME = 'packer.json'

    def __init__(self):
        self._config = {
            "builders": [],
            "provisioners": [],
            "post-processors": []
        }

    def write(self, file_path = None, file_name = PACKER_CONFIG_FILE_NAME):
        file_name_full = os.path.join(file_path, file_name) if file_path else file_name
        write_json_file(self._config, file_name_full)

        return file_name_full

    def _add_section(self, name, config):
        self._config[name].append(config)

    def add_builder(self, config):
        self._add_section('builders', config)

    def add_provisioner(self, config):
        self._add_section('provisioners', config)

    def add_post_processor(self, config):
        self._add_section('post-processors', config)


class BuilderException(Exception):
    pass


class Builder(object):

    TARGET_LOOKUP = {
        'virtualbox': TargetVirtualBox,
        'aws': TargetAWS,
    }

    def __init__(self, config, target_list, dry_run = False, dump_packer = False):
        self._config = config
        self._target_list = target_list
        self._dry_run = dry_run
        self._dump_packer = dump_packer
        self._vagrant_box_metadata = None
        self._data_dir = DataDir()

    def _load_vagrant_box_url(self):
        if self._config.vagrant_box_url and not self._vagrant_box_metadata:
            self._vagrant_box_metadata = BoxMetadata(url = self._config.vagrant_box_url)

    def get_vagrant_box_url_name(self):
        self._load_vagrant_box_url()

        return self._vagrant_box_metadata.name if self._vagrant_box_metadata else ''

    def get_vagrant_box_url_versions(self):
        self._load_vagrant_box_url()

        return self._vagrant_box_metadata.versions if self._vagrant_box_metadata else {}

    def build(self):
        packer_config = PackerConfig()

        with TempDir(self._config.temp_dir) as temp_dir_object:
            temp_dir = temp_dir_object.path

            for target_name in self._target_list:
                target_class = self.TARGET_LOOKUP.get(target_name)
                if not target_class:
                    raise BuilderException('Unknown target: {}'.format(target_name))

                target = target_class(self._config, self._data_dir, packer_config, temp_dir)
                target.build()

            if self._config.provisioners:
                parse_provisioners(self._config.provisioners, self._config, packer_config)

            parse_vagrant_export(self._config, packer_config)

            # self._update_vagrant_version()

            if self._dump_packer:
                self._dump_packer_config(packer_config)

            packer_config_file_name = self._validate_packer(packer_config, temp_dir)

            if not self._dry_run:
                self._run_packer(packer_config_file_name)

                log.info('Build complete')

    @staticmethod
    def _dump_packer_config(packer_config):
        packer_dump_file_name = packer_config.write()
        log.info("Dumped Packer configuration to '{}'".format(packer_dump_file_name))

    def _validate_packer(self, packer_config, temp_dir_path):
        if not self._config.packer_command:
            raise BuilderException('No Packer command set')

        file_name = packer_config.write(file_path = temp_dir_path)

        try:
            log.info('Validating Packer configuration')
            run_command('{} validate {}'.format(self._config.packer_command, file_name), quiet = True)

        except ProcessException as e:
            raise BuilderException('Failed to validate Packer configuration:-\n{}'.format(e.log_stdout))

        except OSError as e:
            raise BuilderException('Failed to validate Packer configuration: {}'.format(e))

        return file_name

    def _run_packer(self, packer_config_file_name):
        if not self._config.packer_command:
            raise BuilderException('No Packer command set')

        try:
            log.info('Building Packer configuration')
            run_command('{} build {}'.format(self._config.packer_command, packer_config_file_name))

        except (ProcessException, OSError) as e:
            raise BuilderException('Failed to build Packer configuration: {}'.format(e))

    # def _update_vagrant_version(self, validate_only = False):
    #     if self._dry_run:
    #         return
    #
    #     if self._config.vagrant_version_prefix is None:
    #         return
    #
    #     if self._config.vm_version is None:
    #         log.info('Unable to modify Vagrant version file as vm_version parameter not set.')
    #         return
    #
    #     if self._config.vagrant_output is not None:
    #         match = re.search('^(.+)\{\{\s*\.Provider\s*\}\}(.+)$', self._config.vagrant_output)
    #         if match:
    #             file_format_name = match.group(1) + '{}' + match.group(2)
    #
    #             self._update_vagrant_version_file(self._config.vagrant_version_prefix, file_format_name, validate_only)
    #
    # def _update_vagrant_version_file(self, file_prefix, file_format_name, validate_only):
    #     version_file_name = file_prefix + '.json'
    #
    #     log.info('{} Vagrant version file: {}'.format(
    #         'Validating' if validate_only else 'Updating',
    #         version_file_name
    #     ))
    #
    #     # get or create the version file
    #     if os.path.exists(version_file_name):
    #         try:
    #             with open(version_file_name, 'rb') as file_object:
    #                 file_content = json.load(file_object)
    #
    #         except ValueError:
    #             raise BuilderException('Unable to update Vagrant version file: {}'.format(version_file_name))
    #
    #     else:
    #         file_content = {
    #             'name': self._config.vm_name,
    #             'versions': []
    #         }
    #
    #     # get or create the version info
    #     try:
    #         vm_version_val = Version(self._config.vm_version)
    #
    #     except ValueError:
    #         raise BuilderException('Failed to parse semantic version from vm_version: {}'.format(self._config.vm_version))
    #
    #     # build a lookup of active versions
    #     version_info_lookup = {}
    #     for version_info in file_content['versions']:
    #         if version_info['status'] == 'active':
    #             try:
    #                 version_val = Version(version_info['version'])
    #                 version_info_lookup[version_val] = version_info
    #
    #             except ValueError:
    #                 raise BuilderException('Failed to parse semantic version: {}'.format(version_info['version']))
    #
    #     # if current version is a development build, check that a higher non-development version exists
    #     if version_info_lookup and vm_version_val.patch == 0:
    #         version_latest = sorted(version_info_lookup.keys(), reverse = True)[0]
    #         if vm_version_val > version_latest:
    #             raise BuilderException('Cannot build a development image if there is no higher version present. {} > {}'.format(vm_version_val, version_latest))
    #
    #     # stop here when validating
    #     if validate_only:
    #         return
    #
    #     version_info_current = version_info_lookup.setdefault(vm_version_val, {})
    #
    #     # populate the version info
    #     time_now = datetime.utcnow()
    #     time_str = time_now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    #
    #     version_info_current['version'] = self._config.vm_version
    #     version_info_current['status'] = 'active'
    #     version_info_current['updated_at'] = time_str
    #     if 'created_at' not in version_info_current:
    #         version_info_current['created_at'] = time_str
    #     version_info_current['providers'] = []
    #
    #     for target in self._target_list:
    #         box_file_name = file_format_name.format(target)
    #
    #         if self._config.vagrant_copy_url_prefix:
    #             box_file_url = self._config.vagrant_copy_url_prefix + os.path.basename(box_file_name)
    #
    #         else:
    #             box_file_url = 'file://{}'.format(os.path.abspath(box_file_name))
    #
    #         self._copy_vagrant_files(box_file_name)
    #
    #         provider_info = {
    #             'name': target,
    #             'url': box_file_url,
    #             'checksum_type': 'md5',
    #             'checksum': get_md5_sum(box_file_name)
    #         }
    #
    #         version_info_current['providers'].append(provider_info)
    #
    #     file_content['versions'] = []
    #     for version_info_key in sorted(version_info_lookup.keys()):
    #         file_content['versions'].append(version_info_lookup[version_info_key])
    #
    #     write_json_file(file_content, version_file_name)
    #
    #     self._copy_vagrant_files(version_file_name)
    #
    # def _copy_vagrant_files(self, file_name):
    #     if 'vagrant_copy_command' not in self._config:
    #         return
    #
    #     tmp_path = self._config.FILE_PATH
    #     tmp_name = self._config.FILE_NAME
    #
    #     self._config.FILE_PATH = file_name
    #     self._config.FILE_NAME = os.path.basename(file_name)
    #     copy_cmd = self._config.vagrant_copy_command
    #
    #     log.info('Executing copy command: {}'.format(copy_cmd))
    #     run_command(copy_cmd)
    #
    #     self._config.FILE_PATH = tmp_path
    #     self._config.FILE_NAME = tmp_name
