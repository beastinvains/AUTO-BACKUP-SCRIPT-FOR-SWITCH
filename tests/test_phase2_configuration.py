import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from configuration.service import configuration_diff, configuration_hash, normalize_configuration
from storage.local import LocalArtifactStorage


class ConfigurationUnitTests(unittest.TestCase):
    def test_normalization_is_stable_and_redacts_secret_values(self):
        raw = "set system root-authentication encrypted-password $6$secret\r\nset system host-name edge  \r\n"
        normalized = normalize_configuration(raw)
        self.assertIn("<redacted>", normalized)
        self.assertEqual(configuration_hash(normalized), configuration_hash(normalize_configuration(raw)))

    def test_deterministic_line_diff(self):
        result = configuration_diff("set vlans HR vlan-id 40\n", "set vlans HR vlan-id 50\n")
        self.assertEqual(result["summary"], {"added": 1, "removed": 1, "unchanged": 0})
        self.assertEqual(result["added"], ["set vlans HR vlan-id 50"])

    def test_local_store_rejects_traversal_and_replacement(self):
        with tempfile.TemporaryDirectory() as root:
            store = LocalArtifactStorage(Path(root))
            uri = store.put_configuration(device_name="../core", version_id="v1", content=b"x", collected_at=datetime.now(timezone.utc))
            self.assertEqual(store.get(uri), b"x")
            with self.assertRaises(ValueError): store.get("../../etc/passwd")
            with self.assertRaises(FileExistsError):
                store.put_configuration(device_name="core", version_id="v1", content=b"x", collected_at=datetime.now(timezone.utc))
