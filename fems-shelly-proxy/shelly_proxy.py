#!/usr/bin/env python3
from __future__ import annotations
"""
Shelly-FEMS-Proxy
=================
Liest Sensordaten aus Home Assistant und emuliert pro konfiguriertem
Gerät einen Shelly Plug S Gen3 HTTP-Endpunkt, den FEMS Shelly DIY
als echten Plug S erkennt.

Betriebsmodi:
  1. HA Add-On:  Liest /data/options.json, nutzt Supervisor-API
  2. Standalone:  Liest config.json, nutzt HA REST-API mit Token

Architektur:
  Home Assistant (Shelly PM Mini Gen3 Sensoren)
       ↓  REST API / Supervisor API
  shelly_proxy.py (dieses Script)
       ↓  HTTP :80 (je eine IP pro Gerät)
  FEMS Shelly DIY App → sieht "Shelly Plug S Gen3"
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from pathlib import Path

import aiohttp
from aiohttp import web

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("shelly-proxy")

# ---------------------------------------------------------------------------
# Configuration loader
# ---------------------------------------------------------------------------
ADDON_OPTIONS_PATH = Path("/data/options.json")
LOCAL_CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    """
    Load configuration. Priority:
      1. /data/options.json  (HA Add-On)
      2. config.json         (Standalone)

    Normalises both formats into a common structure.
    """
    if ADDON_OPTIONS_PATH.exists():
        log.info("Lade Konfiguration aus %s (Add-On Modus)", ADDON_OPTIONS_PATH)
        with open(ADDON_OPTIONS_PATH) as f:
            opts = json.load(f)
        # Normalize Add-On schema (flat entity fields → nested dict)
        devices = []
        for d in opts.get("devices", []):
            devices.append({
                "name": d["name"],
                "ip": d.get("ip", "0.0.0.0"),
                "port": 80,
                "invert": d.get("invert", False),
                "entities": {
                    "power": d.get("entity_power", ""),
                    "voltage": d.get("entity_voltage", ""),
                    "current": d.get("entity_current", ""),
                    "energy": d.get("entity_energy", ""),
                },
            })
        return {"mode": "addon", "devices": devices}

    elif LOCAL_CONFIG_PATH.exists():
        log.info("Lade Konfiguration aus %s (Standalone Modus)", LOCAL_CONFIG_PATH)
        with open(LOCAL_CONFIG_PATH) as f:
            cfg = json.load(f)
        # Ensure each device has ip/port fields
        for d in cfg.get("devices", []):
            d.setdefault("ip", "0.0.0.0")
            d.setdefault("port", 80)
        cfg["mode"] = "standalone"
        return cfg

    else:
        raise FileNotFoundError(
            "Keine Konfiguration gefunden! "
            "Weder /data/options.json (Add-On) noch config.json (Standalone) vorhanden."
        )


# ---------------------------------------------------------------------------
# Home Assistant REST API client
# ---------------------------------------------------------------------------
class HAClient:
    """Reads entity states from Home Assistant REST API."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._session: aiohttp.ClientSession | None = None

    @classmethod
    def from_config(cls, cfg: dict) -> HAClient:
        """Create HAClient based on config mode (Add-On vs Standalone)."""
        if cfg["mode"] == "addon":
            # Supervisor API: Token kommt aus Umgebungsvariable
            token = os.environ.get("SUPERVISOR_TOKEN", "")
            if not token:
                log.warning("SUPERVISOR_TOKEN nicht gesetzt! HA-API wird fehlschlagen.")
            return cls("http://supervisor/core", token)
        else:
            # Standalone: URL + Token aus config.json
            ha_cfg = cfg["homeassistant"]
            return cls(ha_cfg["url"], ha_cfg["token"])

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.token}"}
            )
        return self._session

    async def get_state(self, entity_id: str) -> float | None:
        """Return numeric state of an HA entity, or None."""
        session = await self._get_session()
        url = f"{self.base_url}/api/states/{entity_id}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status != 200:
                    log.warning("HA returned %s for %s", r.status, entity_id)
                    return None
                data = await r.json()
                state = data.get("state")
                if state in ("unavailable", "unknown", None):
                    return None
                return float(state)
        except Exception as e:
            log.error("HA request failed for %s: %s", entity_id, e)
            return None

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


# ---------------------------------------------------------------------------
# Virtual Shelly Plug S Gen3 device
# ---------------------------------------------------------------------------
class VirtualShellyPlugS:
    """
    Emulates the HTTP API of a Shelly Plug S Gen3.
    FEMS polls:
      /rpc/Shelly.GetStatus   → full device status
      /rpc/Shelly.GetDeviceInfo → device identification
      /shelly                   → shorthand device info
      /rpc/Switch.GetStatus?id=0 → switch/meter data
    """

    def __init__(self, device_cfg: dict, ha_client: HAClient):
        self.name = device_cfg["name"]
        self.ip = device_cfg.get("ip", "0.0.0.0")
        self.port = device_cfg.get("port", 80)
        self.entities = device_cfg["entities"]
        self.invert = device_cfg.get("invert", False)
        self.ha = ha_client

        # Generate a stable fake MAC from the device name
        h = hashlib.md5(self.name.encode()).hexdigest()[:12].upper()
        self.mac = h
        self.device_id = f"shellyplugsg3-{h.lower()}"

    async def _read_sensors(self) -> dict:
        """Read current values from HA.

        If 'invert' is enabled, apower and current are negated — matching
        the behaviour of a real Shelly Plug S Gen3 that reports negative
        apower when energy flows back (e.g. solar production).
        Voltage and energy are never inverted (same as OpenEMS/FEMS).
        """
        power = await self.ha.get_state(self.entities.get("power", "")) or 0.0
        voltage = await self.ha.get_state(self.entities.get("voltage", "")) or 230.0
        current = await self.ha.get_state(self.entities.get("current", "")) or 0.0

        # Energy: HA liefert kWh kumuliert, Shelly erwartet Wh
        energy_kwh = await self.ha.get_state(self.entities.get("energy", ""))
        energy_wh = (energy_kwh * 1000.0) if energy_kwh is not None else 0.0

        # Invert power + current (not voltage/energy) to match real
        # Shelly Gen3 sign convention: negative = generation
        if self.invert:
            power = -power
            current = -current

        return {
            "apower": round(power, 1),
            "voltage": round(voltage, 1),
            "current": round(current, 3),
            "energy_wh": round(energy_wh, 3),
        }

    def _switch_status(self, sensors: dict) -> dict:
        """Build the switch:0 status object (Plug S Gen3 format)."""
        now_ts = int(time.time())
        return {
            "id": 0,
            "source": "init",
            "output": True,
            "apower": sensors["apower"],
            "voltage": sensors["voltage"],
            "current": sensors["current"],
            "freq": 50.0,
            "aenergy": {
                "total": sensors["energy_wh"],
                "by_minute": [
                    sensors["apower"] * 1000 / 60,
                    sensors["apower"] * 1000 / 60,
                    sensors["apower"] * 1000 / 60,
                ],
                "minute_ts": now_ts,
            },
            "temperature": {"tC": 35.0, "tF": 95.0},
        }

    def _device_info(self) -> dict:
        """Shelly.GetDeviceInfo – FEMS prüft 'app' und 'gen'."""
        return {
            "name": self.name,
            "id": self.device_id,
            "mac": self.mac,
            "slot": 0,
            "model": "S3PL-00112EU",
            "gen": 3,
            "fw_id": "20250101-000000/1.0.0-proxy",
            "ver": "1.0.0",
            "app": "PlugSG3",
            "auth_en": False,
            "auth_domain": None,
        }

    # -- HTTP Handlers -------------------------------------------------------

    async def handle_shelly_get_status(self, request: web.Request) -> web.Response:
        sensors = await self._read_sensors()
        now_ts = int(time.time())
        status = {
            "ble": {},
            "cloud": {"connected": False},
            "input:0": {"id": 0, "state": True},
            "mqtt": {"connected": False},
            "switch:0": self._switch_status(sensors),
            "sys": {
                "mac": self.mac,
                "restart_required": False,
                "time": time.strftime("%H:%M"),
                "unixtime": now_ts,
                "uptime": now_ts % 86400,
                "ram_size": 262144,
                "ram_free": 150000,
                "fs_size": 524288,
                "fs_free": 300000,
                "available_updates": {},
            },
            "wifi": {
                "sta_ip": self.ip,
                "status": "got ip",
                "ssid": "proxy",
                "rssi": -50,
            },
        }
        log.debug("[%s] GetStatus → apower=%.1f W", self.name, sensors["apower"])
        return web.json_response(status)

    async def handle_shelly_get_device_info(self, request: web.Request) -> web.Response:
        return web.json_response(self._device_info())

    async def handle_shelly_shorthand(self, request: web.Request) -> web.Response:
        """GET /shelly – Kurzform für Device-Erkennung."""
        return web.json_response(self._device_info())

    async def handle_switch_get_status(self, request: web.Request) -> web.Response:
        """GET /rpc/Switch.GetStatus?id=0"""
        sensors = await self._read_sensors()
        return web.json_response(self._switch_status(sensors))

    async def handle_switch_set(self, request: web.Request) -> web.Response:
        """GET /rpc/Switch.Set – Schalten ignorieren (PM Mini hat kein Relais)."""
        log.info("[%s] Switch.Set ignoriert (reines Messgerät)", self.name)
        return web.json_response({"was_on": True})

    async def handle_rpc_post(self, request: web.Request) -> web.Response:
        """POST /rpc – JSON-RPC Dispatcher."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        method = body.get("method", "")
        log.debug("[%s] RPC method=%s", self.name, method)

        if method == "Shelly.GetStatus":
            return await self.handle_shelly_get_status(request)
        elif method == "Shelly.GetDeviceInfo":
            return await self.handle_shelly_get_device_info(request)
        elif method == "Switch.GetStatus":
            return await self.handle_switch_get_status(request)
        elif method == "Switch.Set":
            return await self.handle_switch_set(request)
        else:
            return web.json_response({"id": body.get("id"), "result": {}})

    def create_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/rpc/Shelly.GetStatus", self.handle_shelly_get_status)
        app.router.add_get("/rpc/Shelly.GetDeviceInfo", self.handle_shelly_get_device_info)
        app.router.add_get("/rpc/Switch.GetStatus", self.handle_switch_get_status)
        app.router.add_get("/rpc/Switch.Set", self.handle_switch_set)
        app.router.add_get("/shelly", self.handle_shelly_shorthand)
        app.router.add_post("/rpc", self.handle_rpc_post)
        return app


# ---------------------------------------------------------------------------
# Main – startet einen HTTP-Server pro konfiguriertem Gerät
# ---------------------------------------------------------------------------
async def main():
    cfg = load_config()
    ha_client = HAClient.from_config(cfg)

    runners = []
    for dev_cfg in cfg["devices"]:
        device = VirtualShellyPlugS(dev_cfg, ha_client)
        app = device.create_app()
        runner = web.AppRunner(app)
        await runner.setup()

        bind_ip = dev_cfg.get("ip", "0.0.0.0")
        bind_port = dev_cfg.get("port", 80)
        site = web.TCPSite(runner, bind_ip, bind_port)
        await site.start()
        runners.append(runner)
        log.info(
            "✓ Virtueller Shelly '%s' auf %s:%d gestartet (→ %s)",
            dev_cfg["name"],
            bind_ip,
            bind_port,
            dev_cfg["entities"].get("power", "?"),
        )

    log.info(
        "Alle %d virtuellen Shelly-Geräte aktiv. Warte auf FEMS-Anfragen…",
        len(runners),
    )

    try:
        await asyncio.Event().wait()
    finally:
        await ha_client.close()
        for runner in runners:
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
