import os
import json
import io
import re
import boto3
from pypdf import PdfReader

s3 = boto3.client("s3")

# Environment variables
BUCKET = os.environ["NIAHO_BUCKET"]
RAW_KEY = os.environ.get(
    "RAW_KEY",
    "raw/DNV_NIAHO_Accreditation_Requirements_for_Hospitals_Rev25-1.pdf"
)
CHUNKS_PREFIX = os.environ.get("CHUNKS_PREFIX", "chunks/")

# Pattern for chapter IDs like QM.1, LS.2, IC.3, etc.
CHAPTER_ID_PATTERN = re.compile(r"\b([A-Z]{2,3}\.\d+)\b")

def lambda_handler(event, context):
    """
    1) Read the NIAHO PDF from S3
    2) Extract text
    3) Split text into chapter-based chunks
    4) Save each chunk as chunks/chunk_XXX.json in S3
    """
    print(f"Reading PDF from s3://{BUCKET}/{RAW_KEY}")

    # 1. Read PDF from S3
    obj = s3.get_object(Bucket=BUCKET, Key=RAW_KEY)
    pdf_bytes = obj["Body"].read()
    print(f"PDF size in bytes: {len(pdf_bytes)}")

    reader = PdfReader(io.BytesIO(pdf_bytes))
    num_pages = len(reader.pages)
    print(f"Loaded PDF, total pages = {num_pages}")

    # 2. Extract text from pages (limit to first 80 pages for now)
    all_text = ""
    max_pages = min(num_pages, 80)  # TEMPORARY LIMIT
    for i in range(max_pages):
        page = reader.pages[i]
        page_text = page.extract_text() or ""
        all_text += page_text + "\n"
    print(f"Extracted text from {max_pages} pages")

    # 3. Split into chapters by IDs like QM.1, LS.2...
    chapters = split_by_chapter(all_text)
    print(f"Found {len(chapters)} chapter blocks after split_by_chapter")

    # 4. Save each chapter as a JSON chunk
    chunk_id_counter = 1
    saved_keys = []

    for ch in chapters:
        chapter_id = ch["chapter"]
        section_name = infer_section_from_chapter(chapter_id)
        chunk_text = ch["text"].strip()

        chunk_obj = {
            "chunk_id": f"{chunk_id_counter:03d}",
            "text": chunk_text,
            "metadata": {
                "document": "NIAHO Standards",
                "section": section_name,
                "chapter": chapter_id,
            },
            "token_count": len(chunk_text.split()),
            "embedding": None,
        }

        key = f"{CHUNKS_PREFIX}chunk_{chunk_id_counter:03d}.json"

        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(chunk_obj).encode("utf-8"),
            ContentType="application/json",
        )

        saved_keys.append(key)
        chunk_id_counter += 1

    print(f"Saved {chunk_id_counter - 1} chunks to S3")

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Chunks created",
                "count": chunk_id_counter - 1,
                "keys": saved_keys,
            }
        ),
    }

def split_by_chapter(raw_text: str):
    """
    Very simple splitter:
    - When a line starts with something like QM.1, LS.2, IC.3, treat it as new chapter.
    """
    lines = raw_text.splitlines()
    chapters = []
    current_id = None
    current_lines = []

    def flush():
        nonlocal current_id, current_lines, chapters
        if current_id and current_lines:
            chapters.append(
                {"chapter": current_id, "text": "\n".join(current_lines)}
            )
        current_lines = []

    for line in lines:
        m = CHAPTER_ID_PATTERN.search(line)
        if m and line.strip().startswith(m.group(1)):
            # Start of a new chapter
            flush()
            current_id = m.group(1)
            current_lines.append(line)
        else:
            if current_id:
                current_lines.append(line)

    flush()
    return chapters

def infer_section_from_chapter(chapter_id: str) -> str:
    """
    Simple mapping from chapter prefix to section name.
    """
    prefix = chapter_id.split(".")[0]
    mapping = {
        "QM": "Quality Management System",
        "GB": "Governing Body",
        "MS": "Medical Staff",
        "NS": "Nursing Services",
        "SM": "Staffing Management",
        "MM": "Medication Management",
        "SS": "Surgical Services",
        "AS": "Anesthesia Services",
        "OB": "Obstetrical Care Services",
        "LS": "Laboratory Services",
        "IC": "Infection Prevention and Control Program",
        "PE": "Physical Environment",
        "PR": "Patient Rights",
    }
    return mapping.get(prefix, "Unknown Section")
