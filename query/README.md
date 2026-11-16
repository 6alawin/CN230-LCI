# SQL Queries

เปิดไฟล์แต่ละไฟล์ใน VS Code แล้วกด Run ใน PostgreSQL extension โดยเชื่อมต่อฐานข้อมูล `cn230lci` ไฟล์ถูกแยกตามงานเพื่อเลือกใช้ทีละเรื่อง:

- `insert_sources.sql` เพิ่มข้อมูล SRC-01 ถึง SRC-18
- `insert_location.sql` เพิ่มประเทศไทยเป็น location
- `insert_units.sql` เพิ่มหน่วยต้นทางและหน่วยฐานสำหรับแปลงค่า
- `index_exchange_import_note.sql` เตรียมดัชนีสำหรับนำเข้าข้อมูลซ้ำอย่างปลอดภัย
- `create_import_log.sql` สร้างตารางบันทึกแถว Error และแถวที่ข้ามจาก CSV
- `reset_imported_lci.sql` ล้างข้อมูล LCI เพื่อสร้างใหม่ด้วยชื่อ Process แบบสั้น
- `check_missing_data.sql` แสดงข้อมูลที่ยังรอตรวจหรือมีข้อผิดพลาด
- `check_duplicate_exchange.sql` ค้นหารายการ Exchange ที่อาจซ้ำ
- `check_relationships.sql` ดูความเชื่อมโยง Process, Flow, Unit และ Source
- `view_lci_exchange.sql` เรียกดูรายการ Exchange พร้อมข้อมูลประกอบ
- `view_process_names.sql` แสดงชื่อ Process และประเภทกระบวนการ
- `view_flow_names.sql` แสดงชื่อ Flow และประเภทผลิตภัณฑ์
- `view_standard_units.sql` คำนวณค่าเทียบหน่วยฐานโดยเก็บค่าต้นฉบับไว้
- `summary_by_product_process_period.sql` สรุปตามผลิตภัณฑ์ ประเภท Process และปี
- `unit_consistency_validated_only_counts.sql` นับข้อมูลตามสถานะ พร้อมรายละเอียด Import Error
- `verify_imported_exchanges.sql` ตรวจ amount, period, unit และรายการซ้ำ ก่อนตั้งสถานะ VERIFIED
- `src_coverage_check.sql` ตรวจว่ามี Exchange จาก SRC แต่ละชุดหรือไม่และนับจำนวนแถว

ไฟล์สร้างตารางหลักอยู่ที่ `../initdb/001_schema.sql` ส่วนข้อมูลจำนวนมากใน `lci_exchange` นำเข้าด้วยสคริปต์ Python ในโฟลเดอร์ `../source`.
