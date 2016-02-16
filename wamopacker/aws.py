#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from .target import TargetBase, TargetException, TargetParameter, parse_parameters
import re
import logging


log = logging.getLogger('wamopacker.aws')


__all__ = ['TargetAWS']


class TargetAWSException(TargetException):
    pass


class TargetAWS(TargetBase):

    def __init__(self, *args, **kwargs):
        super(TargetAWS, self).__init__(*args, **kwargs)

        self._config = self._config.provider('aws')

    def build(self):
        self._build_from_vagrant_box_url('aws')

        self._build_from_vagrant_box()

        self._build_from_vagrant_box_file()

    def _build_from_vagrant_box(self):
        self._config.aws_vagrant_box_file = self._export_vagrant_box('aws')

    def _build_from_vagrant_box_file(self):
        if 'aws_vagrant_box_file' not in self._config:
            return

        log.info('Extracting AWS Vagrantfile from Vagrant box')

        file_name_lookup = self._box_inventory.extract(
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
