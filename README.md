# CN230 LCI Database และ Semantic Search

โครงการรวบรวมข้อมูลพลังงานและการปล่อย CO₂ จาก EPPO จัดเก็บใน PostgreSQL เชื่อมความสัมพันธ์ด้วย Neo4j และค้นข้อมูลด้วย Semantic Search และ RAG

- เว็บไซต์สาธิต: https://cn230-lci.onrender.com/
- หน้า SQL Query: https://cn230-lci.onrender.com/query
- ฐานข้อมูลที่ตรวจเมื่อ 16 พฤศจิกายน 2569 มี Exchange 42,599 รายการจาก 22 แหล่งข้อมูล และกราฟในเครื่องซิงก์ Exchange ครบ 42,599 โหนด

## โครงสร้าง repository

| ตำแหน่ง | เนื้อหา |
| --- | --- |
| `initdb/001_schema.sql` | PostgreSQL schema และ constraints |
| `source/SRC-01.csv` ถึง `source/SRC-22.csv` | ข้อมูลต้นทาง EPPO และ metadata |
| `query/` | SQL สำหรับตรวจสอบและวิเคราะห์ข้อมูล |
| `graph/sync_neo4j.py` | ซิงก์ PostgreSQL ไป Neo4j ด้วย UNWIND และ MERGE |
| `app/`, `static/` | FastAPI, Semantic Search, RAG และหน้าเว็บ |
| `CN230_M3_SQL.sql` | Schema และ 3 SQL Query สำหรับส่งงาน M3 |
| `tests/` | Regression tests สำหรับการค้นหาและ RAG |
| `notebooks/` | Notebook ทดลองซึ่งใช้ Gemini Embedding รุ่นก่อน |

## ทดลองผ่านเว็บ

หน้าเว็บค้นด้วยข้อความภาษาไทยหรืออังกฤษและกรองแหล่งข้อมูลได้ หน้าสาธิต Query บน Render รองรับ SQL แบบอ่านข้อมูล ส่วน Cypher ใช้ได้ในเว็บ local ที่เชื่อม Neo4j ผล Query แสดงสูงสุด 100 แถว

เว็บ Render ใช้ multilingual MiniLM แบบ 384 มิติและ pgvector ค้น Exchange จากนั้นส่งหลักฐานให้ Gemini สรุปคำตอบพร้อมอ้างอิง คำถามรายเดือนบางประเภทอ่านข้อมูลโดยตรงจาก PostgreSQL เพื่อแสดงเดือนที่มีข้อมูลและเดือนที่ขาด

## รันในเครื่อง

ติดตั้ง Docker Desktop และ Python 3.12 แล้วเปิด Docker Desktop จากนั้นรันที่ราก repository:

```powershell
docker compose up -d
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-local.txt
```

Docker สร้าง PostgreSQL ที่ `localhost:5433` และ Neo4j ที่ `localhost:7474` โดย schema จะสร้างเมื่อ volume PostgreSQL ถูกสร้างครั้งแรก ข้อมูล CSV ต้องนำเข้าฐานด้วยกระบวนการ ETL ก่อนจึงจะมีรายการสำหรับค้นหา โฟลเดอร์ source มีสคริปต์นำเข้าที่เคยใช้และไฟล์ CSV แต่การสร้างฐาน 22 แหล่งและดัชนีทั้งหมดจากศูนย์ยังไม่ได้ตรวจแบบครบขั้นตอน ไฟล์ใน repository ไม่รวมฐานข้อมูลที่นำเข้าแล้ว

สำหรับเครื่องนำเสนอที่มีข้อมูลและดัชนี local เตรียมไว้ ให้เปิด Ollama พร้อมโมเดล `gemma4:e2b` แล้วดับเบิลคลิก `Start.bat` หรือรัน `start_local.ps1` เพื่อเปิดเว็บ `http://127.0.0.1:8000` เว็บ local ใช้ Sentence Transformers และ Ollama ส่วน Cypher ต้องเปิด Neo4j ด้วย `docker compose up -d neo4j`

เมื่อต้องการซิงก์ข้อมูลลงกราฟจาก PostgreSQL ที่เตรียมแล้ว ให้รัน `graph/sync_neo4j.ps1` จากราก repository แล้วตรวจจำนวนและความสัมพันธ์ กราฟต้องซิงก์ใหม่เมื่อข้อมูลต้นทางเปลี่ยน

## ทดสอบ

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## Deploy Render

`render-cloud.yaml` แสดง build และ runtime สำหรับ ONNX MiniLM บน CPU การ deploy ต้องตั้ง `DATABASE_URL`, `GEMINI_API_KEY`, `SEARCH_BACKEND=local_model` และ `CLOUD_SNAPSHOT_SCHEMA` ให้ตรงกับฐานจริง โดยไม่ใส่รหัสผ่านหรือ API key ใน repository ส่วน notebook และสคริปต์ Gemini embedding เป็นวิธีทดลองรุ่นก่อนซึ่งใช้ดัชนีคนละชุดกับเว็บปัจจุบัน

## ข้อจำกัด

ข้อมูล EPPO เป็นข้อมูลตามแหล่ง หน่วย สาขา และช่วงเวลาที่ระบุ คะแนน semantic similarity ไม่ใช่ความน่าจะเป็นว่าคำตอบถูกต้อง ควรตรวจแหล่งอ้างอิงก่อนสรุป และการมีข้อมูลไม่ครบทุกเดือนไม่สามารถใช้แทนยอดทั้งปีได้