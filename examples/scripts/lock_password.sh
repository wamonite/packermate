#!/bin/bash -eu

[ -z "${SETUP_USER_ACCOUNT}" ] && { echo "SETUP_USER_ACCOUNT not set" ; exit 1 ; }

passwd "${SETUP_USER_ACCOUNT}" -l
