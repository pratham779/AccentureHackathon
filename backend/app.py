import os
import logging
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from pdfminer.high_level import extract_text
import docx
from agents.jd_summarizer import summarize_job_description, process_cvs

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Temporary wildcard for debugging
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint to confirm the API is running
@app.get("/")
async def root():
    return {"message": "API is running"}

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
            text = await file.read()
            text = text.decode("utf-8").strip()
        elif file.content_type == "application/pdf":
            text = extract_text(file.file).strip()
        elif file.content_type in [
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]:
            doc = docx.Document(file.file)
            text = "\n".join([para.text for para in doc.paragraphs]).strip()
        else:
            logger.error(f"Unexpected file type processed: {file.content_type}")
            raise HTTPException(status_code=400, detail="Unsupported file format")
    except Exception as e:
        logger.error(f"Text extraction failed for {file.filename}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to extract text from file")

    if not text:
        logger.warning(f"Empty content in file: {file.filename}")
        raise HTTPException(status_code=400, detail="File content is empty")

    try:
        logger.info(f"Summarizing job description for file: {file.filename}")
        jd_data, jd_id = summarize_job_description(text)
        logger.info(f"Successfully processed JD ID: {jd_id}")
        return {"jd_data": jd_data, "jd_id": jd_id}
    except Exception as e:
        logger.error(f"Failed to process job description: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/process-cvs/{jd_id}")
async def process_candidate_cvs(jd_id: int, files: List[UploadFile] = File(...)):
    logger.info(f"Starting CV processing for JD ID: {jd_id} with {len(files)} files")
    try:
        result = await process_cvs(jd_id, files)
        logger.info(f"CV processing completed for JD ID: {jd_id}")
        return result
    except HTTPException as e:
        logger.error(f"HTTP error during CV processing: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during CV processing: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI application...")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
