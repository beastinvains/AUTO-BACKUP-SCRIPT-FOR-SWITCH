"""A small SSH server used to test network-device backup workflows."""

from __future__ import annotations

import argparse
import socket
import threading
from typing import Optional

import paramiko

from mock_data import COMMAND_OUTPUTS

HOST = "127.0.0.1"
PORT = 2222
USERNAME = "admin"
PASSWORD = "admin"
PROMPT = "Switch#"


class SwitchServer(paramiko.ServerInterface):
    """Accept one password-authenticated shell or exec SSH channel."""

    def __init__(self) -> None:
        self.ready = threading.Event()
        self.shell_requested = False
        self.exec_command: Optional[str] = None

    def check_auth_password(self, username: str, password: str) -> int:
        """Accept the configured username and password only."""
        if username == USERNAME and password == PASSWORD:
            print("User Logged In", flush=True)
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


def command_response(command: str) -> str:
    """Return a canned response for a command, or the CLI error message."""
    normalized = command.strip()
    if normalized in {"terminal width 511", "terminal length 0"}:
        return f"{normalized}\n"
    if normalized in COMMAND_OUTPUTS:
        return f"{normalized}\n{COMMAND_OUTPUTS[normalized]}"
    return f"{normalized}\n% Invalid command\n"


def serve_client(client: socket.socket, host_key: paramiko.PKey) -> None:
    """Handle a single SSH connection until its channel is closed."""
    print("Client Connected", flush=True)
    transport = paramiko.Transport(client)
    transport.add_server_key(host_key)
    server = SwitchServer()
    try:
        transport.start_server(server=server)
        channel = transport.accept(20)
        if channel is None or not server.ready.wait(10):
            return
        if server.exec_command is not None:
            print("Command Executed", flush=True)
            print(server.exec_command, flush=True)
            channel.send(command_response(server.exec_command))
            channel.send_exit_status(0)
            return

        channel.send(PROMPT)
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
                    print("Command Executed", flush=True)
                    print(command, flush=True)
                    channel.send(command_response(command))
                channel.send(PROMPT)
    except (paramiko.SSHException, OSError):
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
        print("Client Disconnected", flush=True)


def main() -> None:
    """Start the mock switch and serve connections until interrupted."""
    parser = argparse.ArgumentParser(description="Run a mock SSH switch.")
    parser.add_argument("--host", default=HOST, help=f"Host to listen on ({HOST}).")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to listen on ({PORT}).")
    args = parser.parse_args()
    host_key = paramiko.RSAKey.generate(2048)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((args.host, args.port))
        listener.listen(20)
        print(f"Mock switch listening on {args.host}:{args.port}", flush=True)
        try:
            while True:
                client, _ = listener.accept()
                threading.Thread(
                    target=serve_client, args=(client, host_key), daemon=True
                ).start()
        except KeyboardInterrupt:
            print("\nMock switch stopped", flush=True)


if __name__ == "__main__":
    main()
