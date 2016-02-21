#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from .target import TargetParameter, parse_parameters
import json


class ProvisionerException(Exception):
    pass


def parse_provisioners(provisioner_list, config, packer_config):
    if not isinstance(provisioner_list, list):
        raise ProvisionerException('Provisioners must be a list')

    def to_expanded_json(val):
        val_expanded = config.expand_parameters(val)
        return json.dumps(val_expanded, indent = None)

    value_definition_lookup = {
        'file': (
            TargetParameter('source', 'source'),
            TargetParameter('destination', 'destination'),
            TargetParameter('direction', 'direction', required = False),
        ),
        'shell': (
            TargetParameter('inline', 'inline', value_type = list, required = False),
            TargetParameter('script', 'script', required = False),
            TargetParameter('scripts', 'scripts', value_type = list, required = False),
            TargetParameter('execute_command', 'execute_command', required = False, default = '(( shell_command ))'),
            TargetParameter('environment_vars', 'environment_vars', value_type = list, required = False),
        ),
        'shell-local': (
            TargetParameter('command', 'command'),
            TargetParameter('execute_command', 'execute_command', value_type = list, required = False, default = ["/bin/sh", "-c", "{{.Command}}"]),
        ),
        'ansible-local': (
            TargetParameter('playbook_file', 'playbook_file'),
            TargetParameter('playbook_dir', 'playbook_dir', required = False),
            TargetParameter('command', 'command', value_type = list),
            TargetParameter('extra_arguments', 'extra_arguments', value_type = list, required = False),
            TargetParameter('extra_vars', 'extra_vars', value_type = dict, required = False, func = to_expanded_json),
        ),
    }
    value_parse_lookup = {
        'ansible-local': parse_provisioner_ansible_local,
    }

    for provisioner_lookup in provisioner_list:
        provisioner_type = provisioner_lookup.get('type')
        if provisioner_type in value_definition_lookup:
            provisioner_output = {
                'type': provisioner_type,
            }
            parse_parameters(
                value_definition_lookup[provisioner_type],
                config,
                provisioner_output,
                config_lookup = provisioner_lookup,
            )

            value_parse_func = value_parse_lookup.get(provisioner_type)
            if callable(value_parse_func):
                value_parse_func(provisioner_output)

            packer_config.add_provisioner(provisioner_output)

        else:
            raise ProvisionerException("Unknown provisioner type: {}".format(provisioner_type))


def parse_provisioner_ansible_local(provisioner_values):
    extra_vars = provisioner_values.get('extra_vars')
    if extra_vars:
        extra_arguments_list = provisioner_values.setdefault('extra_arguments', [])
        extra_arguments_list.append("-e '{}'".format(extra_vars))

        del(provisioner_values['extra_vars'])
