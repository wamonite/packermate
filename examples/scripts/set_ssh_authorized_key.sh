#!/bin/bash -eu

[ -z "${SSH_PUBLIC_KEY_FILES}" ] && { echo "SSH_PUBLIC_KEY_FILES not set" ; exit 1 ; }

[ ! -d "${HOME}/.ssh" ] && { mkdir -p "${HOME}/.ssh" ; chmod 700 "${HOME}/.ssh" ; }
rm -f "${HOME}/.ssh/authorized_keys"

IFS=':' read -ra file_list <<< "${SSH_PUBLIC_KEY_FILES}"
for file_name in "${file_list[@]}"
do
  cat "${file_name}" >> "${HOME}/.ssh/authorized_keys"
done
