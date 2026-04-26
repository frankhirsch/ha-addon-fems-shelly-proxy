#!/bin/sh

# ---------------------------------------------------------------------------
# FEMS Shelly Proxy – Startup Script für HA Add-On
# ---------------------------------------------------------------------------
# 1. Ermittelt das aktive Netzwerk-Interface (Default-Route), mit Retry
# 2. Fügt IP-Aliase für jedes konfigurierte Gerät hinzu
# 3. Startet den Python-Proxy (mit automatischem Neustart bei Absturz)
# 4. Entfernt IP-Aliase beim Shutdown (SIGTERM)
# ---------------------------------------------------------------------------

OPTIONS_FILE="/data/options.json"

# --- Netzwerk-Interface automatisch erkennen (bis zu 10 Versuche à 3 s) ---
detect_interface() {
    local i=0
    while [ $i -lt 10 ]; do
        iface=$(ip route | grep default | awk '{print $5}' | head -1)
        if [ -n "$iface" ]; then
            echo "$iface"
            return 0
        fi
        i=$((i + 1))
        echo "[INFO] Warte auf Netzwerk-Interface (Versuch $i/10)..."
        sleep 3
    done
    echo "[ERROR] Kein aktives Netzwerk-Interface nach 10 Versuchen!"
    exit 1
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

# Version aus config.yaml lesen (einzige Quelle der Wahrheit)
VERSION=$(grep '^version:' /app/config.yaml | sed 's/version:[[:space:]]*"\(.*\)"/\1/' | tr -d '[:space:]')
VERSION=${VERSION:-unknown}

echo "[INFO] ============================================"
echo "[INFO] FEMS Shelly Proxy v${VERSION} – Startup"
echo "[INFO] Interface: $IFACE  Prefix: /$PREFIX"
echo "[INFO] ============================================"

# Prüfe ob options.json existiert
if [ ! -f "$OPTIONS_FILE" ]; then
    echo "[ERROR] $OPTIONS_FILE nicht gefunden! Läuft das Script als HA Add-On?"
    exit 1
fi

# IP-Aliase hinzufügen
add_ip_aliases "$IFACE" "$PREFIX"

# Cleanup bei SIGTERM/SIGINT
SHUTDOWN_REQUESTED=0
cleanup() {
    SHUTDOWN_REQUESTED=1
    remove_ip_aliases "$IFACE" "$PREFIX"
    kill "$PROXY_PID" 2>/dev/null || true
    wait "$PROXY_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

# Proxy starten – mit automatischem Neustart bei unerwartetem Absturz
while [ "$SHUTDOWN_REQUESTED" -eq 0 ]; do
    echo "[INFO] Starte Shelly-FEMS-Proxy..."
    python3 -u /app/shelly_proxy.py &
    PROXY_PID=$!
    wait "$PROXY_PID" || true
    if [ "$SHUTDOWN_REQUESTED" -eq 0 ]; then
        echo "[WARN] Proxy unerwartet beendet – Neustart in 5s..."
        sleep 5
    fi
done
