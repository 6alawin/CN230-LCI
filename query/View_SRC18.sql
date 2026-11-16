SELECT
    e.exchange_id,
    s.src_code,
    s.dataset_name,
    p.name AS process_name,
    p.process_type,
    f.name AS flow_name,
    f.product_type,
    pf.direction,
    e.amount,
    u.symbol AS unit,
    e.period_year,
    e.period_month,
    e.validation_status
FROM lci_exchange AS e
JOIN source AS s ON s.source_id = e.source_id
JOIN process_flow AS pf ON pf.process_flow_id = e.process_flow_id
JOIN process AS p ON p.process_id = pf.process_id
JOIN flow AS f ON f.flow_id = pf.flow_id
JOIN unit AS u ON u.unit_id = e.unit_id
WHERE s.src_code = 'SRC-22'
ORDER BY e.period_year, e.period_month, e.exchange_id;