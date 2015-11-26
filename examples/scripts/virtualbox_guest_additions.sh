#!/bin/bash -eu

# VirtualBox guest additions
if [ -r /tmp/VBoxGuestAdditions.iso ]
then
    mount -o loop,ro /tmp/VBoxGuestAdditions.iso /mnt
    /mnt/VBoxLinuxAdditions.run
    umount /mnt

    # Set halt
    echo 'INIT_HALT=POWEROFF' >> /etc/default/halt
fi
