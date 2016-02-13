#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals


class TargetBase(object):

    def __init__(self, config, packer_config, temp_dir):
        self._config = config
        self._packer_config = packer_config
        self._temp_dir = temp_dir

    def build(self):
        raise NotImplementedError()
