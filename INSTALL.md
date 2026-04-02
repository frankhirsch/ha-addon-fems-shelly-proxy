# FEMS Shelly Proxy – Installation als Home Assistant Add-On

## Voraussetzungen

- Home Assistant OS (HAOS) auf Raspberry Pi, NUC oder VM
- Netzwerkzugriff auf das FEMS (gleiches LAN/Subnetz)
- Freie IP-Adressen im LAN (z.B. 192.168.178.10–20), die nicht im DHCP-Bereich liegen
- Shelly PM Mini Gen3 (oder andere Shelly-Sensoren) bereits in HA eingebunden

---

## Schritt 1: Add-On-Repository vorbereiten

Das Add-On muss als **lokales Repository** in HA verfügbar sein. Dafür wird das Projektverzeichnis auf den HA-Host kopiert.

### Option A: Direkt ins Add-On-Verzeichnis kopieren

Per SSH auf den HA-Host verbinden und das Verzeichnis anlegen:

```bash
ssh root@<HA-IP>

# Add-On-Verzeichnis erstellen
mkdir -p /addons/fems-shelly-proxy
```

Dann die folgenden Dateien ins Verzeichnis `/addons/fems-shelly-proxy/` kopieren:

```
config.yaml
Dockerfile
run.sh
shelly_proxy.py
```

Zum Beispiel per `scp` vom lokalen Rechner:

```bash
scp config.yaml Dockerfile run.sh shelly_proxy.py \
    root@<HA-IP>:/addons/fems-shelly-proxy/
```

### Option B: Git-Repository verwenden

Falls das Projekt in einem Git-Repository liegt, kann es auch als
externes Repository in HA hinzugefügt werden:

1. **Einstellungen** → **Add-Ons** → **Add-On-Store** (unten rechts: drei Punkte)
2. **Repositorys** → Repository-URL eintragen → **Hinzufügen**

---

## Schritt 2: Add-On in HA installieren

1. In Home Assistant: **Einstellungen** → **Add-Ons**
2. **Add-On-Store** (Button unten rechts)
3. Oben rechts: drei Punkte → **Auf Updates prüfen**
4. Unter **Lokale Add-Ons** erscheint **FEMS Shelly Proxy**
5. Anklicken → **Installieren**

> Falls das Add-On nicht erscheint: HA neu starten und erneut prüfen.

---

## Schritt 3: Entity-IDs in Home Assistant ermitteln

Für jedes Gerät werden vier Sensor-Entities benötigt (Power, Voltage, Current, Energy).

1. In HA: **Entwicklerwerkzeuge** → **Zustände**
2. Nach dem Gerätenamen filtern (z.B. "waschmaschine" oder "shellypmminig3")
3. Die Entity-IDs notieren:

| Messgröße | Beispiel Entity-ID |
|-----------|-------------------|
| Leistung  | `sensor.shellypmminig3_84fce639a9e8_waschmaschine_power` |
| Spannung  | `sensor.shellypmminig3_84fce639a9e8_waschmaschine_voltage` |
| Strom     | `sensor.shellypmminig3_84fce639a9e8_waschmaschine_current` |
| Energie   | `sensor.shellypmminig3_84fce639a9e8_waschmaschine_energy` |

---

## Schritt 4: Add-On konfigurieren

1. In HA: **Einstellungen** → **Add-Ons** → **FEMS Shelly Proxy**
2. Tab **Konfiguration**
3. Geräte eintragen:

```yaml
devices:
  - name: Waschmaschine
    ip: "192.168.178.10"
    entity_power: sensor.shellypmminig3_84fce639a9e8_waschmaschine_power
    entity_voltage: sensor.shellypmminig3_84fce639a9e8_waschmaschine_voltage
    entity_current: sensor.shellypmminig3_84fce639a9e8_waschmaschine_current
    entity_energy: sensor.shellypmminig3_84fce639a9e8_waschmaschine_energy
  - name: Trockner
    ip: "192.168.178.11"
    entity_power: sensor.shellypmminig3_5432045520d8_trockner_power
    entity_voltage: sensor.shellypmminig3_5432045520d8_trockner_voltage
    entity_current: sensor.shellypmminig3_5432045520d8_trockner_current
    entity_energy: sensor.shellypmminig3_5432045520d8_trockner_energy
```

**Wichtig bei der IP-Vergabe:**
- Jedes Gerät bekommt eine eigene, feste IP-Adresse
- Die IPs dürfen **nicht** im DHCP-Bereich des Routers liegen
- Die IPs dürfen **nicht** bereits von anderen Geräten belegt sein
- Empfohlen: zusammenhängender Bereich wie 192.168.178.10–20

4. **Speichern** klicken

---

## Schritt 5: DHCP-Bereich im Router prüfen

Damit sich die virtuellen IPs nicht mit per DHCP vergebenen Adressen überschneiden:

1. Router-Oberfläche öffnen (z.B. http://fritz.box)
2. **Heimnetz** → **Netzwerk** → **Netzwerkeinstellungen**
3. Sicherstellen, dass der gewählte IP-Bereich (z.B. .10–.20) **nicht** im DHCP-Pool liegt

Bei der Fritz!Box ist der DHCP-Bereich typisch ab .20 oder .100. Falls nötig, anpassen.

---

## Schritt 6: Add-On starten

1. Zurück zum Add-On → Tab **Info**
2. **Starten** klicken
3. Tab **Protokoll** prüfen – erwartete Ausgabe:

```
[INFO] Netzwerk-Interface: eth0 (Prefix: /24)
[INFO] Füge IP 192.168.178.10/24 auf eth0 hinzu
[INFO] Füge IP 192.168.178.11/24 auf eth0 hinzu
[INFO] Starte Shelly-FEMS-Proxy...
[INFO] ✓ Virtueller Shelly 'Waschmaschine' auf 192.168.178.10:80 gestartet
[INFO] ✓ Virtueller Shelly 'Trockner' auf 192.168.178.11:80 gestartet
[INFO] Alle 2 virtuellen Shelly-Geräte aktiv. Warte auf FEMS-Anfragen…
```

4. Optional: **Beim Start ausführen** aktivieren, damit das Add-On bei jedem HA-Neustart automatisch startet

---

## Schritt 7: Funktion testen

Von einem Rechner im selben Netzwerk:

```bash
# Device-Info abfragen (sollte PlugSG3 melden)
curl http://192.168.178.10/shelly

# Messdaten abfragen
curl http://192.168.178.10/rpc/Shelly.GetStatus
```

Erwartete Antwort bei `/shelly`:
```json
{"name": "Waschmaschine", "app": "PlugSG3", "gen": 3, ...}
```

---

## Schritt 8: In FEMS einbinden

1. FEMS-Oberfläche öffnen
2. **App Center** → **Shelly DIY** installieren (falls nicht vorhanden)
3. Neue Shelly-Komponente hinzufügen:
   - **IP-Adresse:** `192.168.178.10` (ohne Port!)
   - **Typ:** je nach Gerät: Verbrauchszähler oder Erzeugungszähler
4. FEMS sollte das Gerät als **Shelly Plug S Gen3** erkennen
5. Für jedes weitere Gerät wiederholen (nächste IP)

---

## Troubleshooting

| Problem | Ursache | Lösung |
|---------|---------|--------|
| Add-On erscheint nicht im Store | Dateien fehlen oder config.yaml fehlerhaft | SSH: Dateien in `/addons/fems-shelly-proxy/` prüfen, HA neu starten |
| Add-On startet nicht | Log im Tab "Protokoll" prüfen | Häufig: fehlende Entity-IDs oder ungültige IP-Adressen |
| "Kein aktives Netzwerk-Interface" | Interface-Erkennung fehlgeschlagen | Im Log prüfen welches Interface verfügbar ist |
| IP-Alias kann nicht hinzugefügt werden | IP bereits vergeben oder Berechtigungen fehlen | Prüfen ob IP frei ist; Add-On braucht NET_ADMIN |
| curl liefert keine Antwort | IP-Alias nicht aktiv oder Proxy nicht gestartet | Add-On Log prüfen; `ping 192.168.178.10` vom LAN testen |
| FEMS zeigt "Gerät stimmt nicht überein" | FEMS erwartet bestimmte Felder | Add-On aktualisieren (available_updates etc.) |
| Keine Messwerte (alles 0) | HA-Entity-IDs falsch oder Sensor "unavailable" | Entity-IDs in HA Entwicklerwerkzeuge prüfen |
| Werte in FEMS veraltet | Polling-Latenz HA + FEMS | Normal: bis ~40s Verzögerung (HA ~30s + FEMS ~10s) |

---

## Aktualisieren

Bei Updates die Dateien erneut nach `/addons/fems-shelly-proxy/` kopieren und im Add-On auf **Neu erstellen** klicken. Die Konfiguration bleibt erhalten.
