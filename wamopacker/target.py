#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals


class TargetBase(object):

    def __init__(self, config, data_dir, packer_config, temp_dir):
        self._config = config
        self._data_dir = data_dir
        self._packer_config = packer_config
        self._temp_dir = temp_dir

    def build(self):
        raise NotImplementedError()


class TargetParameterException(Exception):
    pass


class TargetParameter(object):

    def __init__(self, config_key, output_key, required = True, value_type = basestring, default = None):
        self.config_key = config_key
        self.output_key = output_key
        self.required = required
        self.value_type = value_type
        self.default = default


def parse_parameters(param_list, config, output):
    for param in param_list:
        assert isinstance(param, TargetParameter)

        if param.config_key not in config:
            if param.default is not None:
                val = param.default

            else:
                if param.required:
                    raise TargetParameterException('Missing required config key: {}'.format(param.config_key))

                else:
                    continue

        else:
            val = getattr(config, param.config_key)

        if not isinstance(val, param.value_type):
            raise TargetParameterException('Parameter type mismatch: name={} expected={} received={}'.format(
                param.config_key,
                param.value_type,
                type(val))
            )

        output[param.output_key] = val
