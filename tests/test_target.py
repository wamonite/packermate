#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import pytest
from packermate.target import parse_parameters, TargetParameter, TargetParameterException
from packermate.config import Config


@pytest.mark.parametrize(
    'param_list, config_lookup, expected',
    (
        (
            [TargetParameter('key2')],
            None,
            None
        ),
        (
            [TargetParameter('key2', 'out2')],
            None,
            None
        ),
        (
            [TargetParameter('key1')],
            None,
            {'key1': 'val1'}
        ),
        (
            [TargetParameter('key1', 'out1')],
            None,
            {'out1': 'val1'}
        ),
        (
            [TargetParameter('key2', 'out2', required = False)],
            None,
            {}
        ),
        (
            [TargetParameter('key2', 'out2', default = 'val4')],
            None,
            {'out2': 'val4'}
        ),
        (
            [TargetParameter('key2', 'out2', default = '(( key1 ))')],
            None,
            {'out2': 'val1'}
        ),
        (
            [TargetParameter('key2', 'out2', required = False, default = 'val4')],
            None,
            {'out2': 'val4'}
        ),
        (
            [TargetParameter('key1', 'out1', value_type = list)],
            None,
            None
        ),
        (
            [TargetParameter('list1', 'out3', value_type = list)],
            None,
            {'out3': ['val2', 'val3']}
        ),
        (
            [TargetParameter('list2', 'out4', default = [], value_type = list)],
            None,
            {'out4': []}
        ),
        (
            [
                TargetParameter('key1', 'out1', only_if = 'out2'),
                TargetParameter('key2', 'out2', required = False),
            ],
            None,
            {}
        ),
        (
            [
                TargetParameter('key1', 'out1', only_if = 'out2'),
                TargetParameter('key2', 'out2', default = 'val4'),
            ],
            None,
            {'out1': 'val1', 'out2': 'val4'}
        ),
        (
            [
                TargetParameter('key1', 'out1', only_if = 'out2'),
                TargetParameter('key2', 'out2'),
            ],
            {'key2': 'val4'},
            {'out1': 'val1', 'out2': 'val4'}
        ),
        (
            [TargetParameter('key2', 'out2', default = 'val4')],
            {'key2': 'val4'},
            {'out2': 'val4'}
        ),
        (
            [TargetParameter('key1', 'out1', func = lambda x: 'val4')],
            None,
            {'out1': 'val4'}
        ),
        (
            [TargetParameter('key2', 'out2', func = lambda x: 'val4')],
            None,
            None
        ),
        (
            [TargetParameter('key2', 'out2', default = 'val4', func = lambda x: '(( key1 ))')],
            None,
            {'out2': 'val1'}
        ),
    )
)
def test_target_parameters(config_simple, param_list, config_lookup, expected):
    output = {}
    if expected is not None:
        parse_parameters(param_list, config_simple, output, config_lookup = config_lookup)

        assert output == expected

    else:
        with pytest.raises(TargetParameterException):
            parse_parameters(param_list, config_simple, output)
