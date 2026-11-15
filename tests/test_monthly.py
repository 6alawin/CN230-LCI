import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from app.monthly import emission_report, emission_scope, monthly_report, monthly_scope

class MonthlyTests(unittest.TestCase):
    def test_scope(self):
        base = "จำนวนการใช้ถ่านหินในการผลิตไฟฟ้าปี 2025 "
        for suffix, expected in [("ทุกเดือน", (list(range(1,13)), ["COAL"], [])), ("กุมภาพันธ์ SPP", ([2], ["COAL"], ["SPP"])), ("รายเดือน กฟผ ลิกไนต์", (list(range(1,13)), ["COAL","LIGNITE"], ["EGAT"]))]:
            with self.subTest(suffix=suffix):
                self.assertEqual(monthly_scope(base + suffix, [2025]), expected)

    def test_other_questions(self):
        for query, years in [("การปล่อย CO2 จากการใช้ถ่านหินผลิตไฟฟ้าทุกเดือน", [2025]), ("การผลิตไฟฟ้าจากถ่านหินรายเดือน", [2025]), ("การใช้ถ่านหินผลิตไฟฟ้าทุกเดือน", [])]:
            with self.subTest(query=query):
                self.assertIsNone(monthly_scope(query, years))

    def test_emission_questions(self):
        examples = [
            ("จำนวนคาร์บอนที่ถูกผลิตจากการใช้น้ำมันในปี 2026 รวมทุกเดือนแยกรายสาขา", ["CO2 - OIL"], []),
            ("การปล่อย CO2 จากน้ำมันปี 2026 รายเดือน ภาคขนส่ง", ["CO2 - OIL"], ["TRANSPORT"]),
            ("CO₂ จากถ่านหินในภาคอุตสาหกรรมปี 2025 ทุกเดือน", ["CO2 - COAL / LIGNITE"], ["INDUSTRY"]),
            ("การปล่อยคาร์บอนจากก๊าซธรรมชาติในภาคผลิตไฟฟ้าปี 2568 ทั้งปี", ["CO2 - NATURAL GAS"], ["ELECTRICITY GENERATION"]),
        ]
        for query, fuels, sectors in examples:
            with self.subTest(query=query):
                scope = emission_scope(query, [2025])
                self.assertEqual(scope, (list(range(1, 13)), fuels, sectors))

    def test_unscoped_emissions(self):
        for query in ("การปล่อย CO2 ปี 2026 รายเดือน", "การใช้น้ำมันผลิตไฟฟ้าปี 2026 ทุกเดือน"):
            with self.subTest(query=query):
                self.assertIsNone(emission_scope(query, [2026]))

    @patch('app.monthly.psycopg.connect')
    def test_emission_report_partial_year_and_source_filter(self, connect):
        connection = connect.return_value.__enter__.return_value
        connection.execute.return_value.fetchall.return_value = [
            (1, 'SRC-18', 'OTHER ECONOMIC SECTORS', 'CO2 - OIL', Decimal('2.50'), 'Thousand Tons-CO2', 101),
            (2, 'SRC-20', 'TRANSPORT', 'CO2 - OIL', Decimal('3.25'), 'Thousand Tons-CO2', 102),
        ]
        request = SimpleNamespace(query='การปล่อย CO2 จากน้ำมันปี 2026 ทุกเดือน', limit=1, source_code=None)
        settings = SimpleNamespace(database_url='test', cloud_snapshot_schema='snapshot')
        result = emission_report(request, settings, 2026, (list(range(1, 13)), ['CO2 - OIL'], []))
        self.assertEqual(result['total_records'], 2)
        self.assertEqual(len(result['results']), 1)
        self.assertIn('2/12 เดือน', result['answer'])
        self.assertIn('2.5 Thousand Tons-CO2 (เฉพาะ 1 เดือน', result['answer'])
        self.assertIn('3.25 Thousand Tons-CO2 (เฉพาะ 1 เดือน', result['answer'])
        self.assertIn('ยังไม่สรุปยอดทั้งปี', result['answer'])
        self.assertIn('ไม่มีรายการตามเงื่อนไข', result['answer'])
        self.assertEqual(connection.execute.call_args.args[1][3:5], (None, None))

    @patch('app.monthly.psycopg.connect')
    def test_previous_monthly_fuel_answer(self, connect):
        connection = connect.return_value.__enter__.return_value
        connection.execute.return_value.fetchall.return_value = [
            (2, 'SRC-15', 'ELECTRICITY (SPP)', 'COAL', Decimal('25.323'), '1,000 Tons', 36074),
        ]
        request = SimpleNamespace(query='การใช้ถ่านหินผลิตไฟฟ้าปี 2025 กุมภาพันธ์', limit=10, source_code='SRC-15')
        settings = SimpleNamespace(database_url='test', cloud_snapshot_schema='snapshot')
        result = monthly_report(request, settings, 2025, ([2], ['COAL'], ['SPP']))
        self.assertEqual(result['total_records'], 1)
        self.assertIn('กุมภาพันธ์ · SPP COAL 25.323', result['answer'])
        self.assertEqual(connection.execute.call_args.args[1][3:5], ('SRC-15', 'SRC-15'))
