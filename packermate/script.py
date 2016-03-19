#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import sys
import argparse
from .config import Config
from .command import Builder
from collections import OrderedDict
from .exception import PackermateException
import logging


DEFAULT_CONFIG_FILE_NAME = 'packermate.yml'
COMMAND_LOOKUP = OrderedDict([
    ('virtualbox', ('build', 'virtualbox')),
    ('aws', ('build', 'aws')),
    ('all', ('build', 'virtualbox', 'aws')),
])
LOG_FORMAT = '%(name)s %(levelname)s: %(message)s'
LOG_FORMAT_DATE = '%Y-%m-%d %H:%M:%S'
LOG_LEVEL = logging.INFO


def configure_logging(level = LOG_LEVEL, format_message = LOG_FORMAT, format_date = LOG_FORMAT_DATE):
    logger = logging.getLogger()
    logger.setLevel(level)

    log_handler = logging.StreamHandler()
    log_handler.setLevel(level)
    logger.addHandler(log_handler)

    log_format = logging.Formatter(format_message, datefmt = format_date)
    log_handler.setFormatter(log_format)


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
    configure_logging()
    logger = logging.getLogger('packermate.script')

    try:
        args = parse_arguments()
        config = Config(args.config, args.param)

        if args.show_config:
            print(unicode(config))

            return

        command_list = COMMAND_LOOKUP.get(args.command)
        if command_list:
            command_name = command_list[0]
            target_list = command_list[1:]
            builder = Builder(config, target_list, args.dry_run, args.dump_packer)
            command_func = getattr(builder, command_name)
            if callable(command_func):
                command_func()

    except PackermateException as e:
        logger.error('{}: {}'.format(e.__class__.__name__, e))
        sys.exit(1)


if __name__ == "__main__":
    run()
