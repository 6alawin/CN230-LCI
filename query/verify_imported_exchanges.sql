-- ตรวจความสอดคล้องที่ทำได้อัตโนมัติ แล้วตั้งสถานะรายการที่ผ่านเป็น VERIFIED
-- แหล่งข้อมูลที่ไม่ครบจะถูกเก็บใน lci_import_log แยกจาก lci_exchange

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM lci_exchange e
        JOIN process_flow pf ON pf.process_flow_id = e.process_flow_id
        JOIN flow f ON f.flow_id = pf.flow_id
        JOIN unit u ON u.unit_id = e.unit_id
        JOIN source s ON s.source_id = e.source_id
        WHERE e.amount < 0
           OR e.period_year NOT BETWEEN 1 AND 9999
           OR (e.period_month IS NOT NULL AND e.period_month NOT BETWEEN 1 AND 12)
           OR u.quantity_type IS DISTINCT FROM CASE s.src_code
                WHEN 'SRC-01' THEN 'VOLUME_RATE'
                WHEN 'SRC-02' THEN 'VOLUME_RATE'
                WHEN 'SRC-03' THEN 'VOLUME'
                WHEN 'SRC-04' THEN 'VOLUME_RATE'
                WHEN 'SRC-05' THEN 'VOLUME'
                WHEN 'SRC-06' THEN 'VOLUME'
                WHEN 'SRC-07' THEN 'VOLUME'
                WHEN 'SRC-08' THEN 'VOLUME'
                WHEN 'SRC-09' THEN 'MASS'
                WHEN 'SRC-10' THEN 'GAS_RATE'
                WHEN 'SRC-11' THEN 'GAS_RATE'
                WHEN 'SRC-12' THEN 'VOLUME_RATE'
                WHEN 'SRC-13' THEN 'MASS'
                WHEN 'SRC-14' THEN 'MASS'
                WHEN 'SRC-15' THEN 'MASS'
                WHEN 'SRC-16' THEN 'VOLUME_RATE'
                WHEN 'SRC-17' THEN 'VOLUME_RATE'
                WHEN 'SRC-18' THEN 'MASS'
                WHEN 'SRC-19' THEN 'MASS'
                WHEN 'SRC-20' THEN 'MASS'
                WHEN 'SRC-21' THEN 'MASS'
                ELSE NULL
              END
    ) THEN
        RAISE EXCEPTION 'ตรวจพบข้อมูล amount, period หรือ unit ที่ไม่ตรงกับกฎของแหล่งข้อมูล';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM lci_exchange
        GROUP BY process_flow_id, period_year, period_month, amount, unit_id, source_id
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'ตรวจพบ Exchange ที่อาจซ้ำ กรุณาตรวจสอบก่อนยืนยัน';
    END IF;

    UPDATE lci_exchange
    SET validation_status = 'VERIFIED'
    WHERE validation_status = 'PENDING';
END $$;
