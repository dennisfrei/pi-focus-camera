#!/usr/bin/env bash
#
# Install avahi so the Pi is reachable at http://astrocam.local — users never type an IP. Sets the
# hostname to "astrocam" and enables the daemon.
set -euo pipefail

echo "Installing avahi-daemon…"
sudo apt-get update -y
sudo apt-get install -y avahi-daemon

echo "Setting hostname to 'astrocam'…"
sudo hostnamectl set-hostname astrocam || true

sudo systemctl enable --now avahi-daemon

echo
echo "mDNS ready: http://astrocam.local:8080"
