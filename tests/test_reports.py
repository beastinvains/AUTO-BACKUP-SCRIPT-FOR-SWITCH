import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from reports.report_manager import ReportManager
from reports.report_models import CommandResult, DeviceReport


class ReportManagerTests(unittest.TestCase):
    def test_save_and_load_daily_report(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = ReportManager(Path(tmp_dir), datetime(2026, 7, 31, 22, 0, 0))
            device = DeviceReport(
                hostname="CORE1",
                ip="10.10.10.1",
                vendor="cisco",
                status="success",
                backup_file="CORE1/backup_2026-07-31_22-00-00.txt",
            )
            manager.add_command(
                device,
                CommandResult(
                    command="show version",
                    status="success",
                    execution_time=0.62,
                    output="Cisco IOS XE",
                ),
            )
            manager.add_device(device)
            path = manager.save()

            loaded = ReportManager.load(path)
            document = loaded.to_dict()

            self.assertTrue(path.exists())
            self.assertEqual(document["report_date"], "2026-07-31")
            self.assertEqual(document["statistics"], {
                "total_devices": 1,
                "successful": 1,
                "failed": 0,
            })
            self.assertEqual(document["devices"][0]["commands"][0]["output"], "Cisco IOS XE")

    def test_same_hostname_replaces_prior_device_report(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = ReportManager(Path(tmp_dir), datetime(2026, 7, 31, 22, 0, 0))
            manager.add_device(DeviceReport("CORE1", "10.10.10.1", "cisco", "failed"))
            manager.add_device(DeviceReport("CORE1", "10.10.10.1", "cisco", "success"))

            self.assertEqual(len(manager.report.devices), 1)
            self.assertEqual(manager.report.devices[0].status, "success")


if __name__ == "__main__":
    unittest.main()
