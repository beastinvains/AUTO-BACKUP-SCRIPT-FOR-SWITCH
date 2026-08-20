"""Run a local, seed-configured, read-only Juniper discovery job."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.juniper.adapter import JuniperAdapter
from database.models import Base
from database.session import SessionLocal, engine
from discovery.jobs import DiscoveryService
from discovery.seeds import load_targets


def main() -> None:
    seed_file = Path("config/devices.yaml")
    if not seed_file.exists():
        raise SystemExit("Create config/devices.yaml from config/devices.example.yaml first.")
    Base.metadata.create_all(engine)  # Local convenience; deployed environments use Alembic.
    job = DiscoveryService(JuniperAdapter(), SessionLocal).run(load_targets(seed_file))
    print(job.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
