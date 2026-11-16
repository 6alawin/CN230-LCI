-- งาน: เพิ่มข้อมูล Location ของพื้นที่ที่โครงงานครอบคลุม
-- ในชุดข้อมูลปัจจุบันกำหนดประเทศเป็น Thailand
INSERT INTO location (country)
VALUES ('Thailand')
ON CONFLICT (country) DO NOTHING;
