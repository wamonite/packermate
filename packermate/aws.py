#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from .target import TargetBase, TargetException, TargetParameter, parse_parameters
from .file_utils import unarchive_file
import re
import logging


log = logging.getLogger('packermate.aws')


__all__ = ['TargetAWS']


class TargetAWSException(TargetException):
    pass


class TargetAWS(TargetBase):

    def __init__(self, *args, **kwargs):
        super(TargetAWS, self).__init__(*args, **kwargs)

        self._config = self._config.provider('aws')

    def build(self):
        self._box_inventory.install_from_config(self._config, 'aws')

        self._build_from_vagrant_box()

        self._build_from_vagrant_box_file()

        self._build_from_ami_id()

    def _build_from_vagrant_box(self):
        self._config.aws_vagrant_box_file = self._box_inventory.export_from_config(self._config, 'aws', self._temp_dir)

    def _build_from_vagrant_box_file(self):
        if 'aws_vagrant_box_file' not in self._config:
            return

        log.info('Extracting AWS Vagrantfile from Vagrant box')

        file_name_lookup = unarchive_file(
            self._config.aws_vagrant_box_file,
            self._temp_dir,
        )

        vagrantfile_file_name = file_name_lookup['Vagrantfile']
        self._config.aws_ami_id = self._parse_vagrantfile_for_ami_id(vagrantfile_file_name)

    @staticmethod
    def _parse_vagrantfile_for_ami_id(file_name):
        with open(file_name, 'r') as file_object:
            for line in file_object:
                match = re.search('ami:\s*\"([^\"]+)\"', line)
                if match:
                    return match.group(1)

        raise TargetAWSException('Unable to extract AWS AMI id from Vagrant box file')

    def _build_from_ami_id(self):
        if 'aws_ami_id' not in self._config:
            return

        log.info('Configuring AWS AMI build')

        packer_amazon_ebs = {
            'type': 'amazon-ebs'
        }

        config_key_list = (
            TargetParameter('aws_access_key', 'access_key', default = '(( env|AWS_ACCESS_KEY_ID ))'),
            TargetParameter('aws_secret_key', 'secret_key', default = '(( env|AWS_SECRET_ACCESS_KEY ))'),
            TargetParameter('aws_session_token', 'token', default = '(( env|AWS_SESSION_TOKEN ))'),
            TargetParameter('aws_region', 'region', default = '(( env|AWS_DEFAULT_REGION ))'),
            TargetParameter('aws_ami_id', 'source_ami'),
            TargetParameter('aws_ami_name', 'ami_name', default = 'packermate {{ isotime \"2006-01-02 15-04\" }}'),
            TargetParameter('aws_ami_force_deregister', 'force_deregister', value_type = bool, default = False),
            TargetParameter('aws_instance_type', 'instance_type'),
            TargetParameter('ssh_user', 'ssh_username'),
            TargetParameter('ssh_key_file', 'ssh_private_key_file', required = False),
            TargetParameter('aws_keypair_name', 'ssh_keypair_name', required = False),
            TargetParameter('aws_disk_gb', 'volume_size', value_type = int, required = False),
            TargetParameter('aws_disk_type', 'volume_type', required = False),
            TargetParameter('aws_ami_tags', 'tags', value_type = dict, required = False),
            TargetParameter('aws_ami_builder_tags', 'run_tags', value_type = dict, required = False),
            TargetParameter('aws_iam_instance_profile', 'iam_instance_profile', required = False),
        )
        parse_parameters(config_key_list, self._config, packer_amazon_ebs)

        # add extra root partition options
        for key_name in ('volume_size', 'volume_type'):
            if key_name in packer_amazon_ebs:
                default_block_device_mappings = [
                    {
                        'device_name': '/dev/sda1',
                        'delete_on_termination': True
                    }
                ]
                ami_block_device_mapping = packer_amazon_ebs.setdefault('ami_block_device_mappings', default_block_device_mappings)
                launch_block_device_mapping = packer_amazon_ebs.setdefault('launch_block_device_mappings', default_block_device_mappings)

                ami_block_device_mapping[0][key_name] = packer_amazon_ebs[key_name]
                launch_block_device_mapping[0][key_name] = packer_amazon_ebs[key_name]

                del(packer_amazon_ebs[key_name])

        self._packer_config.add_builder(packer_amazon_ebs)
