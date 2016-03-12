packermate
==========

.. image:: https://travis-ci.org/wamonite/packermate.svg?branch=master
    :target: https://travis-ci.org/wamonite/packermate

.. image:: https://coveralls.io/repos/github/wamonite/packermate/badge.svg?branch=master
    :target: https://coveralls.io/github/wamonite/packermate?branch=master

.. image:: https://codeclimate.com/github/wamonite/packermate/badges/gpa.svg
   :target: https://codeclimate.com/github/wamonite/packermate

Generate and run Packer_ build configurations from a simple YAML definition.

Currently supported features:-

- Ubuntu on VirualBox preseed build from installation ISO image.
- VirtualBox build from existing OVF file.
- VirtualBox build from Vagrant box file.
- VirtualBox build from installed Vagrant box.
- AWS AMI build from existing AMI.
- AWS AMI from Vagrant box file.
- AWS AMI from installed Vagrant box.
- File, shell and Ansible provisioners.
- Export to Vagrant box file.

To Do
-----

- Documentation.
- Tests.

License
-------

Copyright (c) 2015 Warren Moore

This software may be redistributed under the terms of the MIT License.
See the file LICENSE for details.

Contact
-------

::

          @wamonite     - twitter
           \_______.com - web
    warren____________/ - email

.. _packer: https://packer.io/
