import unittest
from app.cloud_search import requested_years

class RequestedYearsTest(unittest.TestCase):
    def test_gregorian_and_thai_digits(self):
        self.assertEqual(requested_years('การผลิตไฟฟ้าจากถ่านหินในปี 2026'), [2026])
        self.assertEqual(requested_years('ข้อมูลปี ๒๐๒๖'), [2026])

    def test_buddhist_year_and_range(self):
        self.assertEqual(requested_years('ข้อมูล พ.ศ. 2569'), [2026])
        self.assertEqual(requested_years('ข้อมูล 2024 ถึง 2026'), [2024,2025,2026])
        self.assertEqual(requested_years('ข้อมูลปี 2567-2569'), [2024,2025,2026])

    def test_no_invented_year(self):
        self.assertEqual(requested_years('การผลิตไฟฟ้า'), [])
        self.assertEqual(requested_years('ปริมาณ 2500 ลิตร'), [])
        self.assertEqual(requested_years('ราคา 2026.50 บาท'), [])

if __name__ == '__main__': unittest.main()
