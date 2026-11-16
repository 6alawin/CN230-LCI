-- งาน: สรุปข้อมูลตามประเภทผลิตภัณฑ์ ประเภทกระบวนการ และช่วงเวลา (ปี)

SELECT f.product_type, f.name AS flow_name, p.process_type,
       e.period_year, u.symbol AS original_unit,
       CASE
           WHEN u.quantity_type IN ('VOLUME_RATE', 'GAS_RATE') THEN AVG(e.amount)
           ELSE SUM(e.amount)
       END AS summary_amount,
       CASE
           WHEN u.quantity_type IN ('VOLUME_RATE', 'GAS_RATE') THEN 'average of period rates'
           ELSE 'sum of period amounts'
       END AS aggregation_method,
       COUNT(*) AS exchange_count
FROM lci_exchange AS e
JOIN process_flow AS pf ON pf.process_flow_id = e.process_flow_id
JOIN process AS p ON p.process_id = pf.process_id
JOIN flow AS f ON f.flow_id = pf.flow_id
JOIN unit AS u ON u.unit_id = e.unit_id
GROUP BY f.product_type, f.name, p.process_type,
         e.period_year, u.symbol, u.quantity_type
ORDER BY e.period_year, f.product_type, f.name, p.process_type, u.symbol;
