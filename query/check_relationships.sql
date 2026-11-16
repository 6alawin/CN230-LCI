-- งาน: ตรวจสอบความสัมพันธ์ระหว่าง Process, Flow, Exchange, Unit และ Source

SELECT e.exchange_id, p.name AS process_name, f.name AS flow_name,
       pf.direction, u.symbol AS original_unit, s.src_code,
       e.period_year, e.period_month, e.amount
FROM lci_exchange AS e
JOIN process_flow AS pf ON pf.process_flow_id = e.process_flow_id
JOIN process AS p ON p.process_id = pf.process_id
JOIN flow AS f ON f.flow_id = pf.flow_id
JOIN unit AS u ON u.unit_id = e.unit_id
JOIN source AS s ON s.source_id = e.source_id
ORDER BY e.exchange_id
LIMIT 500;
