-- งาน: ตรวจสอบข้อมูล Exchange ที่อาจซ้ำกัน

SELECT process_flow_id, period_year, period_month, amount, unit_id, source_id,
       COUNT(*) AS duplicate_count,
       ARRAY_AGG(exchange_id ORDER BY exchange_id) AS exchange_ids
FROM lci_exchange
GROUP BY process_flow_id, period_year, period_month, amount, unit_id, source_id
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, period_year, period_month;
