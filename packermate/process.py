#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import subprocess
import select
import os
import sys
import shlex
from StringIO import StringIO
from .exception import PackermateException
import logging


RUN_COMMAND_POLL_SECONDS = 1
RUN_COMMAND_READ_BYTES = 1024


log = logging.getLogger('packermate.process')


__all__ = ['stream_subprocess', 'run_command', 'ProcessException']


class ProcessException(PackermateException):
    pass


def stream_subprocess(command_list, quiet = False, working_dir = None, out_to_file = None):
    process = subprocess.Popen(
        command_list,
        bufsize = 0,
        stdout = subprocess.PIPE,
        stderr = subprocess.PIPE,
        cwd = working_dir
    )

    file_std = open(out_to_file, 'wb') if out_to_file else StringIO()
    file_err = StringIO()

    do_print = not (quiet or out_to_file)
    while True:
        select_list = select.select(
            [process.stdout, process.stderr],
            [],
            [],
            RUN_COMMAND_POLL_SECONDS
        )

        for read_file in select_list[0]:
            read_buffer = None
            # non-blocking read
            for read_data in os.read(read_file.fileno(), RUN_COMMAND_READ_BYTES):
                if read_buffer:
                    read_buffer += read_data
                else:
                    read_buffer = read_data

            output_file = None
            if read_file == process.stdout:
                file_std.write(read_buffer)
                output_file = None if quiet else sys.stdout

            elif read_file == process.stderr:
                file_err.write(read_buffer)
                output_file = None if quiet else sys.stderr

            if do_print and read_buffer:
                print(read_buffer, end = '', file = output_file)

        if process.poll() is not None:
            break

    log_stdout = '' if out_to_file else file_std.getvalue()
    log_stderr = file_err.getvalue()

    file_std.close()
    file_err.close()

    return log_stdout, log_stderr, process.returncode


def run_command(command, quiet = False, working_dir = None, out_to_file = None):
    if not quiet:
        log.debug('{}{}'.format(command, ' > {}'.format(out_to_file) if out_to_file else ''))

    command_list = shlex.split(command)
    log_stdout, log_stderr, exit_code = stream_subprocess(
        command_list,
        quiet = quiet,
        working_dir = working_dir,
        out_to_file = out_to_file
    )

    if exit_code != 0:
        ex_message = 'Error running command ({}) exit code ({})'.format(command, exit_code)
        ex = ProcessException(ex_message)
        ex.log_stdout = log_stdout
        ex.log_stderr = log_stderr
        ex.exit_code = exit_code
        raise ex

    return log_stdout.splitlines()
