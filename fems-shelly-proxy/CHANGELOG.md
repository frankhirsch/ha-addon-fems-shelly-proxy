# Changelog

## 1.0.2 — 2026-04-26

### Fixed

- Add-On startet nach HA-Neustart nicht zuverlässig: `run.sh` wartet jetzt bis zu
  30 s auf das Netzwerk-Interface (Default-Route) bevor es abbricht
- `Shelly.GetStatus`-HTTP-Requests wurden auf INFO-Level geloggt und fluteten das
  Protokoll (~4–8 Zeilen/Sek); erscheinen jetzt nur noch auf DEBUG-Level

### Added

- Konfigurierbares Log-Level (DEBUG / INFO / WARNING / ERROR / CRITICAL) als
  Dropdown in der HA-Benutzeroberfläche
- Automatischer Neustart des Python-Proxy bei unerwartetem Absturz (ohne manuellen
  Eingriff)
- Startup-Banner im Log mit Versionsnummer und Netzwerk-Interface
- Version wird dynamisch aus `config.yaml` gelesen – kein doppelter Pflegepunkt

## 1.0.1 — 2026-04-02

### Fixed

- Supervisor API URL had double `/api` path, causing 404 errors for all HA entity requests

### Added

- Per-device `invert` option to negate power and current values for production meters (e.g. balcony PV, solar inverters)

## 1.0.0 — 2026-04-02

### Added

- Initial release
- Emulates Shelly Plug S Gen3 HTTP API from Home Assistant sensor data
- Automatic IP alias management (one virtual IP per device on port 80)
- Automatic network interface detection
- Supervisor API integration (no manual token required)
- Supports Shelly PM Mini Gen3, Plus PM Mini, 1PM Gen2, EM, and any HA power sensor
- Clean IP alias removal on shutdown
