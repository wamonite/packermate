#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from .exception import PackermateException
import logging


log = logging.getLogger('packermate.target')


__all__ = ['TargetBase', 'TargetException', 'TargetParameter', 'TargetParameterException', 'parse_parameters']


class TargetException(PackermateException):
    pass


class TargetBase(object):

    def __init__(self, config, data_dir, packer_config, temp_dir, box_inventory):
        self._config = config
        self._data_dir = data_dir
        self._packer_config = packer_config
        self._temp_dir = temp_dir
        self._box_inventory = box_inventory

    def build(self):
        raise NotImplementedError()


class TargetParameterException(PackermateException):
    pass


class TargetParameter(object):

    def __init__(
            self,
            config_key,
            output_key = None,
            required = True,
            value_type = basestring,
            default = None,
            only_if = None,
            func = None,
    ):
        self.config_key = config_key
        self.output_key = config_key if output_key is None else output_key
        self.required = required
        self.value_type = value_type
        self.default = default
        self.only_if = only_if
        self.func = func


def parse_parameters(param_list, config, output, config_lookup = None):
    for param in param_list:
        assert isinstance(param, TargetParameter)

        if config_lookup and param.config_key in config_lookup:
            val = config.expand_parameters(config_lookup[param.config_key])

        elif param.config_key in config:
            val = getattr(config, param.config_key)

        else:
            if param.default is not None:
                val = config.expand_parameters(param.default)

            else:
                val = None

        if val is not None:
            if not isinstance(val, param.value_type):
                raise TargetParameterException('Parameter type mismatch: name={} expected={} received={}'.format(
                    param.config_key,
                    param.value_type,
                    type(val))
                )

            if param.func and callable(param.func):
                val = config.expand_parameters(param.func(val))

            output[param.output_key] = val

    for param in param_list:
        if param.only_if and param.output_key in output and param.only_if not in output:
            del output[param.output_key]

        elif param.required and param.output_key not in output:
            raise TargetParameterException('Missing required config key: {}'.format(param.config_key))
