# CN230 LCI Semantic Search

เว็บค้นหาข้อมูล LCI ตามความหมายของคำค้น ด้วย Gemini Embeddings และ pgvector บน Render PostgreSQL

## สิ่งที่เตรียมไว้

- หน้าเว็บค้นภาษาไทย/อังกฤษพร้อมกรองแหล่ง SRC
- FastAPI endpoint สำหรับค้นเวกเตอร์
- SQL migration สำหรับ `pgvector` และตารางเก็บ embeddings
- สคริปต์ทำดัชนี Exchange จาก schema CN230 LCI
- Blueprint สำหรับ deploy เป็น Render Web Service
- `.python-version` ล็อก Python runtime ให้ build ทำซ้ำได้

## ตั้งค่าในเครื่อง

1. คัดลอก `.env.example` เป็น `.env` และกำหนด `DATABASE_URL` สำหรับพัฒนาในเครื่อง โดยใช้ External URL จาก Render พร้อม `?sslmode=require`
2. ใส่ Gemini API key ใน `GEMINI_API_KEY` (อย่า commit ไฟล์ `.env`)
3. ติดตั้งและเปิดเว็บ:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

เปิด `http://localhost:8000` เพื่อใช้หน้า search และ `http://localhost:8000/docs` เพื่อดู API

## เตรียม Render PostgreSQL

รัน [db/001_semantic_search.sql](db/001_semantic_search.sql) หนึ่งครั้งกับฐานข้อมูล Render เพื่อเปิด extension `vector` และสร้างตาราง/ดัชนีค้นหา ไฟล์นี้ไม่แก้หรือลบตาราง LCI เดิม

## ทำดัชนีข้อมูล

เมื่อใส่ `GEMINI_API_KEY` และรัน migration แล้ว:

```powershell
python scripts/index_lci.py --limit 100
```

ใช้ `--limit 100` ทดลองปริมาณเล็กน้อยก่อน จากนั้นรันโดยไม่ใส่ `--limit` เพื่อสร้าง embeddings ให้ครบทุก Exchange ที่ยังไม่มีหรือข้อมูลเปลี่ยน สคริปต์เก็บผลเป็นชุดและอัปเดตซ้ำได้

## รันงานบน Render

เมื่อตั้ง `DATABASE_URL` และ `GEMINI_API_KEY` ใน Render Web Service แล้ว ให้เปิด **Shell** ของบริการและรันจากโฟลเดอร์รากของ repository:

```sh
python scripts/setup_semantic_search.py
python scripts/index_lci.py --limit 100
```

ถ้าผลทดลองถูกต้อง ให้รัน `python scripts/index_lci.py` โดยไม่ใส่ `--limit` เพื่อทำ embeddings ให้ครบ งานนี้อ่านฐานข้อมูล Render ผ่าน Internal URL และใช้ Gemini key จาก Environment ของบริการ ไม่ต้องนำ secret มาใส่ในคำสั่ง

การย้ายตาราง LCI จาก LocalDB เป็นอีกขั้นหนึ่ง: Render ต้องได้รับไฟล์ dump ก่อน เพราะไม่สามารถอ่านไฟล์หรือ Docker container ในเครื่องเราได้ หลังส่ง dump เข้า Render แล้ว จึงค่อย restore และรันคำสั่งข้างต้นบน Render

## Deploy ที่ Render

ใช้ Blueprint จาก `render.yaml` โดยตั้ง Environment Variables ในหน้า Render:

- `DATABASE_URL`: Internal Database URL ของ Render จาก host/port/database/user/password ที่ให้มา เมื่อ Web Service อยู่ใน workspace และ region เดียวกัน
- `GEMINI_API_KEY`: API key จาก Google AI Studio

Hostname รูปแบบ `dpg-...-a` ที่ได้มาจาก Render เป็น Internal URL ใช้ได้เมื่อ Web Service อยู่ใน workspace/region เดียวกับ DB เท่านั้น ให้นำค่า Internal URL ไปตั้ง `DATABASE_URL` ใน Environment ของ Render; สำหรับรันในเครื่องต้องใช้ External URL ซึ่งมี hostname อีกแบบและต้องมี `sslmode=require`.

ใช้โมเดล `gemini-embedding-001` เพื่อสร้าง embeddings หลายรายการต่อ request ได้อย่างถูกต้อง พร้อมแยก task สำหรับเอกสารและ query ตามงาน retrieval ของ Gemini

เก็บ secret ใน Environment ของ Render เท่านั้น ห้ามใส่ลง Git หรือ `render.yaml`

## Deploy หน้า Dashboard บน Vercel

โปรเจกต์นี้เตรียม `vercel.json` ไว้ให้ Vercel เสิร์ฟไฟล์หน้าเว็บจาก `static/` และ proxy คำขอ `/api/*` ไปยัง FastAPI ที่ Render (`https://cn230-lci.onrender.com`) หน้า Dashboard จึงเรียก `/api/health` และ `/api/search` บน origin เดียวกับหน้าเว็บได้ โดยไม่ต้องใส่ Gemini key ใน Vercel หรือเปิด CORS เพิ่ม

เมื่อนำ GitHub repository นี้เข้า Vercel ให้ใช้ Root Directory เป็นราก repository และ Framework Preset เป็น Other; ค่าคำสั่ง build และ output directory อ่านจาก `vercel.json` (`static`) ได้เลย หาก Project Settings มีค่า override เก่าค้างอยู่ ให้ปิด override เพื่อให้ใช้ค่าจากไฟล์

`DATABASE_URL` และ `GEMINI_API_KEY` ยังคงต้องตั้งไว้ใน Environment ของ Render เพราะ Render เป็น backend ที่เรียกฐานข้อมูลและ Gemini ส่วน Vercel ให้บริการเฉพาะหน้าเว็บและ proxy API

API: `POST /api/search` รับ `{ "query": "การใช้ก๊าซธรรมชาติ", "limit": 10, "source_code": "SRC-11" }`

สถานะ: `GET /api/health`
