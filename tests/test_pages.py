import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app


class PageTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_distinct_pages_and_assets(self):
        for path, marker in (("/", "LCI — Overview"), ("/search", 'id="search-form"'),
                             ("/query", 'id="query-form"')):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(marker, response.text)
                for link in ('href="/"', 'href="/search"', 'href="/query"'):
                    self.assertIn(link, response.text)
        self.assertNotIn('id="search-form"', self.client.get('/').text)
        for path in ('/assets/dashboard.css', '/assets/overview.js'):
            self.assertEqual(self.client.get(path).status_code, 200)

    @patch('app.main.get_settings')
    @patch('app.overview.read_overview')
    def test_live_overview_payload(self, read_overview, settings):
        read_overview.return_value = dict(exchanges=42599, sources=22, first_year=1986,
                                        last_year=2026, verified=42599)
        response = self.client.get('/api/overview')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), read_overview.return_value)
        read_overview.assert_called_once_with(settings.return_value.database_url,
                                             settings.return_value.cloud_snapshot_schema)
