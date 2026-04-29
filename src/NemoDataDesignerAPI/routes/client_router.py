import uuid
import time
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from models.requests import GenerateRequest
from controllers.job_controller import run_job
from config import JOB_STORE, UPLOAD_DIR
import db

router = APIRouter(
    prefix="/data_generation/v1",
)

def save_file(file: UploadFile):
    path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    with open(path, "wb") as buffer: buffer.write(file.file.read())
    return path

@router.post("/create")
def create_job(bg: BackgroundTasks, generate_request: str = Form(...), seed_data: UploadFile = File(None)):
    try:
        req = GenerateRequest.model_validate_json(generate_request)
        path = save_file(seed_data) if seed_data else None
        job_id = str(uuid.uuid4())

        JOB_STORE[job_id] = {"status": "processing", "created_at": time.time()}
        # Persist to PostgreSQL (non-fatal – never stores API keys)
        db.insert_job(
            job_id=job_id, job_type="create",
            generate_request=req.model_dump(exclude={"provider_api_key"}),
            model_provider=req.model_provider, model_id=req.model_id,
            num_records=req.num_records or 50,
        )
        bg.add_task(run_job, job_id, req, path, "create")

        return {"status": "processing", "job_id": job_id}
    except Exception as e: raise HTTPException(500, str(e))

@router.post("/preview")
def preview_job(bg: BackgroundTasks, generate_request: str = Form(...), seed_data: UploadFile = File(None)):
    try:
        req = GenerateRequest.model_validate_json(generate_request)
        path = save_file(seed_data) if seed_data else None
        job_id = str(uuid.uuid4())

        JOB_STORE[job_id] = {"status": "processing", "created_at": time.time()}
        # Persist to PostgreSQL (non-fatal – never stores API keys)
        db.insert_job(
            job_id=job_id, job_type="preview",
            generate_request=req.model_dump(exclude={"provider_api_key"}),
            model_provider=req.model_provider, model_id=req.model_id,
            num_records=req.num_records or 50,
        )
        bg.add_task(run_job, job_id, req, path, "preview")

        return {"status": "processing", "job_id": job_id}
    except Exception as e: raise HTTPException(500, str(e))

@router.get("/jobs")
def get_all_jobs():
    jobs = sorted(
        [{"job_id": job_id, **job_data} for job_id, job_data in JOB_STORE.items()],
        key=lambda x: x["created_at"]
    )
    return {"jobs": jobs, "total": len(jobs)}

@router.get("/jobs/{job_id}")
def get_status(job_id: str):
    job = JOB_STORE.get(job_id)
    if not job: raise HTTPException(404, "Job not found")
    return job
