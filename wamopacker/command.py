#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import os
from tempfile import mkdtemp
from shutil import rmtree
from jinja2 import Environment, FileSystemLoader
from json import load


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
        packer_config = {
            "builders": [],
            "provisioners": [],
            "post-processors": []
        }

        with TempDir() as temp_dir:
            if 'virtualbox' in self._target_list:
                self._build_virtualbox(packer_config, temp_dir)

            if 'aws' in self._target_list:
                self._build_aws(packer_config, temp_dir)

            # template = self._template_env.get_template('preseed.j2')
            # print(template.render(title = 'hello'))

        from json import dumps
        print(dumps(packer_config, indent = 4))

    def _load_json(self, name):
        file_name = os.path.join(self._data_path, name + '.json')
        with open(file_name, 'r') as file_object:
            return load(file_object)

    def _build_virtualbox(self, packer_config, temp_dir):
        if 'virtualbox_iso_url' in self._config and 'virtualbox_iso_checksum' in self._config:
            packer_virtualbox_iso = self._load_json('packer_virtualbox_iso')

            for config_key, virtualbox_key in (
                    ('vm_name', 'vm_name'),
                    ('virtualbox_iso_url', 'iso_url'),
                    ('virtualbox_iso_checksum', 'iso_checksum'),
                    ('virtualbox_iso_checksum_tyoe', 'iso_checksum_type'),
                    ('virtualbox_guest_os_type', 'guest_os_type'),
                    ('virtualbox_disk_mb', 'disk_size'),
                    ('virtualbox_user', 'ssh_username'),
                    ('virtualbox_password', 'ssh_password'),
                    ('virtualbox_output_directory', 'output_directory'),
            ):
                if config_key in self._config:
                    packer_virtualbox_iso[virtualbox_key] = getattr(self._config, config_key)

            vboxmanage_list = packer_virtualbox_iso.setdefault('vboxmanage', [])
            for vboxmanage_attr, vboxmanage_cmd in (
                    ('virtualbox_memory_mb', '--memory'),
                    ('virtualbox_cpus', '--cpus'),
            ):
                if vboxmanage_attr in self._config:
                    vboxmanage_list.append(['modifyvm', '{{ .Name }}', vboxmanage_cmd, getattr(self._config, vboxmanage_attr)])

            packer_virtualbox_iso['shutdown_command'] = "echo '%s' | sudo -S shutdown -P now" % self._config.virtualbox_password

            packer_config['builders'].append(packer_virtualbox_iso)

    def _build_aws(self, packer_config, temp_dir):
        pass
