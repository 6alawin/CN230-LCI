import unittest
from unittest.mock import patch
from app.flow import read_flow
from app.main import app
from fastapi.testclient import TestClient


class FlowTests(unittest.TestCase):
    @patch('app.flow.psycopg.connect')
    def test_separates_uses_products_and_emissions(self, connect):
        connection = connect.return_value.__enter__.return_value
        connection.execute.return_value.fetchall.side_effect = [
            [(2026, 7)],
            [(1, 'SRC-11', 'NGV', 'DOMESTIC_USE', 'Natural gas', 'NATURAL_GAS', 'IN', '73', 'MMSCFD'),
             (2, 'SRC-12', 'EXPORT', 'EXPORT', 'NGL', 'NATURAL_GAS', 'OUT', '12', 'BBL/DAY'),
             (3, 'SRC-21', 'ELECTRICITY GENERATION', 'EMISSION', 'CO2 - NATURAL GAS', 'EMISSION', 'OUT', '90', 'Thousand Tons-CO2')]]
        result = read_flow('test', 'verified', 'gas')
        self.assertEqual((result['year'], result['month']), (2026, 7))
        self.assertEqual(result['uses'][0]['unit'], 'MMSCFD')
        self.assertEqual(result['outputs'][0]['process_type'], 'EXPORT')
        self.assertEqual(result['emissions'][0]['source_code'], 'SRC-21')
        self.assertEqual([len(result[k]) for k in ('uses','outputs','emissions')], [1,1,1])

    @patch('app.flow.psycopg.connect')
    def test_missing_month_does_not_invent_records(self, connect):
        connect.return_value.__enter__.return_value.execute.return_value.fetchall.side_effect = [[(2026,7)], []]
        result=read_flow('test','verified','coal',2099,1)
        self.assertEqual(result['uses'],[])
        self.assertEqual(result['outputs'],[])
        self.assertEqual(result['emissions'],[])

    @patch('app.main.get_settings')
    def test_invalid_fuel_and_period_rejected(self, settings):
        client=TestClient(app)
        for query in ('fuel=invalid', 'fuel=coal&month=13&year=2026', 'fuel=coal&year=2026'):
            with self.subTest(query=query):
                self.assertEqual(client.get('/api/flow?'+query).status_code,400)
