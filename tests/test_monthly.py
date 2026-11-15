import unittest
from app.monthly import emission_scope, monthly_scope

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
