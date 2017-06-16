packermate
==========

.. image:: https://img.shields.io/pypi/v/packermate.svg
    :target: https://pypi.python.org/pypi/packermate

.. image:: https://travis-ci.org/wamonite/packermate.svg?branch=master
    :target: https://travis-ci.org/wamonite/packermate

.. image:: https://codecov.io/gh/wamonite/packermate/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/wamonite/packermate

.. image:: https://requires.io/github/wamonite/packermate/requirements.svg?branch=master
    :target: https://requires.io/github/wamonite/packermate/requirements/?branch=master

.. image:: https://codeclimate.com/github/wamonite/packermate/badges/gpa.svg
   :target: https://codeclimate.com/github/wamonite/packermate

Generate and run Packer_ build configurations from a simple YAML definition.

Currently supported features:-

- Ubuntu on VirualBox preseed build from installation ISO image.
- VirtualBox build from existing OVF file.
- VirtualBox build from Vagrant box file.
- VirtualBox build from installed Vagrant box.
- VirtualBox build from Atlas Vagrant box name.
- VirtualBox build from Vagrant box URL.
- AWS AMI build from existing AMI.
- AWS AMI from Vagrant box file.
- AWS AMI from installed Vagrant box.
- AWS AMI build from Atlas Vagrant box name.
- AWS AMI build from Vagrant box URL.
- File, shell and Ansible provisioners.
- Export to Vagrant box file.
- Export Vagrant box version metadata to file.
- Specify command to run after Vagrant export.

To Do
-----

- Documentation.
- Tests.

License
-------

Copyright (c) 2016 Warren Moore

This software may be redistributed under the terms of the MIT License.
See the file LICENSE for details.

Contact
-------

::

          @wamonite     - twitter
           \_______.com - web
    warren____________/ - email

.. _packer: https://packer.io/
