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
    ('vagrantfile', ('export', 'vagrantfile'))
])


def parse_arguments():
    parser = argparse.ArgumentParser(
        description = 'packer tool',
        formatter_class = argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-c', '--config', default = DEFAULT_CONFIG_FILE_NAME, help = 'config file')
    parser.add_argument('-p', '--param', action = 'append', help = 'additional parameters e.g. -p foo=bar -p answer=42')
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

        command_list = COMMAND_LOOKUP.get(args.command)
        if command_list:
            command_name = command_list[0]
            target_list = command_list[1:]
            builder = Builder(config, target_list)
            command_func = getattr(builder, command_name)
            if callable(command_func):
                command_func()

    except (ConfigException, BuilderException, ProcessException, NotImplementedError) as e:
        print('ERROR:%s: %s' % (e.__class__.__name__, e), file = sys.stderr)
        sys.exit(1)

    except KeyboardInterrupt:
        sys.exit(1)

if __name__ == "__main__":
    run()
