#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import os
from .process import run_command, ProcessException
from .file_utils import TempDir, DataDir, write_json_file
from .vagrant import BoxMetadata, BoxInventory, parse_vagrant_export, publish_vagrant_box
from .virtualbox import TargetVirtualBox
from .aws import TargetAWS
from .provisioner import parse_provisioners
from .exception import PackermateException
import logging


log = logging.getLogger('packermate.command')


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

    def __eq__(self, other):
        return isinstance(other, PackerConfig) and self._config == other._config


class BuilderException(PackermateException):
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

            box_inventory = BoxInventory(vagrant_command = self._config.vagrant_command)
            for target_name in self._target_list:
                target_class = self.TARGET_LOOKUP.get(target_name)
                if not target_class:
                    raise BuilderException('Unknown target: {}'.format(target_name))

                target = target_class(self._config, self._data_dir, packer_config, temp_dir, box_inventory)
                target.build()

            if self._config.provisioners:
                parse_provisioners(self._config.provisioners, self._config, packer_config)

            parse_vagrant_export(self._config, packer_config)

            if self._dump_packer:
                self._dump_packer_config(packer_config)

            packer_config_file_name = self._validate_packer(packer_config, temp_dir)

            if not self._dry_run:
                self._run_packer(packer_config_file_name)

                log.info('Build complete')

                publish_vagrant_box(
                    self._config,
                    self._target_list,
                    box_inventory,
                )

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
