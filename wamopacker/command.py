#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import os
from .process import run_command, ProcessException
import re
import json
import logging
from datetime import datetime
from semantic_version import Version
from .file_utils import TempDir, DataDir, get_md5_sum, write_json_file
from .vagrant import BoxMetadata
from .virtualbox import TargetVirtualBox


PRESEED_FILE_NAME = 'preseed.cfg'
EXTRACTED_OVF_FILE_NAME = 'box.ovf'
REPACKAGED_VAGRANT_BOX_FILE_NAME = 'package.box'


log = logging.getLogger('wamopacker.command')


__all__ = ['Builder', 'BuilderException']


class PackerConfig(object):

    PACKER_CONFIG_FILE_NAME = 'packer.json'

    def __init__(self):
        self._config = {
            "builders": [],
            "provisioners": [],
            "post-processors": []
        }

    def write(self, file_path = None, file_name = PACKER_CONFIG_FILE_NAME):
        file_name_full = os.path.join(file_path, file_name) if file_path else file_name
        write_json_file(self._config, file_name_full)

        return file_name_full


class BuilderException(Exception):
    pass


class Builder(object):

    TARGET_LOOKUP = {
        'virtualbox': TargetVirtualBox
    }

    def __init__(self, config, target_list, dry_run = False, dump_packer = False):
        self._config = config
        self._target_list = target_list
        self._dry_run = dry_run
        self._dump_packer = dump_packer
        self._vagrant_box_metadata = None

        self._data_dir = DataDir()

    def _load_vagrant_box_url(self):
        if self._config.vagrant_box_url and not self._vagrant_box_metadata:
            self._vagrant_box_metadata = BoxMetadata(url = self._config.vagrant_box_url)

    def get_vagrant_box_url_name(self):
        self._load_vagrant_box_url()

        return self._vagrant_box_metadata.name if self._vagrant_box_metadata else ''

    def get_vagrant_box_url_versions(self):
        self._load_vagrant_box_url()

        return self._vagrant_box_metadata.versions if self._vagrant_box_metadata else {}

    def build(self):
        self._load_vagrant_box_url()

        packer_config = PackerConfig()

        with TempDir(self._config.temp_dir) as temp_dir_object:
            temp_dir = temp_dir_object.path

            for target_name in self._target_list:
                target_class = self.TARGET_LOOKUP.get(target_name)
                if not target_class:
                    raise BuilderException('Unknown target: {}'.format(target_name))

                target = target_class(self._config, packer_config, temp_dir)
                target.build()

            # self._add_provisioners(packer_config)
            #
            # self._add_vagrant_export(packer_config)
            #
            # self._run_packer(packer_config, temp_dir)
            #
            # self._update_vagrant_version()

            if self._dump_packer:
                packer_dump_file_name = packer_config.write()
                log.info("Dumped Packer configuration to '{}'".format(packer_dump_file_name))

            self._validate_packer(packer_config, temp_dir)

    def _validate_packer(self, packer_config, temp_dir_path):
        if not self._config.packer_command:
            raise BuilderException('No Packer command set')

        file_name = packer_config.write(file_path = temp_dir_path)

        try:
            log.info('Validating Packer configuration')
            run_command('{} validate {}'.format(self._config.packer_command, file_name), quiet = True)

        except ProcessException as e:
            error_list = [line for line in e.log_stdout.splitlines() if line.startswith('* ')]
            raise BuilderException('Failed to validate Packer configuration:-\n{}'.format('\n'.join(error_list)))

        except OSError as e:
            raise BuilderException('Failed to validate Packer configuration: {}'.format(e))

    # def _parse_parameters(self, config_key_list, output_lookup):
    #     for config_item in config_key_list:
    #         config_key, output_key, output_type = map(
    #             lambda default, val: val if val is not None else default,
    #             (None, None, basestring),
    #             config_item
    #         )
    #         if config_key in self._config:
    #             val = getattr(self._config, config_key)
    #
    #             if not isinstance(val, output_type):
    #                 raise BuilderException('Parameter type mismatch: name={} expected={} received={}'.format(config_key, output_type, type(val)))
    #
    #             output_lookup[output_key] = val
    #
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
    # def _build_virtualbox_iso(self, packer_config, temp_dir):
    #     packer_virtualbox_iso = self._data_dir.read_json('packer_virtualbox_iso')
    #
    #     config_key_list = (
    #         ('virtualbox_ovf_output', 'vm_name'),
    #         ('virtualbox_iso_url', 'iso_url'),
    #         ('virtualbox_iso_checksum', 'iso_checksum'),
    #         ('virtualbox_iso_checksum_type', 'iso_checksum_type'),
    #         ('virtualbox_guest_os_type', 'guest_os_type'),
    #         ('virtualbox_disk_mb', 'disk_size'),
    #         ('virtualbox_user', 'ssh_username'),
    #         ('virtualbox_password', 'ssh_password'),
    #         ('virtualbox_shutdown_command', 'shutdown_command'),
    #         ('virtualbox_output_directory', 'output_directory'),
    #     )
    #     self._parse_parameters(config_key_list, packer_virtualbox_iso)
    #
    #     vboxmanage_list = packer_virtualbox_iso.setdefault('vboxmanage', [])
    #     for vboxmanage_attr, vboxmanage_cmd in (
    #             ('virtualbox_memory_mb', '--memory'),
    #             ('virtualbox_cpus', '--cpus'),
    #     ):
    #         if vboxmanage_attr in self._config:
    #             vboxmanage_list.append(['modifyvm', '{{ .Name }}', vboxmanage_cmd, getattr(self._config, vboxmanage_attr)])
    #
    #     self._write_virtualbox_iso_preseed(packer_virtualbox_iso, temp_dir)
    #
    #     # add to the builder list
    #     packer_config['builders'].append(packer_virtualbox_iso)
    #
    # def _write_virtualbox_iso_preseed(self, virtualbox_config, temp_dir):
    #     # create the packer_http directory
    #     packer_http_dir = self._config.virtualbox_packer_http_dir
    #     packer_http_path = os.path.join(temp_dir.path, packer_http_dir)
    #     virtualbox_config['http_directory'] = packer_http_path
    #     os.mkdir(packer_http_path)
    #
    #     # generate the preseed text
    #     preseed_template = self._data_dir.read_template(PRESEED_FILE_NAME)
    #     preseed_text = preseed_template.substitute(
    #         user_account = virtualbox_config['ssh_username'],
    #         user_password = virtualbox_config['ssh_password']
    #     )
    #
    #     # write the preseed
    #     preseed_file_name = os.path.join(packer_http_path, PRESEED_FILE_NAME)
    #     with open(preseed_file_name, 'w') as file_object:
    #         file_object.write(preseed_text)
    #
    # def _get_installed_vagrant_box_version(self, search_name, search_provider):
    #     if self._box_lookup is None:
    #         box_lines = run_command('vagrant box list')
    #
    #         self._box_lookup = {}
    #         for box_line in box_lines:
    #             match = re.search('^([^\s]+)\s+\(([^,]+),\s+([^\)]+)\)', box_line)
    #             if match:
    #                 installed_name, installed_provider, installed_version_str = match.groups()
    #
    #                 try:
    #                     installed_version = Version(installed_version_str)
    #
    #                 except ValueError:
    #                     installed_version = None
    #
    #                 provider_lookup = self._box_lookup.setdefault(installed_name, {})
    #                 version_current = provider_lookup.get(installed_provider)
    #                 if version_current is None or version_current < installed_version:
    #                     provider_lookup[installed_provider] = installed_version
    #
    #     box_info = self._box_lookup.get(search_name, {})
    #     if search_provider not in box_info:
    #         raise BuilderException('Unable to find installed Vagrant box: {} {}'.format(
    #             search_provider,
    #             self._config.virtualbox_vagrant_box_name
    #         ))
    #
    #     return box_info.get(search_provider) or 0
    #
    # def _build_virtualbox_vagrant_box_url(self):
    #     log.info('Installing VirtualBox Vagrant box')
    #
    #     try:
    #         # throws exception if not installed
    #         self._get_installed_vagrant_box_version(self._config.virtualbox_vagrant_box_name, 'virtualbox')
    #         return
    #
    #     except BuilderException:
    #         pass
    #
    #     box_add_command = 'vagrant box add --provider virtualbox {}'.format(self._config.virtualbox_vagrant_box_url)
    #     run_command(box_add_command)
    #
    #     self._box_lookup = None
    #
    # def _build_virtualbox_ovf_file(self, packer_config, temp_dir):
    #     packer_virtualbox_ovf = self._data_dir.read_json('packer_virtualbox_ovf')
    #
    #     config_key_list = (
    #         ('virtualbox_ovf_output', 'vm_name'),
    #         ('virtualbox_user', 'ssh_username'),
    #         ('virtualbox_password', 'ssh_password'),
    #         ('virtualbox_private_key_file', 'ssh_key_path'),  # https://github.com/mitchellh/packer/issues/2428
    #         ('virtualbox_ovf_input_file', 'source_path'),
    #         ('virtualbox_output_directory', 'output_directory'),
    #     )
    #     self._parse_parameters(config_key_list, packer_virtualbox_ovf)
    #
    #     packer_config['builders'].append(packer_virtualbox_ovf)
    #
    # def _build_virtualbox_vagrant_box_file(self, temp_dir):
    #     log.info('Extracting VirtualBox OVF file from Vagrant box')
    #
    #     extract_command = "tar -xzvf '{}' -C '{}'".format(self._config.virtualbox_vagrant_box_file, temp_dir.path)
    #     run_command(extract_command)
    #
    #     self._config.virtualbox_ovf_input_file = os.path.join(temp_dir.path, EXTRACTED_OVF_FILE_NAME)
    #
    # def _build_virtualbox_vagrant_box(self, temp_dir):
    #     log.info('Extracting installed VirtualBox Vagrant box')
    #
    #     box_version = self._get_installed_vagrant_box_version(self._config.virtualbox_vagrant_box_name, 'virtualbox')
    #
    #     extract_command = "vagrant box repackage '{}' virtualbox '{}'".format(
    #         self._config.virtualbox_vagrant_box_name,
    #         box_version
    #     )
    #     run_command(extract_command, working_dir = temp_dir.path)
    #
    #     self._config.virtualbox_vagrant_box_file = os.path.join(temp_dir.path, REPACKAGED_VAGRANT_BOX_FILE_NAME)
    #
    # def _build_aws(self, packer_config, temp_dir):
    #     log.info('Building AWS configuration')
    #
    #     if self._config.aws_vagrant_box_url and self._config.aws_vagrant_box_name:
    #         self._build_aws_vagrant_box_url()
    #
    #     if self._config.aws_vagrant_box_name:
    #         self._build_aws_vagrant_box(temp_dir)
    #
    #     if self._config.aws_vagrant_box_file:
    #         self._build_aws_vagrant_box_file(packer_config, temp_dir)
    #
    #     if self._config.aws_ami_id:
    #         self._build_aws_ami_id(packer_config)
    #
    # def _build_aws_ami_id(self, packer_config):
    #     packer_amazon_ebs = {
    #         'type': 'amazon-ebs'
    #     }
    #
    #     config_key_list = (
    #         ('aws_access_key', 'access_key'),
    #         ('aws_secret_key', 'secret_key'),
    #         ('aws_ami_id', 'source_ami'),
    #         ('aws_region', 'region'),
    #         ('aws_ami_name', 'ami_name'),
    #         ('aws_ami_force_deregister', 'force_deregister', bool),
    #         ('aws_instance_type', 'instance_type'),
    #         ('aws_user', 'ssh_username'),
    #         ('aws_keypair_name', 'ssh_keypair_name'),
    #         ('aws_private_key_file', 'ssh_private_key_file'),
    #         ('aws_disk_gb', 'volume_size', int),
    #         ('aws_disk_type', 'volume_type'),
    #         ('aws_ami_tags', 'tags', dict),
    #         ('aws_ami_builder_tags', 'run_tags', dict),
    #         ('aws_iam_instance_profile', 'iam_instance_profile'),
    #     )
    #     self._parse_parameters(config_key_list, packer_amazon_ebs)
    #
    #     # add extra root partition options
    #     for key_name in ('volume_size', 'volume_type'):
    #         if key_name in packer_amazon_ebs:
    #             default_block_device_mappings = [
    #                 {
    #                     'device_name': '/dev/sda1',
    #                     'delete_on_termination': True
    #                 }
    #             ]
    #             ami_block_device_mapping = packer_amazon_ebs.setdefault('ami_block_device_mappings', default_block_device_mappings)
    #             launch_block_device_mapping = packer_amazon_ebs.setdefault('launch_block_device_mappings', default_block_device_mappings)
    #
    #             ami_block_device_mapping[0][key_name] = packer_amazon_ebs[key_name]
    #             launch_block_device_mapping[0][key_name] = packer_amazon_ebs[key_name]
    #
    #             del(packer_amazon_ebs[key_name])
    #
    #     packer_config['builders'].append(packer_amazon_ebs)
    #
    # def _build_aws_vagrant_box_url(self):
    #     log.info('Installing AWS Vagrant box')
    #
    #     try:
    #         # throws exception if not installed
    #         self._get_installed_vagrant_box_version(self._config.aws_vagrant_box_name, 'aws')
    #         return
    #
    #     except BuilderException:
    #         pass
    #
    #     box_add_command = 'vagrant box add --provider aws {}'.format(self._config.aws_vagrant_box_url)
    #     run_command(box_add_command)
    #
    #     self._box_lookup = None
    #
    # def _build_aws_vagrant_box_file(self, packer_config, temp_dir):
    #     log.info('Extracting AWS AMI id from Vagrant box')
    #
    #     extract_command = 'tar -xzvf {} -C {} Vagrantfile'.format(self._config.aws_vagrant_box_file, temp_dir.path)
    #     run_command(extract_command)
    #
    #     vagrant_file_name = os.path.join(temp_dir.path, 'Vagrantfile')
    #     found_ami_id = None
    #     with open(vagrant_file_name, 'r') as file_object:
    #         for line in file_object:
    #             match = re.search('ami:\s*\"([^\"]+)\"', line)
    #             if match:
    #                 found_ami_id = match.group(1)
    #
    #                 break
    #
    #     if not found_ami_id:
    #         raise BuilderException('Unable to extract AWS AMI id from Vagrant box file')
    #
    #     self._config.aws_ami_id = found_ami_id
    #
    # def _build_aws_vagrant_box(self, temp_dir):
    #     log.info('Extracting installed AWS Vagrant box')
    #
    #     box_version = self._get_installed_vagrant_box_version(self._config.aws_vagrant_box_name, 'aws')
    #
    #     extract_command = "vagrant box repackage '{}' aws '{}'".format(
    #         self._config.aws_vagrant_box_name,
    #         box_version
    #     )
    #     run_command(extract_command, working_dir = temp_dir.path)
    #
    #     self._config.aws_vagrant_box_file = os.path.join(temp_dir.path, REPACKAGED_VAGRANT_BOX_FILE_NAME)
    #
    # def _add_provisioners(self, packer_config):
    #     if self._config.provisioners:
    #         if not isinstance(self._config.provisioners, list):
    #             raise BuilderException('Provisioners must be a list')
    #
    #         value_definition_lookup = {
    #             'file': (
    #                 {'name': 'source'},
    #                 {'name': 'destination'},
    #                 {'name': 'direction', 'required': False},
    #             ),
    #             'shell': (
    #                 {'name': 'inline', 'type': list, 'required': False},
    #                 {'name': 'script', 'required': False},
    #                 {'name': 'scripts', 'type': list, 'required': False},
    #                 {'name': 'execute_command', 'required': False, 'default': '(( shell_command ))'},
    #                 {'name': 'environment_vars', 'type': list, 'required': False},
    #             ),
    #             'shell-local': (
    #                 {'name': 'command', 'required': True},
    #                 {'name': 'execute_command', 'type': list, 'required': False, 'default': ["/bin/sh", "-c", "{{.Command}}"]},
    #             ),
    #             'ansible-local': (
    #                 {'name': 'playbook_file'},
    #                 {'name': 'playbook_dir', 'required': False},
    #                 {'name': 'command', 'required': False},
    #                 {'name': 'extra_arguments', 'type': list, 'required': False},
    #                 {'name': 'extra_vars', 'type': dict, 'required': False, 'func': self._to_expanded_json},
    #             ),
    #         }
    #         value_parse_lookup = {
    #             'ansible-local': self._parse_provisioner_ansible_local,
    #         }
    #
    #         provisioner_list = self._config.provisioners
    #         for provisioner_lookup in provisioner_list:
    #             provisioner_type = provisioner_lookup.get('type')
    #             if provisioner_type in value_definition_lookup:
    #                 provisioner_values = self._parse_provisioner(
    #                     provisioner_type,
    #                     provisioner_lookup,
    #                     value_definition_lookup[provisioner_type]
    #                 )
    #
    #                 value_parse_func = value_parse_lookup.get(provisioner_type)
    #                 if callable(value_parse_func):
    #                     value_parse_func(provisioner_values)
    #
    #                 packer_config['provisioners'].append(provisioner_values)
    #
    #             else:
    #                 raise BuilderException("Unknown provision type: type='{}'".format(provisioner_type))
    #
    # def _parse_provisioner(self, provisioner_type, provisioner_lookup, value_definition):
    #     provisioner_values = {
    #         'type': provisioner_type
    #     }
    #
    #     provisioner_val_name_set = set(provisioner_lookup.keys())
    #     provisioner_val_name_set.remove('type')
    #     for val_items in value_definition:
    #         val_name = val_items['name']
    #         val_type = val_items.get('type', basestring)
    #         val_required = val_items.get('required', True)
    #         val_default = self._config.expand_parameters(val_items.get('default'))
    #         val_func = val_items.get('func')
    #
    #         val = provisioner_lookup.get(val_name, val_default)
    #         if not isinstance(val, val_type):
    #             if val or val_required:
    #                 raise BuilderException("Invalid provision value: name='{}' type='{}' type_expected='{}'".format(
    #                     val_name,
    #                     '' if val is None else val.__class__.__name__,
    #                     val_type.__name__
    #                 ))
    #
    #         if callable(val_func):
    #             val = val_func(val)
    #
    #         if val:
    #             provisioner_values[val_name] = val
    #             provisioner_val_name_set.discard(val_name)
    #
    #     if provisioner_val_name_set:
    #         raise BuilderException("Invalid provision value: name='{}'".format(','.join(provisioner_val_name_set)))
    #
    #     return provisioner_values
    #
    # def _to_expanded_json(self, val):
    #     val_expanded = self._config.expand_parameters(val)
    #     return json.dumps(val_expanded, indent = None)
    #
    # def _parse_provisioner_ansible_local(self, provisioner_values):
    #     extra_vars = provisioner_values.get('extra_vars')
    #     if extra_vars:
    #         extra_arguments_list = provisioner_values.setdefault('extra_arguments', [])
    #         extra_arguments_list.append("-e '{}'".format(extra_vars))
    #
    #         del(provisioner_values['extra_vars'])
    #
    # def _add_vagrant_export(self, packer_config):
    #     if self._config.vagrant:
    #         vagrant_config = {
    #             'type': 'vagrant'
    #         }
    #
    #         if self._config.vagrant_output:
    #             vagrant_config['output'] = self._config.vagrant_output
    #
    #         if self._config.vagrant_keep_inputs:
    #             vagrant_config['keep_input_artifact'] = True
    #
    #         packer_config['post-processors'].append(vagrant_config)
    #
    # def _run_packer(self, packer_config, temp_dir):
    #     if self._dump_packer:
    #         log.info("Dumping Packer configuration to '{}'".format(self.PACKER_CONFIG_FILE_NAME))
    #         write_json_file(packer_config, self.PACKER_CONFIG_FILE_NAME)
    #
    #     packer_config_file_name = os.path.join(temp_dir.path, self.PACKER_CONFIG_FILE_NAME)
    #     write_json_file(packer_config, packer_config_file_name)
    #
    #     try:
    #         log.info('Validating Packer configuration')
    #         run_command('{} validate {}'.format(self._config.packer_command, packer_config_file_name))
    #
    #     except (ProcessException, OSError) as e:
    #         raise BuilderException('Failed to validate Packer configuration: {}'.format(e))
    #
    #     if not self._dry_run:
    #         try:
    #             log.info('Building Packer configuration')
    #             run_command('{} build {}'.format(self._config.packer_command, packer_config_file_name))
    #
    #         except (ProcessException, OSError) as e:
    #             raise BuilderException('Failed to build Packer configuration: {}'.format(e))
    #
    # def _update_vagrant_version(self, validate_only = False):
    #     if self._dry_run:
    #         return
    #
    #     if self._config.vagrant_version_prefix is None:
    #         return
    #
    #     if self._config.vm_version is None:
    #         log.info('Unable to modify Vagrant version file as vm_version parameter not set.')
    #         return
    #
    #     if self._config.vagrant_output is not None:
    #         match = re.search('^(.+)\{\{\s*\.Provider\s*\}\}(.+)$', self._config.vagrant_output)
    #         if match:
    #             file_format_name = match.group(1) + '{}' + match.group(2)
    #
    #             self._update_vagrant_version_file(self._config.vagrant_version_prefix, file_format_name, validate_only)
    #
    # def _update_vagrant_version_file(self, file_prefix, file_format_name, validate_only):
    #     version_file_name = file_prefix + '.json'
    #
    #     log.info('{} Vagrant version file: {}'.format(
    #         'Validating' if validate_only else 'Updating',
    #         version_file_name
    #     ))
    #
    #     # get or create the version file
    #     if os.path.exists(version_file_name):
    #         try:
    #             with open(version_file_name, 'rb') as file_object:
    #                 file_content = json.load(file_object)
    #
    #         except ValueError:
    #             raise BuilderException('Unable to update Vagrant version file: {}'.format(version_file_name))
    #
    #     else:
    #         file_content = {
    #             'name': self._config.vm_name,
    #             'versions': []
    #         }
    #
    #     # get or create the version info
    #     try:
    #         vm_version_val = Version(self._config.vm_version)
    #
    #     except ValueError:
    #         raise BuilderException('Failed to parse semantic version from vm_version: {}'.format(self._config.vm_version))
    #
    #     # build a lookup of active versions
    #     version_info_lookup = {}
    #     for version_info in file_content['versions']:
    #         if version_info['status'] == 'active':
    #             try:
    #                 version_val = Version(version_info['version'])
    #                 version_info_lookup[version_val] = version_info
    #
    #             except ValueError:
    #                 raise BuilderException('Failed to parse semantic version: {}'.format(version_info['version']))
    #
    #     # if current version is a development build, check that a higher non-development version exists
    #     if version_info_lookup and vm_version_val.patch == 0:
    #         version_latest = sorted(version_info_lookup.keys(), reverse = True)[0]
    #         if vm_version_val > version_latest:
    #             raise BuilderException('Cannot build a development image if there is no higher version present. {} > {}'.format(vm_version_val, version_latest))
    #
    #     # stop here when validating
    #     if validate_only:
    #         return
    #
    #     version_info_current = version_info_lookup.setdefault(vm_version_val, {})
    #
    #     # populate the version info
    #     time_now = datetime.utcnow()
    #     time_str = time_now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    #
    #     version_info_current['version'] = self._config.vm_version
    #     version_info_current['status'] = 'active'
    #     version_info_current['updated_at'] = time_str
    #     if 'created_at' not in version_info_current:
    #         version_info_current['created_at'] = time_str
    #     version_info_current['providers'] = []
    #
    #     for target in self._target_list:
    #         box_file_name = file_format_name.format(target)
    #
    #         if self._config.vagrant_copy_url_prefix:
    #             box_file_url = self._config.vagrant_copy_url_prefix + os.path.basename(box_file_name)
    #
    #         else:
    #             box_file_url = 'file://{}'.format(os.path.abspath(box_file_name))
    #
    #         self._copy_vagrant_files(box_file_name)
    #
    #         provider_info = {
    #             'name': target,
    #             'url': box_file_url,
    #             'checksum_type': 'md5',
    #             'checksum': get_md5_sum(box_file_name)
    #         }
    #
    #         version_info_current['providers'].append(provider_info)
    #
    #     file_content['versions'] = []
    #     for version_info_key in sorted(version_info_lookup.keys()):
    #         file_content['versions'].append(version_info_lookup[version_info_key])
    #
    #     write_json_file(file_content, version_file_name)
    #
    #     self._copy_vagrant_files(version_file_name)
    #
    # def _copy_vagrant_files(self, file_name):
    #     if 'vagrant_copy_command' not in self._config:
    #         return
    #
    #     tmp_path = self._config.FILE_PATH
    #     tmp_name = self._config.FILE_NAME
    #
    #     self._config.FILE_PATH = file_name
    #     self._config.FILE_NAME = os.path.basename(file_name)
    #     copy_cmd = self._config.vagrant_copy_command
    #
    #     log.info('Executing copy command: {}'.format(copy_cmd))
    #     run_command(copy_cmd)
    #
    #     self._config.FILE_PATH = tmp_path
    #     self._config.FILE_NAME = tmp_name
