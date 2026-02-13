# ODOCO Modes

Documento funcional de modos de operación para ODOCO.

## 1. Router NAT (default)

Objetivo: compartir internet de WAN a clientes del AP.

- WAN: `wlan0` (cliente Wi-Fi)
- LAN: AP en `wlan1` + DHCP
- Tráfico: NAT/masquerade

Toggles esperados:
- AP on/off (`hostapd`)
- DHCP on/off (`dnsmasq`)
- DNS local on/off
- Internet check on/off
- Auto-reconnect WAN on/off
- Client list on/off (solo UI)

## 2. Gateway Inteligente (NAT + control)

Objetivo: NAT + reglas avanzadas de control/enrutado.

Toggles esperados:
- DNS override por dominio
- DNS por cliente (futuro)
- Port redirect (DNAT)
- Proxy HTTP(S) (futuro)
- Captive portal (futuro)
- Logs avanzados

## 3. Bedrock Relay (preset)

Objetivo: preset para conectar clientes del AP a servidor Bedrock externo.

Internamente: variante de Gateway Inteligente con reglas preconfiguradas.

Toggles esperados:
- BedrockConnect local on/off
- DNS override Bedrock on/off
- UDP relay `19132` on/off
- Lista de destinos (`servers` en DB)
- Allowlist de clientes (futuro)

## 4. Offline LAN (servicios locales)

Objetivo: AP + servicios locales sin depender de WAN.

Toggles esperados:
- AP on/off
- DHCP on/off
- DNS local on/off
- Servidor local activo on/off
- Portal/panel local on/off
- Bloqueo de salida a internet

## 5. Monitor Only (dashboard)

Objetivo: observación y administración sin cambios de red.

- No levanta AP
- No aplica reglas NAT
- Solo estado/UI/logs

## Reglas de compatibilidad

- BedrockConnect, DNS override y port redirect solo en:
  - Gateway Inteligente
  - Bedrock Relay
- NAT es requisito para compartir internet AP -> WAN (si no hay bridge).
- Offline LAN puede usar servicios locales sin relay externo.

## Modelo de datos y API objetivo

Diseño recomendado:
- `odoco_mode` en SQLite (o config central)
- tabla `features` (`feature_key`, `enabled`, `config_json`)

Endpoints objetivo:
- `GET /api/mode`
- `POST /api/mode`
- `GET /api/features`
- `POST /api/features/{key}`

## Estado actual

- Existe implementación inicial en `backend/routers/modes.py`.
- Actualmente ese router no está montado en `backend/main.py`.
- Resultado: endpoints de modo todavía no están disponibles en runtime.
