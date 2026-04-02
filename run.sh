#!/bin/sh
set -e

# ---------------------------------------------------------------------------
# FEMS Shelly Proxy – Startup Script für HA Add-On
# ---------------------------------------------------------------------------
# 1. Ermittelt das aktive Netzwerk-Interface (Default-Route)
# 2. Fügt IP-Aliase für jedes konfigurierte Gerät hinzu
# 3. Startet den Python-Proxy
# 4. Entfernt IP-Aliase beim Shutdown (SIGTERM)
# ---------------------------------------------------------------------------

OPTIONS_FILE="/data/options.json"

# --- Netzwerk-Interface automatisch erkennen ---
detect_interface() {
    # Default-Route → aktives Interface
    iface=$(ip route | grep default | awk '{print $5}' | head -1)
    if [ -z "$iface" ]; then
        echo "[ERROR] Kein aktives Netzwerk-Interface gefunden!"
        exit 1
    fi
    echo "$iface"
}

# --- Subnetz-Maske vom Interface lesen ---
detect_prefix_len() {
    local iface="$1"
    # Erste IPv4-Adresse mit Prefix-Länge extrahieren
    prefix=$(ip -4 addr show "$iface" | grep 'inet ' | head -1 | awk '{print $2}' | cut -d'/' -f2)
    echo "${prefix:-24}"
}

# --- IP-Adressen aus options.json extrahieren ---
get_device_ips() {
    python3 -c "
import json, sys
with open('$OPTIONS_FILE') as f:
    opts = json.load(f)
for d in opts.get('devices', []):
    ip = d.get('ip', '')
    if ip:
        print(ip)
"
}

# --- IP-Aliase hinzufügen ---
ADDED_IPS=""
add_ip_aliases() {
    local iface="$1"
    local prefix="$2"

    for ip in $(get_device_ips); do
        # Prüfen ob IP bereits existiert
        if ip addr show dev "$iface" | grep -q "inet ${ip}/"; then
            echo "[INFO] IP $ip ist bereits auf $iface konfiguriert"
        else
            echo "[INFO] Füge IP $ip/$prefix auf $iface hinzu"
            ip addr add "${ip}/${prefix}" dev "$iface" || {
                echo "[ERROR] Konnte $ip nicht hinzufügen!"
                continue
            }
        fi
        ADDED_IPS="$ADDED_IPS $ip"
    done
}

# --- IP-Aliase entfernen (Cleanup) ---
remove_ip_aliases() {
    local iface="$1"
    local prefix="$2"

    echo "[INFO] Cleanup: Entferne IP-Aliase..."
    for ip in $ADDED_IPS; do
        echo "[INFO] Entferne IP $ip von $iface"
        ip addr del "${ip}/${prefix}" dev "$iface" 2>/dev/null || true
    done
}

# --- Main ---
IFACE=$(detect_interface)
PREFIX=$(detect_prefix_len "$IFACE")
echo "[INFO] Netzwerk-Interface: $IFACE (Prefix: /$PREFIX)"

# Prüfe ob options.json existiert
if [ ! -f "$OPTIONS_FILE" ]; then
    echo "[ERROR] $OPTIONS_FILE nicht gefunden! Läuft das Script als HA Add-On?"
    exit 1
fi

# IP-Aliase hinzufügen
add_ip_aliases "$IFACE" "$PREFIX"

# Cleanup bei SIGTERM/SIGINT
cleanup() {
    remove_ip_aliases "$IFACE" "$PREFIX"
    # Python-Prozess beenden
    kill "$PROXY_PID" 2>/dev/null || true
    wait "$PROXY_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

# Proxy starten
echo "[INFO] Starte Shelly-FEMS-Proxy..."
python3 -u /app/shelly_proxy.py &
PROXY_PID=$!

# Warten bis Proxy beendet wird
wait "$PROXY_PID"
