#!/bin/bash

echo "🔥 Instalando ODOCO v0.1..."

set -e

WAN_IF="wlan0"
AP_IF="wlan1"
LAN_IP="192.168.50.1"
LAN_NET="192.168.50.0/24"
DHCP_START="192.168.50.100"
DHCP_END="192.168.50.200"
SSID="ODOCO_SETUP"
PASSPHRASE="12345678"

echo "📦 Instalando paquetes..."
apt-get update -y
apt-get install -y hostapd dnsmasq nftables

systemctl stop hostapd || true
systemctl stop dnsmasq || true

echo "🌐 Configurando IP estática para AP..."

sed -i '/# ODOCO-BEGIN/,/# ODOCO-END/d' /etc/dhcpcd.conf

cat <<EOF >> /etc/dhcpcd.conf

# ODOCO-BEGIN
interface $AP_IF
static ip_address=$LAN_IP/24
nohook wpa_supplicant
# ODOCO-END
EOF

systemctl restart dhcpcd

echo "📡 Configurando hostapd..."

mkdir -p /etc/hostapd

cat <<EOF > /etc/hostapd/hostapd.conf
interface=$AP_IF
driver=nl80211
ssid=$SSID
hw_mode=g
channel=6
wmm_enabled=1
ieee80211n=1
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$PASSPHRASE
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF

sed -i 's|^#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

echo "📡 Configurando dnsmasq..."

rm -f /etc/dnsmasq.d/odoco.conf

cat <<EOF > /etc/dnsmasq.d/odoco.conf
interface=$AP_IF
bind-interfaces
dhcp-range=$DHCP_START,$DHCP_END,255.255.255.0,12h
dhcp-option=option:router,$LAN_IP
dhcp-option=option:dns-server,$LAN_IP
EOF

echo "🔥 Configurando NAT..."

cat <<EOF > /etc/nftables.conf
flush ruleset

table ip odoco_nat {
  chain postrouting {
    type nat hook postrouting priority 100;
    policy accept;
    oifname "$WAN_IF" ip saddr $LAN_NET masquerade
  }
}
EOF

systemctl enable nftables
systemctl restart nftables

echo "🔁 Activando IP forwarding..."
echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-odoco.conf
sysctl --system > /dev/null

echo "🚀 Activando servicios al boot..."
systemctl unmask hostapd || true
systemctl enable hostapd
systemctl enable dnsmasq

systemctl restart hostapd
systemctl restart dnsmasq

echo ""
echo "✅ ODOCO instalado correctamente"
echo "📡 Conectate a WiFi: $SSID"
echo "🔐 Password: $PASSPHRASE"
echo "🌐 Acceso: http://$LAN_IP"
echo ""
