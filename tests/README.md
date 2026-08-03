# Mock SSH Switch

This is a lightweight Paramiko SSH server for exercising the backup workflow
without a real network device. It is not a Cisco IOS emulator.

## Run it

Paramiko is installed as a dependency of Netmiko. If it is not already
available in your environment, install it with `pip install paramiko`.

From the repository root, run:

```bash
python tests/mock_switch.py
pkill -f "mock_switch.py"
```

The server listens on `127.0.0.1:2222` and accepts:

- Username: `admin`
- Password: `admin`

Change the `HOST`, `PORT`, `USERNAME`, and `PASSWORD` constants in
`tests/mock_switch.py` if needed. The host and port can also be overridden for
a run with `--host` and `--port`.

Point your device inventory at the mock switch, for example:

```csv
hostname,ip,vendor
TEST-SWITCH,127.0.0.1,cisco
```

Configure the backup application to use SSH port `2222`, username `admin`,
and password `admin`. Its backup engine does not need any changes.

The server recognizes the command responses in `mock_data.py`, including
`show version`, `show inventory`, `show environment`, and
`show running-config`. Any other command returns `% Invalid command`.
