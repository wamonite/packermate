#!/bin/bash -eu

[ -z "${SETUP_USER_ACCOUNT}" ] && { echo "SETUP_USER_ACCOUNT not set" ; exit 1 ; }

# Setup sudo to allow no-password sudo for "admin"
groupadd -f -r admin
usermod -a -G admin "${SETUP_USER_ACCOUNT}"
