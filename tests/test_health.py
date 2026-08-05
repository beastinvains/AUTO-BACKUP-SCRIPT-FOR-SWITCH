import unittest

from reports.health import parse_power_supplies


class HealthParserTests(unittest.TestCase):
    def test_parse_juniper_power_supply_lines(self):
        text = """
        FPC 0 Power Supply 0    OK
        FPC 0 Power Supply 1    Present
        """

        result = parse_power_supplies(text)

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["ok"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["warning"], 1)
        self.assertEqual(
            result["items"],
            [
                {"name": "Power Supply 0", "status": "OK"},
                {"name": "Power Supply 1", "status": "Present"},
            ],
        )

    def test_parse_cisco_power_supply_line(self):
        text = "Switch 1: POWER SUPPLY 1 is OK"

        result = parse_power_supplies(text)

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["ok"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["warning"], 0)
        self.assertEqual(result["items"], [{"name": "Power Supply 1", "status": "OK"}])

    def test_parse_duplicate_power_supply_entries(self):
        text = """
        FPC 0 Power Supply 0    OK
        FPC 0 Power Supply 0    Present
        """

        result = parse_power_supplies(text)

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["ok"], 0)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["warning"], 1)
        self.assertEqual(result["items"], [{"name": "Power Supply 0", "status": "Present"}])

    def test_parse_absent_power_supply_is_warning(self):
        text = """
        FPC 0 Power Supply 0    OK
        FPC 0 Power Supply 1    Absent
        """

        result = parse_power_supplies(text)

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["ok"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["warning"], 1)
        self.assertEqual(
            result["items"],
            [
                {"name": "Power Supply 0", "status": "OK"},
                {"name": "Power Supply 1", "status": "Absent"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
