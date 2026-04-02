# FEMS Shelly Proxy

This add-on emulates **Shelly Plug S Gen3** HTTP endpoints from Home Assistant
sensor data, allowing the **FEMS Shelly DIY** app to integrate devices that are
not natively supported (e.g. Shelly PM Mini Gen3).

Each configured device gets its own virtual IP address on your LAN and responds
on port 80 — exactly like a real Shelly Plug S Gen3.

## How it works

```
Shelly PM Mini Gen3  ──WiFi──>  Home Assistant
                                     │ Supervisor API
                                     v
                              FEMS Shelly Proxy (this add-on)
                              192.168.178.10 :80  "Washer"
                              192.168.178.11 :80  "Dryer"
                                     │ HTTP (Shelly Gen3 API)
                                     v
                              FEMS Shelly DIY App
                              -> sees real "Shelly Plug S Gen3" devices
```

1. Reads sensor data (power, voltage, current, energy) from Home Assistant
2. Wraps the data in the Shelly Plug S Gen3 `switch:0` JSON format
3. Reports as `PlugSG3` (Gen 3) at `/rpc/Shelly.GetDeviceInfo`
4. FEMS device-type validation passes

## Prerequisites

- Shelly PM Mini Gen3 (or other power-monitoring devices) already
  integrated in Home Assistant
- Free static IP addresses in your LAN (outside your router's DHCP range)
- FEMS and Home Assistant must be on the same network

## Configuration

### Step 1: Find your entity IDs

In Home Assistant go to **Developer Tools** > **States** and search for your
device. You need four entity IDs per device:

| Measurement | Example entity ID |
|-------------|-------------------|
| Power       | `sensor.shellypmminig3_XXXX_power` |
| Voltage     | `sensor.shellypmminig3_XXXX_voltage` |
| Current     | `sensor.shellypmminig3_XXXX_current` |
| Energy      | `sensor.shellypmminig3_XXXX_energy` |

### Step 2: Choose IP addresses

Each virtual Shelly device needs its own IP address. These must be:

- In the same subnet as your Home Assistant and FEMS
- **Not** in your router's DHCP range
- **Not** already used by other devices

Example: `192.168.178.10`, `192.168.178.11`, `192.168.178.12`

**Fritz!Box users:** Check *Home Network* > *Network* > *Network Settings* to
see and adjust the DHCP range.

### Step 3: Configure devices

In the add-on **Configuration** tab, add your devices:

```yaml
devices:
  - name: Washer
    ip: "192.168.178.10"
    entity_power: sensor.shellypmminig3_XXXX_power
    entity_voltage: sensor.shellypmminig3_XXXX_voltage
    entity_current: sensor.shellypmminig3_XXXX_current
    entity_energy: sensor.shellypmminig3_XXXX_energy
  - name: Dryer
    ip: "192.168.178.11"
    entity_power: sensor.shellypmminig3_YYYY_power
    entity_voltage: sensor.shellypmminig3_YYYY_voltage
    entity_current: sensor.shellypmminig3_YYYY_current
    entity_energy: sensor.shellypmminig3_YYYY_energy
```

Click **Save** after entering your devices.

### Step 4: Start the add-on

Start the add-on and check the **Log** tab. You should see:

```
[INFO] Network interface: end0 (Prefix: /24)
[INFO] Adding IP 192.168.178.10/24 on end0
[INFO] Starting Shelly-FEMS-Proxy...
[INFO] Virtual Shelly 'Washer' on 192.168.178.10:80 started
```

Enable **Start on boot** to auto-start the add-on after Home Assistant restarts.

### Step 5: Test from your network

From any computer on the same LAN:

```bash
# Should return Shelly Plug S Gen3 device info
curl http://192.168.178.10/shelly

# Should return power/voltage/current measurements
curl http://192.168.178.10/rpc/Shelly.GetStatus
```

### Step 6: Add to FEMS

1. Open your FEMS UI
2. Go to **App Center** > install **Shelly DIY** (if not already installed)
3. Add a new Shelly component:
   - **IP address:** `192.168.178.10` (no port needed!)
   - **Type:** consumption meter or production meter (depending on your device)
4. FEMS should detect the device as a **Shelly Plug S Gen3**
5. Repeat for each additional device

## Supported devices

This proxy works with **any Home Assistant sensor** that provides power and
energy data. Tested with:

- Shelly PM Mini Gen3
- Any HA sensor with power/energy entities (e.g. solar inverters)

## Limitations

- **No switching:** The PM Mini Gen3 has no relay. `Switch.Set` commands from
  FEMS are accepted but ignored.
- **Energy precision:** Energy values are taken directly from HA (kWh to Wh
  conversion). The `by_minute` values are approximations.
- **Polling latency:** FEMS polls every ~10s, HA updates every ~30s, resulting
  in up to ~40s delay.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Add-on won't start | Check the Log tab for errors. Verify entity IDs exist in HA. |
| "No active network interface" | The add-on cannot detect the host network interface. Check your HAOS network config. |
| IP alias cannot be added | Verify the IP is not already in use. The add-on requires NET_ADMIN privilege. |
| curl returns no response | Check if the IP alias is active (add-on log). Try `ping <IP>` from your LAN. |
| FEMS shows "device mismatch" | Make sure the add-on is up to date. |
| All values are 0 | Entity IDs are wrong or the sensor is "unavailable" in HA. Check Developer Tools > States. |
| Stale values in FEMS | Normal: up to ~40s delay (HA ~30s polling + FEMS ~10s polling). |

## Network details

The add-on runs in **host network mode** and adds secondary IP addresses
(aliases) to the active network interface. Each virtual Shelly device binds to
its own IP on port 80. When the add-on stops, all IP aliases are automatically
removed.

This requires the `NET_ADMIN` Linux capability, which is granted through the
add-on configuration.
