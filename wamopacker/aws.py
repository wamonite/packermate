#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from .target import TargetBase, TargetException, TargetParameter, parse_parameters
import os
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
        pass
