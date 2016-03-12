#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import pytest
from packermate.provisioner import parse_provisioners, ProvisionerException
from packermate.target import TargetParameterException
from packermate.command import PackerConfig


@pytest.mark.parametrize(
    'provisioner_list, expected',
    (
        (None, None),
        ([], False),
        (
            [{
                'type': 'unknown',
            }],
            None
        ),
        (
            [{
                'type': 'file',
            }],
            None
        ),
        (
            [{
                'type': 'file',
                'source': 'abc',
                'destination': 'def',
            }],
            {
                'type': 'file',
                'source': 'abc',
                'destination': 'def',
            },
        ),
        (
            [{
                'type': 'ansible-local',
                'playbook_file': 'install.yml',
                'extra_arguments': ['-abc'],
                'extra_vars': {'key1': 'val1'},
            }],
            {
                'type': 'ansible-local',
                'playbook_file': 'install.yml',
                'extra_arguments': ['-abc', '-e \'{"key1": "val1"}\''],
            },
        ),
    )
)
def test_parse_provisioner(config_simple, provisioner_list, expected):
    packer_config = PackerConfig()
    if expected:
        parse_provisioners(provisioner_list, config_simple, packer_config)
        packer_config_expected = PackerConfig()
        packer_config_expected.add_provisioner(expected)
        assert packer_config == packer_config_expected

    elif expected is not None:
        parse_provisioners(provisioner_list, config_simple, packer_config)
        packer_config_expected = PackerConfig()
        assert packer_config == packer_config_expected

    else:
        with pytest.raises((ProvisionerException, TargetParameterException)):
            parse_provisioners(provisioner_list, config_simple, packer_config)
