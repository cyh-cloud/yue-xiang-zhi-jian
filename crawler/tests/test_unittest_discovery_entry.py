import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class UnittestDiscoveryEntryTest(unittest.TestCase):
    def test_documented_crawler_discovery_command_imports(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "crawler",
                "-p",
                "test_scrapy_dependency_contract.py",
                "-t",
                ".",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
