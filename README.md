# FEMS Shelly Proxy — Home Assistant Add-On

Emulates **Shelly Plug S Gen3** HTTP endpoints from Home Assistant sensor data,
so **FEMS Shelly DIY** can integrate devices that are not natively supported
(e.g. Shelly PM Mini Gen3, solar inverters, or any HA power sensor).

Each virtual device gets its own IP address on your LAN and responds on port 80
— FEMS sees a real Shelly Plug S Gen3.

## Quick Install

1. In Home Assistant go to **Settings** > **Add-ons** > **Add-on Store**
2. Click **⋮** (top right) > **Repositories**
3. Add this URL:
   ```
   https://github.com/frankhirsch/ha-addon-fems-shelly-proxy
   ```
4. Install **FEMS Shelly Proxy** from the store
5. Configure your devices in the **Configuration** tab
6. Start the add-on

Full documentation is available in the add-on's **Documentation** tab after installation.

## How it works

```
Shelly PM Mini Gen3  ──WiFi──>  Home Assistant
                                     │ Supervisor API
                                     v
                              FEMS Shelly Proxy
                              192.168.178.10 :80  "Washer"
                              192.168.178.11 :80  "Dryer"
                                     │ HTTP (Shelly Gen3 API)
                                     v
                              FEMS Shelly DIY App
```

The proxy reads sensor data from HA and wraps it in the Shelly Plug S Gen3
JSON format. FEMS device-type validation passes because the proxy reports the
correct model, app name (`PlugSG3`), and generation (3).

## Supported devices

Works with any HA entity that provides power/energy data:

- Shelly PM Mini Gen3
- Shelly Plus PM Mini
- Shelly 1PM (Gen2)
- Shelly EM
- Solar inverters, smart plugs, or any other HA power sensor

## Standalone usage

You can also run the proxy without Home Assistant's add-on system:

```bash
pip install aiohttp
cp config.example.json config.json
# Edit config.json with your HA URL, token, and device entities
python3 shelly_proxy.py
```

See [config.example.json](config.example.json) for the standalone configuration format.

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

---

**Deutsche Anleitung:** Siehe [INSTALL.md](INSTALL.md) für eine deutschsprachige Installationsanleitung.
