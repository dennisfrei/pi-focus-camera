#!/usr/bin/env bash
#
# Turn the Pi into a WiFi access point via NetworkManager. The phone/tablet joins this network and
# opens the GUI — no router, no internet. NM's shared mode hands out DHCP + DNS and puts the Pi at
# 10.42.0.1.
#
# WARNING: this reconfigures wlan0 as an AP and will DISCONNECT the Pi from any WiFi it's currently
# joined to. Run it from a wired/serial/local session, not over the WiFi you're about to replace.
#
# Env overrides: AP_SSID, AP_PASS (8+ chars), AP_IFACE.
set -euo pipefail

SSID="${AP_SSID:-AstroCam}"
PASS="${AP_PASS:-astrocam-focus}"
IFACE="${AP_IFACE:-wlan0}"

if ! command -v nmcli >/dev/null 2>&1; then
  echo "error: nmcli (NetworkManager) not found — this setup assumes Raspberry Pi OS Bookworm/Trixie." >&2
  exit 1
fi

if [ "${#PASS}" -lt 8 ]; then
  echo "error: AP_PASS must be at least 8 characters (WPA2 minimum)." >&2
  exit 1
fi

echo "Creating hotspot '$SSID' on $IFACE (this will drop the current WiFi connection)…"
nmcli device wifi hotspot ifname "$IFACE" ssid "$SSID" password "$PASS"

# Make it come back automatically on boot, ahead of any saved client networks.
nmcli connection modify Hotspot connection.autoconnect yes connection.autoconnect-priority 100

echo
echo "Access point up:"
echo "  SSID:     $SSID"
echo "  Password: $PASS"
echo "  URL:      http://10.42.0.1:8080   (or http://astrocam.local:8080 with mDNS)"
