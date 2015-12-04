#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import sys
import argparse
from .config import Config, ConfigException
from .command import Builder, BuilderException
from .process import ProcessException
from collections import OrderedDict


DEFAULT_CONFIG_FILE_NAME = 'wamopacker.yml'
COMMAND_LOOKUP = OrderedDict([
    ('virtualbox', ('build', 'virtualbox')),
    ('aws', ('build', 'aws')),
    ('all', ('build', 'virtualbox', 'aws')),
])


def parse_arguments():
    parser = argparse.ArgumentParser(
        description = 'packer tool',
        formatter_class = argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-c', '--config', default = DEFAULT_CONFIG_FILE_NAME, help = 'config file')
    parser.add_argument('-p', '--param', action = 'append', help = 'additional parameters e.g. -p foo=bar -p answer=42')
    parser.add_argument('-s', '--show-config', action = 'store_true', help = 'show parameters')
    parser.add_argument('-n', '--dry-run', action = 'store_true', help = 'validate only')
    parser.add_argument('-d', '--dump-packer', action = 'store_true', help = 'dump packer config to working directory')
    parser.add_argument(
        'command',
        nargs = '?',
        choices = COMMAND_LOOKUP.keys(),
        default = COMMAND_LOOKUP.keys()[0],
        help = 'command'
    )
    args = parser.parse_args()

    return args


def run():
    try:
        args = parse_arguments()
        config = Config(args.config, args.param)

        if args.show_config:
            print(unicode(config))

        command_list = COMMAND_LOOKUP.get(args.command)
        if command_list:
            command_name = command_list[0]
            target_list = command_list[1:]
            builder = Builder(config, target_list, args.dry_run, args.dump_packer)
            command_func = getattr(builder, command_name)
            if callable(command_func):
                command_func()

    except (ConfigException, BuilderException, ProcessException, NotImplementedError) as e:
        print('ERROR:{}: {}'.format(e.__class__.__name__, e), file = sys.stderr)
        sys.exit(1)

    except KeyboardInterrupt:
        sys.exit(1)

if __name__ == "__main__":
    run()
