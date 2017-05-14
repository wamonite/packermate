#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from .target import TargetBase, TargetException, TargetParameter, parse_parameters
from .file_utils import unarchive_file
import os
import logging


log = logging.getLogger('packermate.virtualbox')


__all__ = ['TargetVirtualBox', 'TargetVirtualBoxException']


class TargetVirtualBoxException(TargetException):
    pass


class TargetVirtualBox(TargetBase):

    PRESEED_FILE_NAME = 'preseed.cfg'

    def __init__(self, *args, **kwargs):
        super(TargetVirtualBox, self).__init__(*args, **kwargs)

        self._config = self._config.provider('virtualbox')

    def build(self):
        if self._config.virtualbox_iso_url:
            log.info('Configuring ISO build')

            self._build_iso()

        else:
            log.info('Configuring OVF/OVA build')

            self._box_inventory.install_from_config(self._config, 'virtualbox')

            self._build_from_vagrant_box()

            self._build_from_vagrant_box_file()

            self._build_from_input_file()

    def _build_iso(self):
        iso_build_config = self._data_dir.read_json('packer_virtualbox_iso')

        param_list = (
            TargetParameter('virtualbox_output_name', 'vm_name', func = to_machine_name),
            TargetParameter('virtualbox_iso_url', 'iso_url'),
            TargetParameter('virtualbox_iso_checksum', 'iso_checksum'),
            TargetParameter('virtualbox_iso_checksum_type', 'iso_checksum_type', default = 'md5'),
            TargetParameter('virtualbox_guest_os_type', 'guest_os_type', default = 'Ubuntu_64'),
            TargetParameter('virtualbox_disk_mb', 'disk_size', required = False),
            TargetParameter('ssh_user', 'ssh_username'),
            TargetParameter('ssh_password', 'ssh_password'),
            TargetParameter('virtualbox_shutdown_command', 'shutdown_command', default = "echo '(( ssh_password ))' | sudo -S shutdown -P now"),
            TargetParameter('virtualbox_output_directory', 'output_directory'),
            TargetParameter('virtualbox_output_format', 'format', required = False),
            TargetParameter('virtualbox_packer_http_dir', 'http_directory', default = 'packer_http'),
            TargetParameter('virtualbox_headless', 'headless', value_type = bool, default = True),
            TargetParameter('virtualbox_boot_command', 'boot_command', value_type = list, default = [
                "<esc><esc><enter><wait>",
                "/install/vmlinuz noapic preseed/url=http://{{ .HTTPIP }}:{{ .HTTPPort }}/preseed.cfg <wait>",
                "debian-installer=en_GB auto locale=en_GB kbd-chooser/method=gb <wait>",
                "hostname={{ .Name }} <wait>",
                "fb=false debconf/frontend=noninteractive <wait>",
                "keyboard-configuration/modelcode=SKIP keyboard-configuration/layout=GB keyboard-configuration/variant=GB console-setup/ask_detect=false <wait>",
                "initrd=/install/initrd.gz -- <enter><wait>"
            ])
        )
        parse_parameters(param_list, self._config, iso_build_config)

        vboxmanage_list = iso_build_config.setdefault('vboxmanage', [])
        for vboxmanage_attr, vboxmanage_cmd in (
            ('virtualbox_memory_mb', '--memory'),
            ('virtualbox_cpus', '--cpus'),
        ):
            if vboxmanage_attr in self._config:
                vboxmanage_list.append([
                    'modifyvm',
                    '{{ .Name }}',
                    vboxmanage_cmd,
                    getattr(self._config, vboxmanage_attr)
                ])

        self._write_iso_preseed(iso_build_config)

        self._packer_config.add_builder(iso_build_config)

    def _write_iso_preseed(self, output):
        # create the packer_http directory
        packer_http_dir = output['http_directory']
        packer_http_path = os.path.join(self._temp_dir, packer_http_dir)
        output['http_directory'] = packer_http_path
        os.mkdir(packer_http_path)

        # generate the preseed text
        preseed_template = self._data_dir.read_template(self.PRESEED_FILE_NAME)
        preseed_text = preseed_template.substitute(
            user_account = output['ssh_username'],
            user_password = output['ssh_password']
        )

        # write the preseed
        preseed_file_name = os.path.join(packer_http_path, self.PRESEED_FILE_NAME)
        with open(preseed_file_name, 'w') as file_object:
            file_object.write(preseed_text)

    def _build_from_vagrant_box(self):
        self._config.virtualbox_vagrant_box_file = self._box_inventory.export_from_config(self._config, 'virtualbox', self._temp_dir)

    def _build_from_vagrant_box_file(self):
        if 'virtualbox_vagrant_box_file' not in self._config:
            return

        log.info('Extracting VirtualBox OVF/OVA file from Vagrant box')

        file_name_lookup = unarchive_file(
            self._config.virtualbox_vagrant_box_file,
            self._temp_dir,
        )

        self._config.virtualbox_input_file = file_name_lookup.get('box.ovf') or file_name_lookup.get('box.ova')

    def _build_from_input_file(self):
        if 'virtualbox_input_file' not in self._config:
            return

        log.info('Building from VirtualBox OVF/OVA file')

        packer_virtualbox_ovf = self._data_dir.read_json('packer_virtualbox_ovf')

        param_list = (
            TargetParameter('virtualbox_output_name', 'vm_name', func = to_machine_name),
            TargetParameter('ssh_user', 'ssh_username'),
            TargetParameter('ssh_password', 'ssh_password', required = False),
            TargetParameter('ssh_key_file', 'ssh_private_key_file', required = False),  # https://github.com/mitchellh/packer/issues/2428
            TargetParameter('virtualbox_input_file', 'source_path'),
            TargetParameter('virtualbox_output_directory', 'output_directory'),
            TargetParameter('virtualbox_headless', 'headless', value_type = bool, default = True),
        )
        parse_parameters(param_list, self._config, packer_virtualbox_ovf)

        self._packer_config.add_builder(packer_virtualbox_ovf)


def to_machine_name(name):
    return name.replace('_', '-').replace('.', '-')
