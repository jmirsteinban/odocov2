# backend/main.py
# Module: ODOCO Backend — FastAPI application entrypoint

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import subprocess
import re
import time
import shlex
from pathlib import Path
from typing import Optional, Tuple, List

from pydantic import BaseModel, Field
from sqlalchemy import select
from backend.db.session import SessionLocal
from backend.db.models import Server
from backend.db.init_db import init_db
from backend.routers.servers import router as servers_router
from backend.routers.targets import router as targets_router


# ----------------------------
# Safe command runner (NO shell=True)
# ----------------------------
def run_cmd(args: List[str], sudo: bool = False, timeout: int = 8) -> Tuple[int, str, str]:
    """
    Run a command safely (shell=False). Returns (returncode, stdout, stderr).
    If sudo=True, it will prepend: sudo -n (non-interactive).
    """
    if sudo:
        args = ["sudo", "-n"] + args

    try:
        cp = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return cp.returncode, (cp.stdout or "").strip(), (cp.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 1, "", str(e)


def cmd_out(args: List[str], sudo: bool = False, timeout: int = 8) -> str:
    rc, out, _err = run_cmd(args, sudo=sudo, timeout=timeout)
    return out if rc == 0 else ""


def nmcli(args: List[str]) -> str:
    # nmcli often requires sudo in your setup
    return cmd_out(["nmcli"] + args, sudo=True, timeout=12)


# ----------------------------
# Network helpers (single source of truth)
# ----------------------------
def get_default_route():
    out = cmd_out(["ip", "route", "show", "default"])
    # example: default via 172.16.1.1 dev wlan0 proto dhcp src 172.16.1.212 metric 600
    m_dev = re.search(r"\bdev\s+(\S+)", out)
    m_gw = re.search(r"\bvia\s+(\S+)", out)
    m_src = re.search(r"\bsrc\s+(\S+)", out)
    return {
        "raw": out,
        "wan_iface": m_dev.group(1) if m_dev else "",
        "gateway": m_gw.group(1) if m_gw else "",
        "wan_ip": m_src.group(1) if m_src else "",
    }


def ping(ip: str, count: int = 1, timeout_sec: int = 2) -> bool:
    if not ip:
        return False
    # ping usually doesn't need sudo; if yours does, change sudo=True
    rc, _out, _err = run_cmd(["ping", "-c", str(count), "-W", str(timeout_sec), ip], sudo=False, timeout=timeout_sec + 2)
    return rc == 0


def dns_resolve(hostname: str) -> bool:
    if not hostname:
        return False
    rc, out, _err = run_cmd(["getent", "hosts", hostname], sudo=True, timeout=4)
    return rc == 0 and bool(out.strip())


def nmcli_wlan0_state():
    # nmcli -t -f DEVICE,STATE,CONNECTION dev status
    out = nmcli(["-t", "-f", "DEVICE,STATE,CONNECTION", "dev", "status"])
    for ln in out.splitlines():
        if ln.startswith("wlan0:"):
            parts = ln.split(":", 2)
            return {
                "raw": ln,
                "state": parts[1] if len(parts) > 1 else "",
                "connection": parts[2] if len(parts) > 2 else "",
            }
    return {"raw": out.strip(), "state": "", "connection": ""}


def wifi_scan_wlan0():
    out = nmcli(["-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "ifname", "wlan0", "--rescan", "yes"])
    best = {}  # ssid -> record (keep highest signal)

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
    return nmcli(args)


def connect_and_verify(ssid: str, password: Optional[str], wait_sec: int = 20):
    connect_output = nmcli_connect_wlan0(ssid, password)

    t0 = time.time()
    state = nmcli_wlan0_state()
    while time.time() - t0 < wait_sec:
        state = nmcli_wlan0_state()
        if state["state"] == "connected":
            break
        time.sleep(1)

    route = get_default_route()
    gw = route["gateway"]

    gw_ok = ping(gw) if gw else False
    internet_ip_ok = ping("1.1.1.1") or ping("8.8.8.8")
    dns_ok = dns_resolve("one.one.one.one") or dns_resolve("google.com")

    ok = (state["state"] == "connected") and gw_ok and internet_ip_ok and dns_ok

    return {
        "ok": ok,
        "ssid_requested": ssid,
        "nmcli_connect_output": connect_output.strip(),
        "wlan0_state": state,
        "default_route": route["raw"],
        "gateway": gw,
        "checks": {
            "gateway_ping": gw_ok,
            "internet_ping": internet_ip_ok,
            "dns_resolve": dns_ok,
        },
    }


# ----------------------------
# Existing helpers you already had (kept)
# ----------------------------
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
    p = "/etc/dnsmasq.conf"
    iface = parse_kv_from_file(p, "interface")
    dhcp_range = parse_kv_from_file(p, "dhcp-range")
    return {"path": p, "dhcp_iface": iface, "dhcp_range": dhcp_range}

def get_iface_ipv4(iface: str) -> str:
    if not iface:
        return ""
    out = cmd_out(["ip", "-4", "-br", "addr", "show", iface])
    m = re.search(r"\b(\d+\.\d+\.\d+\.\d+/\d+)\b", out)
    return m.group(1) if m else ""

def get_dns_resolv_conf():
    p = Path("/etc/resolv.conf")
    if not p.exists():
        return []
    lines = [ln.strip() for ln in p.read_text(errors="ignore").splitlines()]
    return [ln for ln in lines if ln.startswith("nameserver")]

def get_service_active(service: str) -> bool:
    rc, out, _err = run_cmd(["systemctl", "is-active", service], sudo=False, timeout=3)
    return rc == 0 and out.strip() == "active"


# ----------------------------
# FastAPI app
# ----------------------------
app = FastAPI(title="ODOCO Control Panel", version="0.1.0")
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

init_db()
app.include_router(servers_router)
app.include_router(targets_router)

class WanConnectReq(BaseModel):
    ssid: str = Field(min_length=1, max_length=64)
    password: Optional[str] = Field(default=None, max_length=128)
    wait_sec: int = Field(default=20, ge=5, le=60)

@app.get("/", response_class=HTMLResponse)
def dashboard_ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/ui")
def ui_redirect():
    return RedirectResponse(url="/", status_code=307)

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
        "ssid": ap.get("ssid") or "Unknown",
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

@app.get("/wan/status")
def wan_status():
    route = get_default_route()
    return {
        "wlan0": nmcli_wlan0_state(),
        "default_route": route["raw"],
        "gateway": route["gateway"],
    }

@app.get("/wan/networks")
def wan_networks():
    return {"networks": wifi_scan_wlan0()}

@app.post("/wan/connect")
def wan_connect(req: WanConnectReq):
    return connect_and_verify(req.ssid, req.password, wait_sec=req.wait_sec)

@app.get("/wan/internet")
def wan_internet():
    route = get_default_route()
    gw = route["gateway"]
    gw_ok = ping(gw) if gw else False
    internet_ip_ok = ping("1.1.1.1") or ping("8.8.8.8")
    dns_ok = dns_resolve("one.one.one.one") or dns_resolve("google.com")

    return {
        "ok": bool(gw_ok and internet_ip_ok and dns_ok),
        "gateway": gw,
        "ping_ok": bool(internet_ip_ok),
        "dns_ok": bool(dns_ok),
        "gateway_ping_ok": bool(gw_ok),
    }
