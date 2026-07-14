import os


def _default_backup_root() -> str:
    if os.name == "nt":
        return r"C:\Users\Backup\OneDrive\NetworkBackups"
    return os.path.expanduser("~/NetworkBackups")


BACKUP_ROOT = os.environ.get("BACKUP_ROOT", _default_backup_root())

# Example override:
# BACKUP_ROOT = "/home/backup/NetworkBackups"