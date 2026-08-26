"""Run the whole mock estate on one machine, one SSH port per device.

Point it at a spare laptop or Raspberry Pi on the same LAN as the platform and the entire
feature set becomes exercisable without touching real hardware: discovery, inventory,
backups, versioning and diffs, schedules, and the topology map — which needs several
devices reporting each other over LLDP and so cannot be demonstrated with a single mock.

    python tests/mock_lab.py --host 0.0.0.0

Then, on the machine running the platform::

    python scripts/lab_setup.py --host <ip-of-the-lab-machine>

Only paramiko is required here, so the lab machine does not need the platform installed::

    pip install paramiko

While it runs, a console lets the estate misbehave on purpose:

    list            what is running, on which port, and how many changes it has taken
    drift <name>    change that device's running config, so the next backup has a real diff
    drift all       change every device
    down <name>     stop listening, so the platform records a connection failure
    up <name>       start listening again
    quit            stop the lab

Devices are ``admin``/``admin``: a development login that exists only inside this lab.
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading

import paramiko

try:  # package import when run as ``python -m tests.mock_lab``
    from .lab_estate import BASE_PORT, PASSWORD, USERNAME, build_estate
    from .mock_switch import accept_forever, open_listener, quiet_paramiko_logging
except ImportError:  # pragma: no cover - script execution fallback
    from lab_estate import BASE_PORT, PASSWORD, USERNAME, build_estate
    from mock_switch import accept_forever, open_listener, quiet_paramiko_logging


class LabDevice:
    """One persona bound to one port, which can be taken down and brought back up."""

    def __init__(self, persona, host: str, port: int, host_key: paramiko.PKey) -> None:
        self.persona = persona
        self.host = host
        self.port = port
        self.host_key = host_key
        self.listener: socket.socket | None = None
        self.thread: threading.Thread | None = None

    @property
    def name(self) -> str:
        return self.persona.hostname

    @property
    def running(self) -> bool:
        return self.listener is not None

    def start(self) -> None:
        if self.running:
            return
        self.listener = open_listener(self.host, self.port)
        self.thread = threading.Thread(
            target=accept_forever,
            args=(self.listener, self.host_key),
            kwargs={"outputs": self.persona.responses, "prompt": self.persona.prompt,
                    "label": self.persona.short_name},
            daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        """Close the listening socket, which is what ends the accept loop."""
        listener, self.listener = self.listener, None
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
        self.thread = None


def local_address() -> str:
    """Best guess at the LAN address of this machine, for the instructions printed below."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))  # no packet is sent; this only picks a route
            return probe.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())


def _match(devices: list[LabDevice], name: str) -> LabDevice | None:
    """Find a device by full hostname or by its short name, whichever the user typed."""
    wanted = name.strip().casefold()
    for device in devices:
        if wanted in {device.name.casefold(), device.persona.short_name.casefold()}:
            return device
    return None


def _print_table(devices: list[LabDevice]) -> None:
    print(f"\n{'DEVICE':<22} {'PORT':>5}  {'STATE':<5} {'MODEL':<12} {'SITE':<6} CHANGES")
    for device in devices:
        persona = device.persona
        print(f"{persona.hostname:<22} {device.port:>5}  {'up' if device.running else 'down':<5} "
              f"{persona.model:<12} {persona.site:<6} {persona.drift_applied}")
    print()


def _console(devices: list[LabDevice]) -> None:
    """Read control commands until EOF or ``quit``.

    Piped or backgrounded stdin gives EOF immediately; the lab then just keeps serving,
    which is what you want when it runs under ``nohup``.
    """
    while True:
        try:
            line = input("lab> ").strip()
        except EOFError:
            print("stdin is closed; serving without a console (Ctrl-C to stop)", flush=True)
            threading.Event().wait()  # still interruptible; the listener threads keep serving
            return
        if not line:
            continue
        command, _, argument = line.partition(" ")
        command, argument = command.casefold(), argument.strip()
        if command in {"quit", "exit"}:
            return
        if command in {"list", "ls", "status"}:
            _print_table(devices)
        elif command == "drift":
            targets = devices if argument.casefold() in {"", "all"} else [d for d in [_match(devices, argument)] if d]
            if not targets:
                print(f"unknown device: {argument}")
            for device in targets:
                print(f"{device.name}: {device.persona.apply_drift()}")
        elif command in {"down", "up"}:
            device = _match(devices, argument)
            if device is None:
                print(f"unknown device: {argument}")
            elif command == "down":
                device.stop()
                print(f"{device.name} is down (port {device.port} closed)")
            else:
                device.start()
                print(f"{device.name} is up on port {device.port}")
        else:
            print("commands: list | drift <name|all> | down <name> | up <name> | quit")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the mock device estate for lab testing.")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Address to bind (default 0.0.0.0, so the LAN can reach it).")
    parser.add_argument("--base-port", type=int, default=BASE_PORT,
                        help=f"Port of the first device; the rest follow (default {BASE_PORT}).")
    parser.add_argument("--only", default="",
                        help="Comma-separated device names to run instead of the whole estate.")
    args = parser.parse_args()

    personas = build_estate()
    if args.only:
        wanted = {name.strip().casefold() for name in args.only.split(",") if name.strip()}
        personas = [p for p in personas
                    if wanted & {p.hostname.casefold(), p.short_name.casefold()}]
        if not personas:
            parser.error(f"--only matched no devices; known: {', '.join(p.hostname for p in build_estate())}")

    print("Generating host key...", flush=True)
    quiet_paramiko_logging()
    host_key = paramiko.RSAKey.generate(2048)  # one key for the estate; this is a mock
    devices = [LabDevice(persona, args.host, persona.port(args.base_port), host_key) for persona in personas]

    started: list[LabDevice] = []
    try:
        for device in devices:
            try:
                device.start()
            except OSError as exc:
                print(f"cannot bind {device.name} to {args.host}:{device.port}: {exc}", file=sys.stderr)
                raise SystemExit(1) from exc
            started.append(device)

        address = local_address() if args.host in {"0.0.0.0", ""} else args.host
        print(f"\nMock lab running: {len(devices)} devices on {args.host}, "
              f"ports {devices[0].port}-{devices[-1].port}")
        print(f"Login: {USERNAME}/{PASSWORD}")
        _print_table(devices)
        print("Register this estate with the platform:")
        print(f"  python scripts/lab_setup.py --host {address} --base-port {args.base_port}\n")
        _console(devices)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        for device in started:
            device.stop()
        print("\nMock lab stopped", flush=True)


if __name__ == "__main__":
    main()
