-- งาน: เพิ่มข้อมูลหน่วยต้นทางและหน่วยมาตรฐานสำหรับเปรียบเทียบ/แปลงหน่วย
-- หน่วยฐานคือ L, L/day, scf/day และ kg; ยังเก็บหน่วยต้นทางของแต่ละ Exchange ไว้
-- ประเภทผลิตภัณฑ์และประเภทกระบวนการถูกเพิ่มตาม mapping ใน source/import_exchanges.py

INSERT INTO unit (symbol, quantity_type, to_base_factor)
VALUES
    ('L', 'VOLUME', 1),
    ('Million Litres', 'VOLUME', 1000000),
    ('MMSCF', 'VOLUME', 28316846.592),
    ('L/day', 'VOLUME_RATE', 1),
    ('BBL/DAY', 'VOLUME_RATE', 158.987295),
    ('Million Litres/Day', 'VOLUME_RATE', 1000000),
    ('scf/day', 'GAS_RATE', 1),
    ('MMSCFD', 'GAS_RATE', 1000000),
    ('kg', 'MASS', 1),
    ('Ton', 'MASS', 1000),
    ('Thousand Tons', 'MASS', 1000000),
    ('1,000 Tons', 'MASS', 1000000),
    ('Thousand Tons-CO2', 'MASS', 1000000)
ON CONFLICT (symbol) DO UPDATE SET
    quantity_type = EXCLUDED.quantity_type,
    to_base_factor = EXCLUDED.to_base_factor;
