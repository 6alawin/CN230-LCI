-- งาน: ดูชื่อ Flow และประเภทผลิตภัณฑ์ที่ใช้ใน LCI
SELECT flow_id, name AS flow_name, product_type
FROM flow
ORDER BY product_type, name;
