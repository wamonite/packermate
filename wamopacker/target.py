#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from .vagrant import BoxInventory
import logging


log = logging.getLogger('wamopacker.target')


__all__ = ['TargetBase', 'TargetException', 'TargetParameter', 'TargetParameterException', 'parse_parameters']


class TargetException(Exception):
    pass


class TargetBase(object):

    def __init__(self, config, data_dir, packer_config, temp_dir):
        self._config = config
        self._data_dir = data_dir
        self._packer_config = packer_config
        self._temp_dir = temp_dir
        self._box_inventory = BoxInventory()

    def build(self):
        raise NotImplementedError()

    def _build_from_vagrant_box_url(self, provider):
        if 'vagrant_box_name' not in self._config:
            return

        box_url = self._config.vagrant_box_url or self._config.vagrant_box_name
        box_version = self._config.vagrant_box_version

        log.info('Checking for local Vagrant box: {} {}'.format(self._config.vagrant_box_name, box_version or ''))
        if not self._box_inventory.installed(self._config.vagrant_box_name, provider, box_version):
            log.info('Installing Vagrant box: {} {}'.format(box_url, box_version or ''))
            self._box_inventory.install(box_url, provider, box_version)

    def _export_vagrant_box(self, provider):
        if 'vagrant_box_name' not in self._config:
            return

        box_version = self._config.vagrant_box_version
        if not box_version:
            box_version = self._box_inventory.installed(self._config.vagrant_box_name, provider)

        log.info('Exporting installed Vagrant box: {} {}'.format(self._config.vagrant_box_name, box_version or ''))

        return self._box_inventory.export(
            self._temp_dir,
            self._config.vagrant_box_name,
            provider,
            box_version
        )


class TargetParameterException(Exception):
    pass


class TargetParameter(object):

    def __init__(
            self,
            config_key,
            output_key,
            required = True,
            value_type = basestring,
            default = None,
            only_if = None,
            func = None,
    ):
        self.config_key = config_key
        self.output_key = output_key
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
                continue

        if not isinstance(val, param.value_type):
            raise TargetParameterException('Parameter type mismatch: name={} expected={} received={}'.format(
                param.config_key,
                param.value_type,
                type(val))
            )

        if param.func and callable(param.func):
            val = param.func(val)

        output[param.output_key] = val

    for param in param_list:
        if param.only_if and param.output_key in output and param.only_if not in output:
            del output[param.output_key]

        elif param.required and param.output_key not in output:
            raise TargetParameterException('Missing required config key: {}'.format(param.config_key))
