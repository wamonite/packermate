#!/bin/bash -eu

# Wait for ec2 startup to update sources list
sleep 10

# Fix hash mismatch on ubuntu ISO
rm -rf /var/lib/apt/lists/*

export DEBIAN_FRONTEND=noninteractive
export DEBCONF_NONINTERACTIVE_SEEN=true
apt-get clean
apt-get update
apt-get -y upgrade
