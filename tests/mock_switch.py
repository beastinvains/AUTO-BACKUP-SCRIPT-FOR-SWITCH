"""A small SSH server used to test network-device backup workflows.

Run directly it serves the single fixture device in :mod:`tests.mock_data` — that is the
mode ``tests/phase2_smoke_test.py`` drives, and its ``--host``/``--port`` contract has not
changed.  The response table, prompt and log label are parameters, so
:mod:`tests.mock_lab` reuses this plumbing to serve a whole estate of personas from one
host without a second SSH implementation.
"""

from __future__ import annotations

import argparse
import logging
import socket
import threading
from typing import Mapping, Optional

import paramiko

try:
    from .mock_data import COMMAND_OUTPUTS
except ImportError:  # pragma: no cover - script execution fallback
    from mock_data import COMMAND_OUTPUTS

HOST = "127.0.0.1"
PORT = 2222
USERNAME = "admin"
PASSWORD = "admin"
PROMPT = "Switch#"


def log(message: str, label: str = "") -> None:
    """Print one line of server activity, tagged when several devices share a console."""
    print(f"[{label}] {message}" if label else message, flush=True)


class SwitchServer(paramiko.ServerInterface):
    """Accept one password-authenticated shell or exec SSH channel."""

    def __init__(self, label: str = "") -> None:
        self.label = label
        self.ready = threading.Event()
        self.shell_requested = False
        self.exec_command: Optional[str] = None

    def check_auth_password(self, username: str, password: str) -> int:
        """Accept the configured username and password only."""
        if username == USERNAME and password == PASSWORD:
            log("User Logged In", self.label)
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username: str) -> str:
        """Advertise password authentication."""
        return "password"

    def check_channel_request(self, kind: str, channel_id: int) -> int:
        """Allow session channels, which are used for shells and commands."""
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_pty_request(self, *args: object) -> bool:
        """Accept a PTY request from SSH libraries such as Netmiko."""
        return True

    def check_channel_shell_request(self, channel: paramiko.Channel) -> bool:
        """Mark the channel as an interactive shell."""
        self.shell_requested = True
        self.ready.set()
        return True

    def check_channel_exec_request(
        self, channel: paramiko.Channel, command: bytes
    ) -> bool:
        """Mark the channel as a single command execution request."""
        self.exec_command = command.decode("utf-8", errors="replace").strip()
        self.ready.set()
        return True


def _normalize_command(command: str) -> str:
    """Canonicalize commands so the mock remains stable across CLI variants."""
    normalized = command.strip().lower()
    normalized = normalized.replace("\r", "")
    normalized = normalized.replace("| no-more", "")
    normalized = normalized.strip()
    return normalized


def command_response(command: str, outputs: Mapping[str, str] = COMMAND_OUTPUTS) -> str:
    """Return a canned response for a command, or the CLI error message.

    Netmiko expects the exact command text to be echoed back before the device
    output. We keep the real command string for that echo while supporting the
    canonical Junos command keys used by the tests and adapter.
    """
    normalized = command.strip()
    if normalized in {"terminal width 511", "terminal length 0"}:
        return f"{normalized}\n"
    if normalized in outputs:
        return f"{normalized}\n{outputs[normalized]}"
    canonical = _normalize_command(normalized)
    if canonical in outputs:
        return f"{normalized}\n{outputs[canonical]}"
    return f"{normalized}\n% Invalid command\n"


def serve_client(
    client: socket.socket,
    host_key: paramiko.PKey,
    *,
    outputs: Mapping[str, str] = COMMAND_OUTPUTS,
    prompt: str = PROMPT,
    label: str = "",
) -> None:
    """Handle a single SSH connection until its channel is closed."""
    log("Client Connected", label)
    transport = paramiko.Transport(client)
    transport.add_server_key(host_key)
    server = SwitchServer(label)
    try:
        transport.start_server(server=server)
        channel = transport.accept(20)
        if channel is None or not server.ready.wait(10):
            return
        if server.exec_command is not None:
            log("Command Executed", label)
            log(server.exec_command, label)
            channel.send(command_response(server.exec_command, outputs))
            channel.send_exit_status(0)
            return

        channel.send(prompt)
        buffer = ""
        while transport.is_active() and not channel.closed:
            data = channel.recv(1024)
            if not data:
                break
            buffer += data.decode("utf-8", errors="replace")
            while "\n" in buffer or "\r" in buffer:
                parts = buffer.replace("\r", "\n").split("\n", 1)
                command, buffer = parts[0].strip(), parts[1]
                if command:
                    log("Command Executed", label)
                    log(command, label)
                    channel.send(command_response(command, outputs))
                channel.send(prompt)
    except (paramiko.SSHException, OSError, EOFError):
        # EOFError is the normal end of a netmiko session: the client sends "exit" and drops
        # the connection while the server is still writing the next prompt.
        pass
    finally:
        channel = locals().get("channel")
        if channel is not None:
            try:
                channel.close()
            except (EOFError, OSError):
                pass
        try:
            transport.close()
        except (EOFError, OSError):
            pass
        try:
            client.close()
        except OSError:
            pass
        log("Client Disconnected", label)


def open_listener(host: str, port: int, backlog: int = 20) -> socket.socket:
    """Bind and listen. The caller owns the socket, and closing it stops ``accept_forever``."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind((host, port))
        listener.listen(backlog)
    except OSError:
        listener.close()
        raise
    return listener


def accept_forever(
    listener: socket.socket,
    host_key: paramiko.PKey,
    *,
    outputs: Mapping[str, str] = COMMAND_OUTPUTS,
    prompt: str = PROMPT,
    label: str = "",
) -> None:
    """Serve every connection on ``listener`` until it is closed.

    Closing the listener from another thread is the supported way to stop this loop; that
    is how the lab console takes a device out of service.
    """
    while True:
        try:
            client, _ = listener.accept()
        except OSError:  # listener closed, or the OS refused the connection
            return
        threading.Thread(
            target=serve_client, args=(client, host_key),
            kwargs={"outputs": outputs, "prompt": prompt, "label": label},
            daemon=True,
        ).start()


def quiet_paramiko_logging() -> None:
    """Keep paramiko's transport errors out of the console.

    A TCP reachability probe — like the one ``scripts/lab_setup.py`` runs — connects and
    closes without an SSH banner, and paramiko reports that as an error with a traceback.
    It looks like a failure and is not one, so it is silenced; the mock prints its own
    connection and command lines.
    """
    logger = logging.getLogger("paramiko")
    logger.setLevel(logging.CRITICAL)
    logger.addHandler(logging.NullHandler())


def main() -> None:
    """Start the mock switch and serve connections until interrupted."""
    parser = argparse.ArgumentParser(description="Run a mock SSH switch.")
    parser.add_argument("--host", default=HOST, help=f"Host to listen on ({HOST}).")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to listen on ({PORT}).")
    args = parser.parse_args()
    quiet_paramiko_logging()
    host_key = paramiko.RSAKey.generate(2048)

    with open_listener(args.host, args.port) as listener:
        print(f"Mock switch listening on {args.host}:{args.port}", flush=True)
        try:
            accept_forever(listener, host_key)
        except KeyboardInterrupt:
            print("\nMock switch stopped", flush=True)


if __name__ == "__main__":
    main()
