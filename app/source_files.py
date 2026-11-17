"""Serve the project's published EPPO source CSVs by source code."""
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()
SOURCE = Path(__file__).resolve().parent.parent / "source"


@router.get("/api/source-csv/{code}")
def source_csv(code: str):
    if not re.fullmatch(r"SRC-(?:0[1-9]|1[0-9]|2[0-2])", code):
        raise HTTPException(404, "ไม่มีข้อมูลชุดนี้")
    path = SOURCE / f"{code}.csv"
    if not path.is_file():
        raise HTTPException(404, "ไม่มีไฟล์ของแหล่งข้อมูลนี้")
    return FileResponse(path, media_type="text/csv")

