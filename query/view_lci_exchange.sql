-- งาน: ค้นหาและแสดง Process, Flow และ Exchange สำหรับจัดทำ LCI
-- แสดงทิศทาง ปริมาณ หน่วยต้นทาง ช่วงเวลา และ Source เพื่อให้ตรวจย้อนกลับได้\

SELECT p.name AS process_name, p.process_type, f.name AS flow_name,
       f.product_type, pf.direction, e.amount, u.symbol AS original_unit,
       e.period_year, e.period_month, s.src_code, s.dataset_name,
       e.validation_status, e.note
FROM lci_exchange AS e
JOIN process_flow AS pf ON pf.process_flow_id = e.process_flow_id
JOIN process AS p ON p.process_id = pf.process_id
JOIN flow AS f ON f.flow_id = pf.flow_id
JOIN unit AS u ON u.unit_id = e.unit_id
JOIN source AS s ON s.source_id = e.source_id
ORDER BY e.period_year, e.period_month, p.name, f.name;
