#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import os
from .process import run_command, ProcessException
from .file_utils import TempDir, DataDir, write_json_file
from .vagrant import BoxMetadata
from .virtualbox import TargetVirtualBox
from .aws import TargetAWS
import logging


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

    def add_builder(self, builder_config):
        self._config['builders'].append(builder_config)


class BuilderException(Exception):
    pass


class Builder(object):

    TARGET_LOOKUP = {
        'virtualbox': TargetVirtualBox,
        'aws': TargetAWS,
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
        packer_config = PackerConfig()

        with TempDir(self._config.temp_dir) as temp_dir_object:
            temp_dir = temp_dir_object.path

            for target_name in self._target_list:
                target_class = self.TARGET_LOOKUP.get(target_name)
                if not target_class:
                    raise BuilderException('Unknown target: {}'.format(target_name))

                target = target_class(self._config, self._data_dir, packer_config, temp_dir)
                target.build()

            # self._add_provisioners(packer_config)
            #
            # self._add_vagrant_export(packer_config)
            #
            # self._run_packer(packer_config, temp_dir)
            #
            # self._update_vagrant_version()

            if self._dump_packer:
                self._dump_packer_config(packer_config)

            packer_config_file_name = self._validate_packer(packer_config, temp_dir)

            if not self._dry_run:
                self._run_packer(packer_config_file_name)

                log.info('Build complete')

    @staticmethod
    def _dump_packer_config(packer_config):
        packer_dump_file_name = packer_config.write()
        log.info("Dumped Packer configuration to '{}'".format(packer_dump_file_name))

    def _validate_packer(self, packer_config, temp_dir_path):
        if not self._config.packer_command:
            raise BuilderException('No Packer command set')

        file_name = packer_config.write(file_path = temp_dir_path)

        try:
            log.info('Validating Packer configuration')
            run_command('{} validate {}'.format(self._config.packer_command, file_name), quiet = True)

        except ProcessException as e:
            raise BuilderException('Failed to validate Packer configuration:-\n{}'.format(e.log_stdout))

        except OSError as e:
            raise BuilderException('Failed to validate Packer configuration: {}'.format(e))

        return file_name

    def _run_packer(self, packer_config_file_name):
        if not self._config.packer_command:
            raise BuilderException('No Packer command set')

        try:
            log.info('Building Packer configuration')
            run_command('{} build {}'.format(self._config.packer_command, packer_config_file_name))

        except (ProcessException, OSError) as e:
            raise BuilderException('Failed to build Packer configuration: {}'.format(e))

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
