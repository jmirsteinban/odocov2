// frontend/js/app.js
// Module: ODOCO Control Panel frontend logic
const el = (id) => document.getElementById(id);
let auto = false;
let timer = null;

const API_BASE = window.location.origin; // http://192.168.50.1:8000


function now() {
    return new Date().toLocaleTimeString();
}

function log(msg) {
    const box = el("log");
    const line = `[${now()}] ${msg}\n`;
    box.textContent = line + box.textContent;
}

function setPill(pillEl, text, kind) {
    pillEl.textContent = text;
    pillEl.className = "pill" + (kind ? " " + kind : "");
}

function escapeHTML(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    } [c]));
}

function sigColor(sig) {
    const op = Math.min(1, Math.max(.25, (sig || 0) / 100));
    return `rgba(108,124,255,${op})`;
}

async function fetchJSON(url, opts) {


    const res = await fetch(url, {
        cache: "no-store",
        ...(opts || {})
    });
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    const text = await res.text();

    if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${text.slice(0, 160)}`);
    if (!ct.includes("application/json")) {
        throw new Error(`Respuesta no es JSON. content-type=${ct}. Inicio: ${text.slice(0, 60)}`);
    }
    return JSON.parse(text);
}



async function loadSummary() {
    // Tu GET "/" devuelve JSON (no UI). Perfecto como endpoint de summary.
    const data = await fetchJSON("/api/summary");
    el("lastUpdate").textContent = `última actualización: ${now()}`;

    // AP/LAN
    el("apSsid").textContent = data.ssid || "Unknown";
    el("apIface").textContent = data.network?.ap_iface || "—";
    el("apIp").textContent = data.network?.ap_ip || "—";
    el("dhcpRange").textContent = data.network?.dhcp_range || "—";

    const hostapd = !!data.services?.hostapd;
    const dnsmasq = !!data.services?.dnsmasq;
    el("svcHostapd").textContent = hostapd ? "active" : "inactive";
    el("svcDnsmasq").textContent = dnsmasq ? "active" : "inactive";

    const both = hostapd && dnsmasq;
    el("svcTitle").textContent = both ? "OK" : "Revisar";
    setPill(el("svcPill"), both ? "Online" : "Issues", both ? "good" : "warn");

    const dns = (data.dns || []).map(x => `<code>${escapeHTML(x.replace("nameserver", "").trim())}</code>`).join(" ");
    el("dnsList").innerHTML = dns || "<span class='muted'>—</span>";

    // Server activo
    const s = data.active_server;
    if (!s) {
        el("serverBox").innerHTML = "<div class='muted'>No hay servidor activo.</div>";
    } else {
        el("serverBox").innerHTML = `
        <div>Nombre: <code>${escapeHTML(s.name)}</code></div>
        <div>Host: <code>${escapeHTML(s.host)}</code></div>
        <div>Port: <code>${escapeHTML(s.port)}</code></div>
        <div>Edition: <code>${escapeHTML(s.edition)}</code></div>
      `;
    }

    log("Summary OK (/)");
}

async function loadWanStatus() {
    const data = await fetchJSON("/wan/status");
    const w = data.wlan0 || {};
    el("wanConn").textContent = w.connection || "—";
    el("wanState").textContent = w.state || "—";

    if (w.state === "connected") setPill(el("wanPill"), "Conectado", "good");
    else if (w.state === "disconnected") setPill(el("wanPill"), "Desconectado", "bad");
    else setPill(el("wanPill"), w.state || "unknown", "warn");

    el("wanGw").textContent = data.gateway || "—";
    el("wanRoute").textContent = data.default_route ? `Route: ${data.default_route}` : "Route: —";

    // Tu "/" ya expone wan_ip; lo dejamos ahí (se refresca con loadSummary).
    log("WAN status OK (/wan/status)");
}

async function scanNetworks() {
    const data = await fetchJSON("/wan/networks");
    const nets = data.networks || [];
    const rows = nets.map(n => {
        const inuse = !!n.in_use;
        const sig = Number(n.signal ?? 0);
        const width = Math.max(2, Math.min(100, sig));
        const sec = n.security || "—";
        const ssid = n.ssid || "—";
        return `
        <tr>
          <td class="ssid ${inuse ? "inuse" : ""}">${escapeHTML(ssid)}</td>
          <td class="sig">
            <div class="bar"><div class="fill" style="width:${width}%;background:${sigColor(sig)}"></div></div>
            <div class="muted" style="font-size:12px;margin-top:6px">${sig}%</div>
          </td>
          <td>${escapeHTML(sec)}</td>
          <td>${inuse ? "<span class='pill good'>En uso</span>" : "<span class='pill'>Disponible</span>"}</td>
          <td>
            <button class="small ${inuse ? "" : "primary"}"
              data-action="connect"
              data-ssid="${escapeHTML(ssid)}"
              data-sec="${escapeHTML(sec)}">${inuse ? "Reconectar" : "Conectar"}</button>
          </td>
        </tr>
      `;
    }).join("");

    el("netBody").innerHTML = rows || `<tr><td colspan="5" class="muted">No se detectaron redes.</td></tr>`;
    log(`Scan OK (/wan/networks) • ${nets.length} redes`);
}

async function loadClients() {
    const data = await fetchJSON("/clients");
    const clients = data.clients || [];

    // overview table (compact)
    const compact = clients.slice(0, 12).map(c => `
      <tr>
        <td><code>${escapeHTML(c.ip)}</code></td>
        <td class="muted">${escapeHTML(c.mac)}</td>
        <td>${escapeHTML(c.hostname || "")}</td>
        <td class="muted">${c.expires_in_minutes ?? "—"}</td>
      </tr>
    `).join("");
    el("clientsBody").innerHTML = compact || `<tr><td colspan="4" class="muted">Sin clientes.</td></tr>`;

    // full table
    const full = clients.map(c => `
      <tr>
        <td><code>${escapeHTML(c.ip)}</code></td>
        <td class="muted">${escapeHTML(c.mac)}</td>
        <td>${escapeHTML(c.hostname || "")}</td>
        <td class="muted">${escapeHTML(c.clientid || "")}</td>
        <td class="muted">${c.expiry_epoch ?? "—"}</td>
      </tr>
    `).join("");
    el("clientsFullBody").innerHTML = full || `<tr><td colspan="5" class="muted">Sin clientes.</td></tr>`;

    log(`Clients OK (/clients) • ${clients.length}`);
}

// Modal
function openModal(ssid, sec) {
    el("mSsid").value = ssid || "";
    el("mSec").value = sec || "";
    el("mPass").value = "";
    el("mMsg").textContent = "";
    el("modalBack").style.display = "flex";
    el("modalBack").setAttribute("aria-hidden", "false");
    setTimeout(() => el("mPass").focus(), 50);
}

function closeModal() {
    el("modalBack").style.display = "none";
    el("modalBack").setAttribute("aria-hidden", "true");
}

async function wanConnect() {
    const ssid = el("mSsid").value.trim();
    const password = el("mPass").value;
    const wait_sec = Number(el("mWait").value || 20);

    el("mMsg").textContent = "Conectando…";
    log(`Connect start: ${ssid}`);

    const url = `${window.location.origin}/wan/connect`;
    log(`POST ${url}`);

    const res = await fetchJSON(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        body: JSON.stringify({
            ssid,
            password,
            wait_sec
        })
    });

    // Render resultado “bonito”
    const ok = !!res.ok;
    el("mMsg").textContent = ok ? "✅ Conectado y verificado" : "⚠️ Conectado pero checks fallaron";
    log(`Connect result: ${ok ? "OK" : "FAIL"} • gw_ping=${res.checks?.gateway_ping} inet=${res.checks?.internet_ping} dns=${res.checks?.dns_resolve}`);

    // refrescar estado
    await refreshAll();
    if (ok) closeModal();
}

// Internet button (opcional)
async function testInternet() {
    try {
        const res = await fetchJSON("/wan/internet");
        const ok = !!res.ok;
        log(`Internet: ${ok ? "OK" : "FAIL"} • ping=${res.ping_ok} dns=${res.dns_ok}`);
        alert(ok ? "Internet OK ✅" : "Internet FAIL ⚠️");
    } catch (e) {
        log("Internet endpoint no existe (/wan/internet).");
        alert("No existe /wan/internet todavía. (Opcional) Te dejo el endpoint para agregarlo.");
    }
}

async function refreshAll() {
    await loadSummary();
    el("wanIp").textContent = (await fetchJSON("/api/summary")).network?.wan_ip || "—";
    await loadWanStatus();
    await loadClients();
}

// Tabs
function setTab(name) {
    document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
    el("tab-overview").classList.toggle("hidden", name !== "overview");
    el("tab-networks").classList.toggle("hidden", name !== "networks");
    el("tab-clients").classList.toggle("hidden", name !== "clients");
}
document.querySelectorAll(".tab").forEach(t => {
    t.addEventListener("click", () => setTab(t.dataset.tab));
});

// Events
el("btnRefresh").addEventListener("click", refreshAll);
el("btnScan").addEventListener("click", scanNetworks);
el("btnScan2").addEventListener("click", scanNetworks);
el("btnLoadClients").addEventListener("click", loadClients);
el("btnClients2").addEventListener("click", loadClients);
el("btnInternet").addEventListener("click", testInternet);

el("btnAuto").addEventListener("click", () => {
    auto = !auto;
    el("btnAuto").textContent = `⏱️ Auto (5s): ${auto ? "ON" : "OFF"}`;
    if (timer) clearInterval(timer);
    if (auto) {
        timer = setInterval(async () => {
            await refreshAll();
        }, 5000);
        log("Auto refresh ON (5s)");
    } else {
        log("Auto refresh OFF");
    }
});

el("btnClearLog").addEventListener("click", () => {
    const box = el("log");
    if (box.textContent.trim()) {
        box.textContent = "";
        log("Log limpiado");
    } else {
        // si está vacío, no hagas nada
    }
});

el("btnCopyServer").addEventListener("click", async () => {
    try {
        const data = await fetchJSON("/api/summary");
        const s = data.active_server;
        if (!s) return alert("No hay servidor activo.");
        const txt = `${s.name} ${s.host}:${s.port} (${s.edition})`;
        await navigator.clipboard.writeText(txt);
        log("Server copiado al clipboard");
    } catch (e) {
        log("No se pudo copiar server");
    }
});

// table action connect
el("netBody").addEventListener("click", (ev) => {
    const btn = ev.target.closest("button[data-action='connect']");
    if (!btn) return;
    openModal(btn.dataset.ssid, btn.dataset.sec);
});

el("mCancel").addEventListener("click", closeModal);
el("modalBack").addEventListener("click", (ev) => {
    if (ev.target === el("modalBack")) closeModal();
});
el("mConnect").addEventListener("click", async () => {
    try {
        await wanConnect();
    } catch (e) {
        el("mMsg").textContent = `Error: ${e.message}`;
        log(`ERROR connect: ${e.message}`);
    }
});

// init
(async function() {
    log("UI iniciado");
    await refreshAll();
    await scanNetworks();
})();