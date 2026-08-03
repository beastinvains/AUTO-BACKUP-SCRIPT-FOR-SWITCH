import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from backup import backup_device
from config import AppConfig
from devices import Device
from reports.report_manager import ReportManager


class BackupReportingIntegrationTests(unittest.TestCase):
    @patch("backup.get_credentials", return_value={"username": "backup", "password": "secret"})
    @patch("backup.ConnectHandler")
    def test_selected_commands_are_written_to_one_daily_report(self, connect_handler, _credentials):
        connection = MagicMock()
        connection.send_command.side_effect = lambda command, **_kwargs: f"output for {command}"
        connect_handler.return_value = connection

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config = AppConfig(
                backup_root=root,
                devices_file=root / "devices.csv",
                env_file=root / ".env",
                log_file=root / "backup.log",
                max_workers=1,
                report_commands={"cisco": ["show version", "show environment"]},
            )
            report_manager = ReportManager(root, datetime.now())
            device = Device("CORE1", "10.10.10.1", "cisco", "network")

            result = backup_device(device, config, MagicMock(), report_manager)
            report_path = report_manager.save()
            document = ReportManager.load(report_path).to_dict()

            self.assertEqual(result["status"], "success")
            self.assertEqual(connection.send_command.call_count, 5)
            self.assertEqual(
                [item["command"] for item in document["devices"][0]["commands"]],
                ["show version", "show environment"],
            )
            self.assertEqual(document["statistics"]["successful"], 1)


if __name__ == "__main__":
    unittest.main()
