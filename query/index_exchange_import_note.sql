-- งานประกอบ: เตรียมดัชนีให้ Python นำเข้า Exchange จำนวนมากและรันซ้ำได้
-- ดัชนีนี้ใช้หาแถว CSV ที่เคยนำเข้าแล้ว ไม่ใช่ Query สำหรับดูข้อมูล
CREATE INDEX IF NOT EXISTS idx_lci_exchange_import_note
    ON lci_exchange (note)
    WHERE note IS NOT NULL;
