from decimal import Decimal
import unittest
from unittest.mock import patch
from app.annual_flow import annualize


def row(month=1, amount='2', unit='MMSCFD', source='SRC-11', process='ELECTRICITY',
        product='Natural gas', product_type='NATURAL_GAS', kind='DOMESTIC_USE'):
    return dict(entity_id=month,source_code=source,process=process,process_type=kind,
                product=product,product_type=product_type,month=month,amount=amount,unit=unit)


def node(result, key):
    return next(n for n in result['nodes'] if n['id']==key)


class AnnualFlowTests(unittest.TestCase):
    def test_rates_use_days_and_leap_year(self):
        r=annualize([row(1), row(2)],2024,'gas')
        record=node(r,'electricity')['records'][0]
        self.assertEqual(Decimal(record['amount']),Decimal(120))
        self.assertEqual(record['unit'],'MMSCF')
        self.assertFalse(record['complete'])
        self.assertEqual(record['missing_months'],list(range(3,13)))

    def test_full_year_month_quantities_are_summed_once(self):
        rows=[row(m,'3','1,000 Tons','SRC-15','INDUSTRY','COAL','COAL') for m in range(1,13)]
        r=annualize(rows,2025,'coal');n=node(r,'industry')
        self.assertTrue(n['complete'])
        self.assertEqual(n['summaries'],[dict(amount='36000',unit='Ton')])

    def test_mixed_units_and_scopes_stay_separate(self):
        rows=[row(),row(amount='5',unit='Million Litres',source='SRC-22',process='ELECTRICITY (EGAT)',product='DIESEL',product_type='OIL'),
              row(source='SRC-22',process='ELECTRICITY (EGAT)')]
        r=annualize(rows,2025,'all')
        self.assertEqual(len(node(r,'electricity')['records']),2)
        self.assertEqual({v['unit'] for v in node(r,'electricity')['summaries']},{'MMSCF','Million Litres'})

    def test_cooking_transport_and_refining_mapping(self):
        rows=[row(source='SRC-09',process='COOKING',unit='Thousand Tons',product='LPG',product_type='OIL'),
              row(source='SRC-09',process='AUTOMOBILE',unit='Thousand Tons',product='LPG',product_type='OIL'),
              row(source='SRC-04',process='THAI OIL',kind='REFINING',unit='BBL/DAY',product='Crude oil',product_type='OIL')]
        r=annualize(rows,2025,'oil')
        for key in ('cooking','transport','refining'):
            self.assertEqual(len(node(r,key)['records']),1)
        self.assertEqual(node(r,'refining')['records'][0]['unit'],'BBL')

    def test_emissions_and_fuel_filter(self):
        rows=[row(source='SRC-21',kind='EMISSION',product='CO2 - NATURAL GAS',product_type='EMISSION',unit='Thousand Tons-CO2'),
              row(source='SRC-19',kind='EMISSION',product='CO2 - OIL',product_type='EMISSION',unit='Thousand Tons-CO2')]
        r=annualize(rows,2025,'gas')
        self.assertEqual(len(node(r,'co2')['records']),1)
        self.assertEqual(node(r,'co2')['records'][0]['product'],'CO2 - NATURAL GAS')

    def test_duplicate_month_rejected(self):
        with self.assertRaises(ValueError):annualize([row(),row()],2025,'gas')

    def test_missing_sector_stays_empty(self):
        self.assertEqual(node(annualize([],2025,'coal'),'cooking')['summaries'],[])

    @patch('app.main.get_settings')
    @patch('app.annual_flow.read_annual_flow')
    def test_annual_endpoint(self, read, settings):
        from fastapi.testclient import TestClient
        from app.main import app
        read.return_value = dict(year=2025,fuel='all',years=[2026,2025],nodes=[])
        response=TestClient(app).get('/api/annual-flow?year=2025')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['year'],2025)
        read.assert_called_once_with(settings.return_value.database_url,
                                     settings.return_value.cloud_snapshot_schema,'all',2025)
