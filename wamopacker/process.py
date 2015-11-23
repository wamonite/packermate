#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import subprocess
import select
import os
import sys
import shlex
from StringIO import StringIO


RUN_COMMAND_POLL_SECONDS = 1
RUN_COMMAND_READ_BYTES = 1024


class ProcessException(Exception):
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
            read_buffer = ''
            # non-blocking read
            for read_data in os.read(read_file.fileno(), RUN_COMMAND_READ_BYTES):
                read_buffer += read_data

            output_file = None
            if read_file == process.stdout:
                file_std.write(read_buffer)
                output_file = None if quiet else sys.stdout

            elif read_file == process.stderr:
                file_err.write(read_buffer)
                output_file = None if quiet else sys.stderr

            if do_print:
                print(read_buffer, end = '', file = output_file)

        if process.poll() is not None:
            break

    output_std = '' if out_to_file else file_std.getvalue()
    output_err = file_err.getvalue()

    file_std.close()
    file_err.close()

    return output_std, output_err, process.returncode


def run_command(command, quiet = False, working_dir = None, out_to_file = None):
    if not quiet:
        print('RUN: %s%s' % (command, ' > %s' % out_to_file if out_to_file else ''))

    command_list = shlex.split(command)
    output_std, output_err, exit_code = stream_subprocess(
        command_list,
        quiet = quiet,
        working_dir = working_dir,
        out_to_file = out_to_file
    )

    if exit_code != 0:
        ex_message = 'Error running command (%s) exit code (%s)' % (command, exit_code)
        ex = ProcessException(ex_message)
        ex.output_std = output_std
        ex.output_err = output_err
        ex.exit_code = exit_code
        raise ex

    return output_std.splitlines()
