import unittest
from app.monthly import monthly_scope

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
