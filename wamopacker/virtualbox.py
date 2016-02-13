#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from .target import TargetBase
import logging


log = logging.getLogger('wamopacker.virtualbox')


__all__ = ['TargetVirtualBox']


class TargetVirtualBox(TargetBase):

    def build(self):
        if self._config.virtualbox_iso_url:
            log.info('Building ISO configuration')

            self._build_iso()

        else:
            log.info('Building OVF configuration')

    def _build_iso(self):
        pass

    # def _build_virtualbox(self, packer_config, temp_dir):
    #     if self._config.virtualbox_iso_url and self._config.virtualbox_iso_checksum:
    #         log.info('Bulding VirtualBox ISO configuration')
    #
    #         self._build_virtualbox_iso(packer_config, temp_dir)
    #
    #     else:
    #         log.info('Bulding VirtualBox OVF configuration')
    #
    #         if self._config.virtualbox_vagrant_box_url and self._config.virtualbox_vagrant_box_name:
    #             self._build_virtualbox_vagrant_box_url()
    #
    #         if self._config.virtualbox_vagrant_box_name:
    #             self._build_virtualbox_vagrant_box(temp_dir)
    #
    #         if self._config.virtualbox_vagrant_box_file:
    #             self._build_virtualbox_vagrant_box_file(temp_dir)
    #
    #         if self._config.virtualbox_ovf_input_file:
    #             self._build_virtualbox_ovf_file(packer_config, temp_dir)
    #