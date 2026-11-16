-- งาน: ล้างข้อมูล LCI ที่นำเข้าจาก CSV เพื่อสร้างใหม่ด้วย Process name แบบสั้น
-- เก็บ SOURCE, LOCATION และ UNIT ไว้ตามเดิม
-- คำเตือน: ลบ PROCESS, FLOW, PROCESS_FLOW และ LCI_EXCHANGE ทั้งหมด
TRUNCATE TABLE lci_exchange, process_flow, process, flow RESTART IDENTITY;

-- ชื่อ Process ใช้ซ้ำได้ข้ามประเภทกระบวนการ แต่ห้ามซ้ำเมื่อชื่อ ประเภท และ Location เดียวกัน
ALTER TABLE process DROP CONSTRAINT IF EXISTS process_name_key;
ALTER TABLE process DROP CONSTRAINT IF EXISTS process_name_process_type_location_id_key;
ALTER TABLE process
    ADD CONSTRAINT process_name_process_type_location_id_key
    UNIQUE (name, process_type, location_id);
