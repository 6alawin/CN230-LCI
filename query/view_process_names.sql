-- งาน: ดูชื่อ Process และประเภทกระบวนการที่สร้างจากข้อมูล SRC

SELECT process_id, name AS process_name, process_type
FROM process
๋JOIN
ORDER BY process_type, name;
