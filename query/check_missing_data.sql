-- งาน: ตรวจสอบข้อมูลว่างและรายการที่ยังรอตรวจ/มีข้อผิดพลาด

SELECT exchange_id, process_flow_id, amount, unit_id,
       period_year, period_month, source_id, validation_status, note
FROM lci_exchange
WHERE amount IS NULL
   OR unit_id IS NULL
   OR period_year IS NULL
   OR source_id IS NULL
   OR validation_status IN ('PENDING', 'ERROR')
ORDER BY exchange_id;
