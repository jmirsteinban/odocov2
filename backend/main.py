# backend/main.py
# Module: ODOCO Backend — FastAPI application entrypoint


from fastapi import FastAPI
import subprocess
import re
import time
from pathlib import Path

from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Request
from fastapi.templating import Jinja2Templates

from backend.db.init_db import init_db
from backend.routers.servers import router as servers_router
from backend.routers.targets import router as targets_router
from backend.routers.modes import router as modes_router

from sqlalchemy import select
from backend.db.session import SessionLocal
from backend.db.models import Server

import shlex
from pydantic import BaseModel, Field
from typing import Optional


app = FastAPI(title="ODOCO Control Panel", version="0.1.0")
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

init_db()
app.include_router(servers_router)
app.include_router(targets_router)

templates = Jinja2Templates(directory="templates")

def parse_kv_from_file(path: str, key: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    for ln in p.read_text(errors="ignore").splitlines():
        ln = ln.strip()
        if ln.startswith(f"{key}="):
            return ln.split("=", 1)[1].strip()
    return ""

def get_hostapd_iface_and_ssid():
    hostapd_paths = ["/etc/hostapd/hostapd.conf", "/etc/hostapd.conf"]
    for hp in hostapd_paths:
        if Path(hp).exists():
            return {
                "path": hp,
                "ap_iface": parse_kv_from_file(hp, "interface"),
                "ssid": parse_kv_from_file(hp, "ssid"),
            }
    return {"path": "", "ap_iface": "", "ssid": ""}

def get_dnsmasq_dhcp_info():
    # We read only /etc/dnsmasq.conf for now (your config is there).
    p = "/etc/dnsmasq.conf"
    iface = parse_kv_from_file(p, "interface")
    dhcp_range = parse_kv_from_file(p, "dhcp-range")
    return {"path": p, "dhcp_iface": iface, "dhcp_range": dhcp_range}

def ip_addr_brief(iface: str) -> str:
    try:
        out = subprocess.check_output(["ip", "-4", "-br", "addr", "show", iface], stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except Exception:
        return ""



def run_cmd(args: list[str], timeout: int = 20) -> dict:
    try:
        res = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False
        )
        return {
            "rc": res.returncode,
            "stdout": (res.stdout or "").strip(),
            "stderr": (res.stderr or "").strip(),
        }
    except Exception as e:
        return {"rc": 99, "stdout": "", "stderr": str(e)}


def nmcli_args(args: list[str], timeout: int = 25) -> dict:
    return run_cmd(["sudo", "-n", "nmcli", *args], timeout=timeout)


def get_iface_ipv4(iface: str) -> str:
    if not iface:
        return ""
    out = ip_addr_brief(iface)
    # example: wlan1 UP 192.168.50.1/24
    m = re.search(r"\b(\d+\.\d+\.\d+\.\d+/\d+)\b", out)
    return m.group(1) if m else ""

def sh(cmd: str) -> str:
    """Run a shell command and return stdout (safe for read-only ops)."""
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""

def wifi_scan_wlan0():
    res = nmcli_args([
        "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY",
        "dev", "wifi", "list",
        "ifname", "wlan0",
        "--rescan", "yes"
    ], timeout=30)

    if res["rc"] != 0:
        return []

    out = res["stdout"]

    best = {}
    for ln in out.splitlines():
        if not ln.strip():
            continue
        parts = ln.split(":")
        inuse = (parts[0] == "*") if len(parts) >= 1 else False
        ssid = parts[1] if len(parts) >= 2 else ""
        signal = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 0
        security = parts[3] if len(parts) >= 4 else ""

        if not ssid or ssid == "ODOCO_SETUP":
            continue

        rec = {"in_use": inuse, "ssid": ssid, "signal": signal, "security": security}
        if ssid not in best or signal > (best[ssid]["signal"] or 0) or inuse:
            best[ssid] = rec

    nets = list(best.values())
    nets.sort(key=lambda x: (not x["in_use"], -(x["signal"] or 0), x["ssid"]))
    return nets

def nmcli_connect_wlan0(ssid: str, password: Optional[str]):
    args = ["dev", "wifi", "connect", ssid, "ifname", "wlan0"]
    if password and password.strip():
        args += ["password", password]
    return nmcli_args(args, timeout=40)


def nmcli_wlan0_state():
    res = nmcli_args(["-t", "-f", "DEVICE,STATE,CONNECTION", "dev", "status"], timeout=10)
    out = res["stdout"]

    for ln in out.splitlines():
        if ln.startswith("wlan0:"):
            parts = ln.split(":", 2)
            return {
                "raw": ln,
                "state": parts[1] if len(parts) > 1 else "",
                "connection": parts[2] if len(parts) > 2 else "",
            }

    return {"raw": out.strip(), "state": "", "connection": ""}




def ping(ip: str, count: int = 1, timeout_sec: int = 2) -> bool:
    if not ip:
        return False
    try:
        rc = subprocess.run(
            ["sudo", "-n", "ping", "-c", str(count), "-W", str(timeout_sec), ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_sec + 2,
            check=False
        ).returncode
        return rc == 0
    except Exception:
        return False

def dns_resolve(hostname: str) -> bool:
    if not hostname:
        return False
    try:
        rc = subprocess.run(
            ["sudo", "-n", "getent", "hosts", hostname],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False
        ).returncode
        return rc == 0
    except Exception:
        return False


def connect_and_verify(ssid: str, password: Optional[str], wait_sec: int = 20):
    connect_output = nmcli_connect_wlan0(ssid, password)

    # wait for NM state to become connected
    t0 = time.time()
    state = nmcli_wlan0_state()
    while time.time() - t0 < wait_sec:
        state = nmcli_wlan0_state()
        if state["state"] == "connected":
            break
        time.sleep(1)

    route = get_default_route()
    default_route = route["raw"]
    gw = route["gateway"]

    # Connectivity checks
    gw_ok = ping(gw) if gw else False
    internet_ip_ok = ping("1.1.1.1") or ping("8.8.8.8")
    dns_ok = dns_resolve("one.one.one.one") or dns_resolve("google.com")

    ok = (state["state"] == "connected") and gw_ok and internet_ip_ok and dns_ok

    return {
        "ok": ok,
        "ssid_requested": ssid,
        "nmcli_connect": connect_output,
        "wlan0_state": state,
        "default_route": default_route,
        "gateway": gw,
        "checks": {
            "gateway_ping": gw_ok,
            "internet_ping": internet_ip_ok,
            "dns_resolve": dns_ok
        }
    }


def get_default_route():
    out = sh("ip route show default")
    # example: default via 172.16.1.1 dev wlan0 proto dhcp src 172.16.1.212 metric 600
    m_dev = re.search(r"\bdev\s+(\S+)", out)
    m_gw  = re.search(r"\bvia\s+(\S+)", out)
    m_src = re.search(r"\bsrc\s+(\S+)", out)
    return {
        "raw": out,
        "wan_iface": m_dev.group(1) if m_dev else "",
        "gateway": m_gw.group(1) if m_gw else "",
        "wan_ip": m_src.group(1) if m_src else "",
    }

def guess_lan_from_leases(clients):
    # If we have clients like 192.168.50.153, return "192.168.50.0/24"
    if not clients:
        return ""
    ip = clients[0].get("ip", "")
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    return ""


def read_dnsmasq_leases():
    leases_paths = [
        "/var/lib/misc/dnsmasq.leases",
        "/var/lib/dnsmasq/dnsmasq.leases",
    ]
    for p in leases_paths:
        fp = Path(p)
        if fp.exists():
            rows = []
            for ln in fp.read_text(errors="ignore").splitlines():
                if not ln.strip():
                    continue
                # format: expiry epoch, mac, ip, hostname, clientid
                parts = ln.split()
                if len(parts) >= 5:
                    expiry, mac, ip, hostname, clientid = parts[:5]
                    now = int(time.time())
                    expiry_int = int(expiry) if expiry.isdigit() else None
                    expires_in = (expiry_int - now) if expiry_int else None

                    rows.append({
                        "ip": ip,
                        "mac": mac,
                        "hostname": "" if hostname == "*" else hostname,
                        "expiry_epoch": expiry_int,
                        "expires_in_seconds": expires_in,
                        "expires_in_minutes": (expires_in // 60) if expires_in is not None else None,
                        "clientid": "" if clientid == "*" else clientid,
                    })
            return rows
    return []


def get_ssid() -> str:
    # Try common hostapd paths. We don't change anything; read-only.
    candidates = [
        "/etc/hostapd/hostapd.conf",
        "/etc/hostapd.conf",
    ]
    for p in candidates:
        if Path(p).exists():
            line = sh(f"grep -E '^\\s*ssid=' {p} | tail -n 1")
            if line and "=" in line:
                return line.split("=", 1)[1].strip()
    return "Unknown"


def get_dns_resolv_conf():
    p = Path("/etc/resolv.conf")
    if not p.exists():
        return []
    # Return only nameserver lines
    lines = [ln.strip() for ln in p.read_text(errors="ignore").splitlines()]
    return [ln for ln in lines if ln.startswith("nameserver")]


def get_clients_count() -> int:
    # dnsmasq leases file (common path)
    leases_paths = [
        "/var/lib/misc/dnsmasq.leases",
        "/var/lib/dnsmasq/dnsmasq.leases",
    ]
    for p in leases_paths:
        fp = Path(p)
        if fp.exists():
            content = fp.read_text(errors="ignore").strip()
            if not content:
                return 0
            return len([ln for ln in content.splitlines() if ln.strip()])
    return 0


def get_service_active(service: str) -> bool:
    out = sh(f"systemctl is-active {service}")
    return out.strip() == "active"

class WanConnectReq(BaseModel):
    ssid: str = Field(min_length=1, max_length=64)
    password: Optional[str] = Field(default=None, max_length=128)
    wait_sec: int = Field(default=20, ge=5, le=60)

@app.get("/", response_class=HTMLResponse)
def dashboard_ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/summary")
def dashboard():

    db = SessionLocal()
    try:
        active = db.execute(select(Server).where(Server.is_active == True)).scalars().first()
    finally:
        db.close()

    clients = read_dnsmasq_leases()
    named = [c for c in clients if c.get("hostname")]
    route = get_default_route()

    ap = get_hostapd_iface_and_ssid()
    dhcp = get_dnsmasq_dhcp_info()

    ap_iface = ap.get("ap_iface") or dhcp.get("dhcp_iface")
    ap_ip_cidr = get_iface_ipv4(ap_iface)

    return {
        "ssid": ap.get("ssid") or get_ssid(),
        "network": {
            "wan_iface": route["wan_iface"],
            "wan_ip": route["wan_ip"],
            "gateway": route["gateway"],
            "ap_iface": ap_iface,
            "ap_ip": ap_ip_cidr,
            "dhcp_range": dhcp.get("dhcp_range", ""),
        },
        "clients": {
            "connected": len(clients),
            "named": len(named),
            "hostnames": [c["hostname"] for c in named][:10],
        },
        "dns": get_dns_resolv_conf(),
        "services": {
            "hostapd": get_service_active("hostapd"),
            "dnsmasq": get_service_active("dnsmasq"),
        },
        "active_server": None if not active else {
            "id": active.id,
            "name": active.name,
            "host": active.host,
            "port": active.port,
            "edition": active.edition,
        },
    }

@app.get("/clients")
def clients():
    return {"clients": read_dnsmasq_leases()}


@app.get("/ui")
def ui():
    return RedirectResponse(url="/", status_code=307)

@app.get("/wan/networks")
def wan_networks():
    return {"networks": wifi_scan_wlan0()}

@app.get("/wan/status")
def wan_status():
    route = get_default_route()
    return {
        "wlan0": nmcli_wlan0_state(),
        "default_route": route["raw"],
        "gateway": route["gateway"],
    }


@app.post("/wan/connect")
def wan_connect(req: WanConnectReq):
    # ⚠️ Usa el panel por LAN (192.168.50.1) para no perder sesión
    return connect_and_verify(req.ssid, req.password, wait_sec=req.wait_sec)



@app.get("/wan/internet")
def wan_internet():
    # Usa tus helpers existentes (ping/dns_resolve)
    internet_ip_ok = ping("1.1.1.1") or ping("8.8.8.8")
    dns_ok = dns_resolve("one.one.one.one") or dns_resolve("google.com")
    gw = get_default_route()["gateway"]
    gw_ok = ping(gw) if gw else False

    return {
        "ok": bool(gw_ok and internet_ip_ok and dns_ok),
        "gateway": gw,
        "ping_ok": bool(internet_ip_ok),
        "dns_ok": bool(dns_ok),
        "gateway_ping_ok": bool(gw_ok),
    }