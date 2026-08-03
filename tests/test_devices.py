import tempfile
import unittest
from pathlib import Path

from devices import load_devices


class DevicesModuleTests(unittest.TestCase):
    def test_load_devices_parses_supported_inventory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "devices.csv"
            csv_path.write_text(
                "hostname,ip,vendor,credential_profile\n"
                "SW1,10.0.0.1,cisco,hq\n",
                encoding="utf-8",
            )

            devices = load_devices(csv_path)

            self.assertEqual(len(devices), 1)
            self.assertEqual(devices[0].hostname, "SW1")
            self.assertEqual(devices[0].vendor, "cisco")
            self.assertEqual(devices[0].credential_profile, "hq")

    def test_load_devices_accepts_ip_with_port(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "devices.csv"
            csv_path.write_text(
                "hostname,ip,vendor,credential_profile\n"
                "SW2,127.0.0.1:2222,cisco,hq\n",
                encoding="utf-8",
            )

            devices = load_devices(csv_path)

            self.assertEqual(len(devices), 1)
            self.assertEqual(devices[0].ip, "127.0.0.1")
            self.assertEqual(devices[0].port, 2222)

    def test_load_devices_rejects_invalid_ip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "devices.csv"
            csv_path.write_text(
                "hostname,ip,vendor,credential_profile\n"
                "SW2,999.0.0.1,cisco,hq\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                load_devices(csv_path)


if __name__ == "__main__":
    unittest.main()
