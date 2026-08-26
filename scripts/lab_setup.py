"""Register the mock lab estate with this platform, discover it, and report what came back.

Companion to ``tests/mock_lab.py``, which serves the estate from another machine on the
LAN.  This side does only what an operator would do: point discovery at the endpoints and
let Phase 1 write inventory.  Nothing is faked — every device, interface, neighbour and
topology edge printed below came from an SSH session with the mock.

    python scripts/lab_setup.py --host 192.168.1.42

Re-running is safe: discovery upserts by management endpoint, so the same estate is
refreshed rather than duplicated.
"""

from pathlib import Path
import argparse
import socket
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlalchemy as sa

from adapters.juniper.adapter import JuniperAdapter
from core.models import DeviceType, DiscoveryTarget
from credentials import CredentialError, get_credentials
from database.models import Base
from database.session import DATABASE_URL, SessionLocal, engine
from discovery.jobs import DiscoveryService, JobStatus
from tests.lab_estate import BASE_PORT, CREDENTIALS_PROFILE, PASSWORD, UNREACHABLE_DEVICE, USERNAME, build_estate
from topology.service import TopologyService


def stale_address_unique() -> bool:
    """True if this database still requires ``management_ip`` to be unique on its own.

    A lab puts several devices on one address, so that older constraint has to be gone.
    """
    inspector = sa.inspect(engine)
    if "devices" not in inspector.get_table_names():
        return False
    constraints = [list(item.get("column_names") or []) for item in inspector.get_unique_constraints("devices")]
    constraints += [list(item.get("column_names") or []) for item in inspector.get_indexes("devices")
                    if item.get("unique")]
    return ["management_ip"] in constraints


def port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def build_targets(host: str, base_port: int, reference: str, include_unreachable: bool) -> list[DiscoveryTarget]:
    targets = [
        DiscoveryTarget(
            name=persona.hostname, management_ip=host, port=persona.port(base_port),
            credentials_reference_id=reference, type=DeviceType(persona.device_type),
            vendor="juniper", site=persona.site,
        )
        for persona in build_estate()
    ]
    if include_unreachable:
        # Nothing listens here on purpose: the platform must show a FAILED result and a
        # PARTIAL job rather than pretending the estate is complete.
        targets.append(DiscoveryTarget(
            name=UNREACHABLE_DEVICE["hostname"], management_ip=host,
            port=base_port + int(UNREACHABLE_DEVICE["port_offset"]),
            credentials_reference_id=reference, type=DeviceType(UNREACHABLE_DEVICE["device_type"]),
            vendor="juniper", site=UNREACHABLE_DEVICE["site"],
        ))
    return targets


def check_credentials(reference: str) -> None:
    try:
        get_credentials(reference)
    except CredentialError:
        variable = reference.upper()
        raise SystemExit(
            f"No credentials for profile '{reference}'.\n"
            f"The lab's devices accept one fixed development login, so set it for this shell:\n"
            f"  export {variable}_USERNAME={USERNAME}\n"
            f"  export {variable}_PASSWORD={PASSWORD}\n"
            f"(or add those two lines to .env). Never reuse this profile for real devices."
        ) from None


def main() -> None:
    parser = argparse.ArgumentParser(description="Register and discover the mock lab estate.")
    parser.add_argument("--host", required=True, help="Address of the machine running tests/mock_lab.py.")
    parser.add_argument("--base-port", type=int, default=BASE_PORT,
                        help=f"Base port the lab was started with (default {BASE_PORT}).")
    parser.add_argument("--credentials-reference", default=CREDENTIALS_PROFILE,
                        help=f"Credential profile name to store on each device (default {CREDENTIALS_PROFILE}).")
    parser.add_argument("--with-unreachable", action="store_true",
                        help="Also register a device nothing answers on, to exercise failure handling.")
    parser.add_argument("--skip-discovery", action="store_true",
                        help="Only check the environment and print the plan.")
    args = parser.parse_args()

    if stale_address_unique():
        raise SystemExit(
            f"{DATABASE_URL} still has a single-column unique constraint on devices.management_ip,\n"
            "so it cannot hold several devices on one address. Bring the schema up to date:\n"
            "  alembic upgrade head\n"
            "(or delete the development database and let it be recreated)."
        )
    check_credentials(args.credentials_reference)
    Base.metadata.create_all(engine)  # Local convenience; deployed environments use Alembic.

    targets = build_targets(args.host, args.base_port, args.credentials_reference, args.with_unreachable)
    estate_ports = [persona.port(args.base_port) for persona in build_estate()]
    print(f"Lab host {args.host}, ports {min(estate_ports)}-{max(estate_ports)}, "
          f"credential profile '{args.credentials_reference}'")
    closed = [target for target in targets if not port_open(args.host, target.port)]
    for target in targets:
        state = "closed" if target in closed else "open"
        print(f"  {target.name:<22} port {target.port:>5}  {state}")
    if len(closed) == len(targets):
        raise SystemExit(f"\nNothing is listening on {args.host}. Start the lab there first:\n"
                         f"  python tests/mock_lab.py --host 0.0.0.0 --base-port {args.base_port}")
    if closed and not args.with_unreachable:
        print(f"\nWarning: {len(closed)} port(s) closed; those devices will be recorded as FAILED.")
    if args.skip_discovery:
        return

    print("\nDiscovering...")
    job = DiscoveryService(JuniperAdapter(), SessionLocal).run(targets)
    for result in job.results:
        detail = result.error or result.device_id
        print(f"  {result.status.value:<8} {result.target:<22} {detail}")
    succeeded = sum(result.status == JobStatus.SUCCESS for result in job.results)
    print(f"Discovery job {job.status.value}: {succeeded}/{len(job.results)} devices")

    stats = TopologyService(SessionLocal).graph()["stats"]
    print("\nTopology built from the LLDP evidence just collected:")
    for key in ("device_count", "external_count", "edge_count", "corroborated_edges",
                "unresolved_neighbors", "insufficient_evidence"):
        print(f"  {key:<22} {stats[key]}")
    ambiguous = stats["ambiguous_identities"]
    print(f"  {'ambiguous_identities':<22} {', '.join(ambiguous) if ambiguous else 'none'}")
    if ambiguous:
        print("  (a neighbour reported one of those names and two devices answer to it, so the"
              " link was refused rather than guessed)")

    print("\nNext:\n"
          "  uvicorn backend.app:app --reload            # API on 127.0.0.1:8000\n"
          "  cd frontend && npm run dev                  # UI on 127.0.0.1:5173\n"
          "Then open Topology, run a backup, use 'drift <device>' in the lab console, and back"
          " up again to see the diff.")


if __name__ == "__main__":
    main()
