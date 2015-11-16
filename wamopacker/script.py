#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import argparse
from .config import Config, ConfigException


def parse_arguments():
    parser = argparse.ArgumentParser(
        description = 'packer tool',
        formatter_class = argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-c', '--config', default = 'packer.yml', help = 'config file')
    args = parser.parse_args()

    return args


def run():
    try:
        args = parse_arguments()
        config = Config(args.config)

    except ConfigException as e:
        print('ERROR:', e, file = sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run()
