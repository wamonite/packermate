#!/bin/bash -eu

# Wait for ec2 startup to update sources list
sleep 10

# Fix hash mismatch on ubuntu ISO
rm -rf /var/lib/apt/lists/*
apt-get clean
apt-get update
apt-get -y upgrade
