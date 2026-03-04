import json
import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
from types import SimpleNamespace
import sys
import os

# Add current directory to path so we can import tools
sys.path.append(os.getcwd())

import tools.query_usaspending as usaspending

class TestUSASpending(unittest.TestCase):

    def setUp(self):
        # Patch write_output to return False so it proceeds to print
        self.patcher = patch('tools.query_usaspending.write_output', return_value=False)
        self.mock_write_output = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    @patch('tools.query_usaspending.urlopen')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cmd_search(self, mock_stdout, mock_urlopen):
        # Mock API response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "results": [
                {"recipient_name": "PALANTIR TECHNOLOGIES INC.", "uei": "RN99S3S7N977", "duns": "123456789"}
            ]
        }).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        args = SimpleNamespace(query="Palantir", json_out=False, output=None)
        usaspending.cmd_search(args)

        output = mock_stdout.getvalue()
        self.assertIn("PALANTIR TECHNOLOGIES INC.", output)
        self.assertIn("RN99S3S7N977", output)

    @patch('tools.query_usaspending.urlopen')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cmd_awards(self, mock_stdout, mock_urlopen):
        # Mock API response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "results": [
                {
                    "Award ID": "W91WAW11F0017",
                    "Award Amount": 421016.04,
                    "Recipient Name": "PALANTIR TECHNOLOGIES INC.",
                    "Awarding Agency": "Department of Defense",
                    "Awarding Sub Agency": "Department of the Army",
                    "Start Date": "2011-06-30",
                    "End Date": "2012-01-04",
                    "Description": "Test description"
                }
            ]
        }).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        args = SimpleNamespace(query="Palantir", uei=None, limit=1, page=1, agency=None, grants=False, json_out=False, output=None)
        usaspending.cmd_awards(args)

        output = mock_stdout.getvalue()
        self.assertIn("W91WAW11F0017", output)
        self.assertIn("$421,016.04", output)
        self.assertIn("Department of Defense", output)

    @patch('tools.query_usaspending.urlopen')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cmd_covid(self, mock_stdout, mock_urlopen):
        # Mock API response (only one group for brevity)
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "results": [
                {
                    "Award ID": "COVID-123",
                    "Award Amount": 1000000.0,
                    "Recipient Name": "HEALTH CORP",
                    "Awarding Agency": "HHS",
                    "Description": "COVID relief"
                }
            ]
        }).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        args = SimpleNamespace(query="Health", limit=1, json_out=False, output=None)
        usaspending.cmd_covid(args)

        output = mock_stdout.getvalue()
        self.assertIn("COVID-123", output)
        self.assertIn("$1,000,000.00", output)

    @patch('tools.query_usaspending.urlopen')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cmd_loans(self, mock_stdout, mock_urlopen):
        # Mock API response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "results": [
                {
                    "Award ID": "LOAN-456",
                    "Award Amount": 50000.0,
                    "Recipient Name": "SMALL BIZ",
                    "Awarding Agency": "SBA"
                }
            ]
        }).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        args = SimpleNamespace(query="Biz", limit=1, json_out=False, output=None)
        usaspending.cmd_loans(args)

        output = mock_stdout.getvalue()
        self.assertIn("LOAN-456", output)
        self.assertIn("$50,000.00", output)

    @patch('tools.query_usaspending.urlopen')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cmd_recipient(self, mock_stdout, mock_urlopen):
        # Mock two consecutive API calls (search then spending_by_category)
        mock_resp_search = MagicMock()
        mock_resp_search.read.return_value = json.dumps({
            "results": [{"recipient_name": "PALANTIR", "uei": "RN99S3S7N977"}]
        }).encode()
        mock_resp_search.__enter__.return_value = mock_resp_search
        
        mock_resp_spending = MagicMock()
        mock_resp_spending.read.return_value = json.dumps({
            "results": [{"name": "Department of Defense", "amount": 1000000.0}]
        }).encode()
        mock_resp_spending.__enter__.return_value = mock_resp_spending
        
        mock_urlopen.side_effect = [mock_resp_search, mock_resp_spending]

        args = SimpleNamespace(query="Palantir", json_out=False, output=None)
        usaspending.cmd_recipient(args)

        output = mock_stdout.getvalue()
        self.assertIn("Recipient: PALANTIR", output)
        self.assertIn("UEI: RN99S3S7N977", output)
        self.assertIn("Department of Defense", output)
        self.assertIn("$1,000,000.00", output)

if __name__ == '__main__':
    unittest.main()
