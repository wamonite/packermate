#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import pytest
from wamopacker.target import parse_parameters, TargetParameter, TargetParameterException
from wamopacker.config import Config


@pytest.mark.parametrize(
    'param_list, expected',
    (
        ([TargetParameter('key1', 'out1')], {'out1': 'val1'}),
        ([TargetParameter('key2', 'out2')], None),
        ([TargetParameter('key2', 'out2', required = False)], {}),
        ([TargetParameter('key2', 'out2', default = 'val2')], {'out2': 'val2'}),
        ([TargetParameter('key2', 'out2', required = False, default = 'val2')], {'out2': 'val2'}),
        ([TargetParameter('key1', 'out1', value_type = list)], None),
        ([TargetParameter('list1', 'out3', value_type = list)], {'out3': ['val3', 'val4']}),
        ([TargetParameter('list2', 'out4', default = [], value_type = list)], {'out4': []}),
    )
)
def test_target_parameters(param_list, expected):
    config_str = """---
key1: val1
list1:
- val3
- val4
"""
    config = Config(config_string = config_str)
    output = {}
    if expected is not None:
        parse_parameters(param_list, config, output)

        assert output == expected

    else:
        with pytest.raises(TargetParameterException):
            parse_parameters(param_list, config, output)
