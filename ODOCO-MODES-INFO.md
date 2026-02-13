Modos principales de ODOCO
1) Router NAT (Default)

    Objetivo: dar internet a clientes del AP usando WAN (wlan0) y LAN (AP).

    - WAN: cliente Wi-Fi (wlan0)

    - LAN: AP (wlan1) + DHCP

    - Tráfico: NAT (masquerade)

    Sub-opciones (toggles)

    - AP ON/OFF (hostapd)

    - DHCP ON/OFF (dnsmasq leases)

    - DNS Local ON/OFF (dnsmasq como DNS)

    - “Internet Check” ON/OFF (ping/dns checks)

    - Auto-Reconnect WAN ON/OFF (reintentos nmcli)

    - Client List / Leases Viewer ON/OFF (solo UI)

    ✅ Este es tu modo actual.

2) Gateway Inteligente (NAT + Control)

Objetivo: lo mismo que NAT, pero además ODOCO controla/enruta “inteligente”.

Tráfico: NAT + reglas extra (DNS override, redirects, logging)

Sub-opciones (toggles)

DNS Override (por dominio) ON/OFF

DNS por-cliente (solo ciertas MAC/IP) ON/OFF (futuro, pero lo dejamos previsto)

Port Redirect (DNAT) ON/OFF (ej: UDP 19132 → destino)

Proxy HTTP(S) (si algún día) ON/OFF

Captive Portal (si algún día) ON/OFF

Logs avanzados ON/OFF

✅ Aquí vive perfecto lo de Bedrock y “trucos” de red.

3) Bedrock Relay (Preset)

Objetivo: preset listo para “conectar a server externo (Aternos) fácil desde el AP”.
Técnicamente es Gateway Inteligente, pero lo exponemos como modo para UX.

Sub-opciones (toggles)

BedrockConnect local ON/OFF (servicio local)

DNS Override Bedrock ON/OFF (dominios necesarios → IP del router)

UDP Relay 19132 ON/OFF (DNAT/forward hacia Aternos o destino definido)

Lista de “Destinos” (servers): Aternos / otros (desde DB)

“Solo estos clientes” (allowlist) ON/OFF (futuro)

✅ Este modo te resuelve “sin estar cambiando DNS en la consola”.

4) Offline LAN (Local Services)

Objetivo: AP + servicios locales, sin depender de WAN.

WAN: opcional / puede estar desconectado

LAN: AP + DHCP + servicios

Sub-opciones (toggles)

AP ON/OFF

DHCP ON/OFF

DNS local ON/OFF

“Servidor activo” local (tu Server.is_active) ON/OFF

Portal local / panel ON/OFF

Bloqueo de salida a internet (si WAN se conecta) ON/OFF

✅ Para partidas/servicios locales, laboratorio, etc.

5) Monitor Only (Dashboard)

Objetivo: solo observar/administrar, sin tocar red.

No levanta AP

No toca iptables

Solo UI + lectura de estado

Sub-opciones (toggles)

Mostrar WAN status ON/OFF

Mostrar clients (si existen leases) ON/OFF

Logs ON/OFF

✅ Ideal para “no romper nada” mientras debugueás.

Reglas claras de compatibilidad (para que no haya caos)

BedrockConnect / DNS Override / Port Redirect solo se permiten en:

Gateway Inteligente

Bedrock Relay

NAT es requisito para “compartir internet” del AP hacia WAN (a menos que hagas bridge).

Offline LAN permite BedrockConnect “solo local” si querés, pero sin relay hacia Aternos (porque no hay WAN).

Cómo se vería en UI

Selector: Modo actual

Router NAT

Gateway Inteligente

Bedrock Relay

Offline LAN

Monitor Only

Debajo: “Features” con switches (según modo)

Mi recomendación práctica para empezar

Modo Router NAT (ya)

Agregar Modo Bedrock Relay como preset

Internamente, Bedrock Relay = Gateway Inteligente con 2–3 toggles pre-encendidos

Si te parece bien esta definición, el siguiente paso es aterrizarlo a código:

Un odoco_mode en SQLite (o config file)

Una tabla features (feature_key, enabled, config_json)

Endpoints:

GET /api/mode

POST /api/mode

GET /api/features

POST /api/features/{key}

y en UI un card “Modo” + switches.