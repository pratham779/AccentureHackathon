import os
import logging
import subprocess
from typing import List

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pdfminer.high_level import extract_text
import docx

from agents.jd_summarizer import summarize_job_description, process_cvs

# Ensure spaCy model is available
import spacy
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI()

# CORS settings (allow all for now — adjust in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/process-jd/")
async def process_job_description(file: UploadFile):
    supported_types = [
        "text/plain",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]

    if file.content_type not in supported_types:
        logger.warning(f"Unsupported file type: {file.content_type}")
        raise HTTPException(status_code=400, detail="Unsupported file format")

    try:
        logger.info(f"Processing file: {file.filename} (type: {file.content_type})")
        if file.content_type == "text/plain":
            text = (await file.read()).decode("utf-8").strip()
        elif file.content_type == "application/pdf":
            text = extract_text(file.file).strip()
        elif file.content_type in ["application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
            doc = docx.Document(file.file)
            text = "\n".join(para.text for para in doc.paragraphs).strip()
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")
    except Exception as e:
        logger.error(f"Text extraction failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to extract text from file")

    if not text:
        logger.warning("File content is empty")
        raise HTTPException(status_code=400, detail="File content is empty")

    try:
        jd_data, jd_id = summarize_job_description(text)
        logger.info(f"Processed JD ID: {jd_id}")
        return {"jd_data": jd_data, "jd_id": jd_id}
    except Exception as e:
        logger.error(f"JD processing failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/process-cvs/{jd_id}")
async def process_candidate_cvs(jd_id: int, files: List[UploadFile] = File(...)):
    logger.info(f"Processing {len(files)} CV(s) for JD ID: {jd_id}")
    try:
        result = await process_cvs(jd_id, files)
        return result
    except HTTPException as e:
        logger.error(f"HTTP error: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"CV processing error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Entrypoint for manual run (e.g. local dev)
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI application...")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
