-- 6.3 Unit Consistency / Validated-only Counts
-- ใช้ตรวจจำนวนข้อมูลตามสถานะตรวจสอบ และจำนวนหน่วยมาตรฐาน

-- Query 1: จำนวนรายการที่นำเข้าหรือมี Error จริง (ไม่รวมแถว SKIPPED)
SELECT
    (SELECT COUNT(*) FROM lci_exchange)
    + (SELECT COUNT(*) FROM lci_import_log
       WHERE status = 'ERROR' AND resolved_at IS NULL) AS total_records;

-- Query 2: จำนวน Exchange ที่ตรวจสอบแล้ว
SELECT COUNT(*) AS verified_exchange_count
FROM lci_exchange
WHERE validation_status = 'VERIFIED';

-- Query 3: จำนวน Exchange ที่รอตรวจสอบ
SELECT COUNT(*) AS pending_exchange_count
FROM lci_exchange
WHERE validation_status = 'PENDING';

-- Query 4: จำนวน Error ทั้งหมด รวม Exchange Error และ CSV Error ที่ยังไม่แก้
SELECT
    (SELECT COUNT(*) FROM lci_exchange WHERE validation_status = 'ERROR')
    + (SELECT COUNT(*) FROM lci_import_log
       WHERE status = 'ERROR' AND resolved_at IS NULL) AS error_count;

-- Query 5: จำนวนหน่วยมาตรฐานที่ระบบกำหนด
SELECT COUNT(*) AS unit_count
FROM unit;

-- Query 6: จำนวนแถว CSV ที่ผิดพลาดและยังไม่ถูกนำเข้า Exchange
SELECT COUNT(*) AS csv_import_error_count
FROM lci_import_log
WHERE status = 'ERROR'
  AND resolved_at IS NULL;

-- Query 7: รายละเอียด Error จาก CSV Import (คนละกลุ่มกับ Exchange)
SELECT s.src_code, log.source_line, log.reason, log.raw_data, log.last_seen_at
FROM lci_import_log AS log
JOIN source AS s ON s.source_id = log.source_id
WHERE log.status = 'ERROR'
  AND log.resolved_at IS NULL
ORDER BY s.src_code, log.source_line;

-- Query 8: จำนวนแถวที่ข้ามโดยตั้งใจ เช่น แถว TOTAL ที่อาจนับซ้ำ
SELECT COUNT(*) AS intentionally_skipped_count
FROM lci_import_log
WHERE status = 'SKIPPED'
  AND resolved_at IS NULL;

-- Query 9: จำนวนแถวต้นทางทั้งหมด (นำเข้า + CSV Error + ข้ามโดยตั้งใจ)
SELECT
    (SELECT COUNT(*) FROM lci_exchange)
    + (SELECT COUNT(*) FROM lci_import_log WHERE status = 'ERROR' AND resolved_at IS NULL)
    + (SELECT COUNT(*) FROM lci_import_log WHERE status = 'SKIPPED' AND resolved_at IS NULL)
    AS source_rows_accounted_for;
