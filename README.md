# ODOCO

Panel de control para un router/AP en Raspberry Pi con backend FastAPI y UI web.

## Estado actual

ODOCO hoy permite:
- Levantar una UI en `/` para ver estado WAN/LAN y clientes DHCP.
- Escanear redes Wi-Fi en `wlan0` y conectar WAN vía `nmcli`.
- Consultar conectividad (gateway, ping internet y DNS).
- Gestionar servidores (`/servers`) y targets de sistema (`/targets/{key}`) en SQLite.

## Requisitos

- Linux (objetivo: Raspberry Pi OS / Debian).
- Python 3.11+.
- Servicios del sistema para modo router/AP:
  - `hostapd`
  - `dnsmasq`
  - `nftables`
  - `NetworkManager` + `nmcli`
- Permisos para ejecutar comandos con `sudo -n` desde la app en endpoints WAN.

## Instalación base del router (opcional)

El script `odoco_install.sh` configura AP + DHCP + NAT con valores por defecto.

```bash
sudo bash odoco_install.sh
```

Valores por defecto del script:
- WAN: `wlan0`
- AP/LAN: `wlan1`
- IP LAN: `192.168.50.1/24`
- SSID: `ODOCO_SETUP`
- Password: `12345678`

## Setup del backend

Crear entorno virtual e instalar dependencias mínimas:

```bash
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn sqlalchemy jinja2
```

Levantar API/UI:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Abrir:
- `http://127.0.0.1:8000` (local)
- `http://192.168.50.1:8000` (desde clientes LAN)

## Endpoints activos

UI:
- `GET /` dashboard
- `GET /ui` redirección a `/`

Resumen y estado:
- `GET /api/summary`
- `GET /clients`
- `GET /wan/status`
- `GET /wan/networks`
- `POST /wan/connect`
- `GET /wan/internet`

CRUD de servidores:
- `GET /servers`
- `POST /servers`
- `PUT /servers/{server_id}`
- `DELETE /servers/{server_id}`
- `POST /servers/{server_id}/activate`

Targets del sistema:
- `GET /targets/{key}`
- `PUT /targets/{key}`

## Estructura

```text
backend/
  core/       config y logging
  db/         modelos, sesión, init
  routers/    endpoints API
  schemas/    validación pydantic
  services/   lógica de negocio
frontend/
  css/
  js/
templates/
  index.html
odoco_install.sh
```

## Base de datos

- La app actual usa `odoco.db` en la raíz del proyecto (`backend/db/session.py`).
- También existe `db/odoco.db` en el repo.
- Recomendación: definir una sola ubicación para evitar confusiones.

## Notas importantes

- Existe `backend/routers/modes.py`, pero hoy no está montado en `backend/main.py`; por eso `/api/modes` y `/api/mode` no quedan expuestos aún.
- El frontend sí intenta consumir esos endpoints para el selector de modo.
- El estándar sugiere prefijo `/api/...`, pero hoy conviven rutas con y sin prefijo.

## Documentación adicional

- `ODOCO-MODES-INFO.md`: definición funcional de modos.
- `ODOCO_CODING_STANDARD.md`: reglas de estructura y estilo del proyecto.
