-- 6.4 SRC-xx coverage check
-- จำนวนแถวนับจาก Exchange ที่นำเข้าใน lci_exchange

WITH src_groups (sort_order, src_label, src_codes, note) AS (
    VALUES
        (1, 'SRC-01', ARRAY['SRC-01']::text[], NULL::text),
        (2, 'SRC-02', ARRAY['SRC-02']::text[], NULL::text),
        (3, 'SRC-03', ARRAY['SRC-03']::text[], NULL::text),
        (4, 'SRC-04', ARRAY['SRC-04']::text[], NULL::text),
        (5, 'SRC-05', ARRAY['SRC-05']::text[], NULL::text),
        (6, 'SRC-06', ARRAY['SRC-06']::text[], NULL::text),
        (7, 'SRC-07', ARRAY['SRC-07']::text[], NULL::text),
        (8, 'SRC-08', ARRAY['SRC-08']::text[], NULL::text),
        (9, 'SRC-09–SRC-11', ARRAY['SRC-09', 'SRC-10', 'SRC-11']::text[], 'ใช้สำหรับตรวจสอบข้อมูล ไม่ใช่แหล่งข้อมูลหลัก')
)
SELECT
    g.src_label AS "SRC-xx",
    CASE WHEN COUNT(e.exchange_id) > 0 THEN 'มีข้อมูล' ELSE 'ไม่มีข้อมูล' END AS "มีข้อมูล",
    COUNT(e.exchange_id) AS "จำนวนแถว",
    COALESCE(g.note, string_agg(DISTINCT s.dataset_name, ', ')) AS "หมายเหตุ"
FROM src_groups AS g
LEFT JOIN source AS s
    ON s.src_code = ANY(g.src_codes)
LEFT JOIN lci_exchange AS e
    ON e.source_id = s.source_id
GROUP BY g.sort_order, g.src_label, g.note
ORDER BY g.sort_order;
