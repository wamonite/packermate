#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import pytest
from wamopacker.process import run_command, ProcessException
import os
import uuid


def test_run_command():
    cwd = os.getcwd()
    output_cmd = run_command('ls -1A', working_dir = cwd)
    output_py = os.listdir(cwd)
    assert sorted(output_cmd) == sorted(output_py)


def test_run_command_error():
    data = uuid.uuid4().hex
    with pytest.raises(ProcessException) as e:
        run_command('cat {}'.format(data))

    assert e.value.log_stdout == ''
    assert e.value.log_stderr == 'cat: {}: No such file or directory\n'.format(data)
    assert e.value.exit_code != 0
