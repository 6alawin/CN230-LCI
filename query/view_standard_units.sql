-- งาน: ปรับ/แสดงค่าปริมาณในหน่วยมาตรฐานของระบบ
-- คำนวณค่าเทียบหน่วยฐานจาก to_base_factor โดยไม่เขียนทับ amount หรือหน่วยต้นทาง

SELECT e.exchange_id, p.name AS process_name, f.name AS flow_name,
       e.amount AS original_amount, u.symbol AS original_unit,
       e.amount * u.to_base_factor AS standardized_amount,
       CASE u.quantity_type
           WHEN 'VOLUME' THEN 'L'
           WHEN 'VOLUME_RATE' THEN 'L/day'
           WHEN 'GAS_RATE' THEN 'scf/day'
           WHEN 'MASS' THEN 'kg'
       END AS standardized_unit,
       e.period_year, e.period_month, s.src_code
FROM lci_exchange AS e
JOIN process_flow AS pf ON pf.process_flow_id = e.process_flow_id
JOIN process AS p ON p.process_id = pf.process_id
JOIN flow AS f ON f.flow_id = pf.flow_id
JOIN unit AS u ON u.unit_id = e.unit_id
JOIN source AS s ON s.source_id = e.source_id
ORDER BY e.period_year, e.period_month, p.name, f.name;
