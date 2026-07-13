from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from uuid import UUID

import models, schemas
from celery_worker import run_multi_agent_workflow
from database import engine, get_db
from worker import test_agent_task

app = FastAPI(title="Distributed Multi-Agent System")


@app.on_event("startup")
def initialize_database() -> None:
    models.Base.metadata.create_all(bind=engine)


@app.post("/api/v1/agents/workflow", status_code=202)
def start_workflow(payload: schemas.WorkflowCreate, db: Session = Depends(get_db)):
    db_job = models.WorkflowJob(user_prompt=payload.prompt, status="queued")
    db.add(db_job)
    db.commit()
    db.refresh(db_job)

    run_multi_agent_workflow.delay(str(db_job.id), payload.prompt)

    return {
        "workflow_id": db_job.id,
        "status": db_job.status,
        "check_status_url": f"/api/v1/agents/workflow/{db_job.id}",
    }


@app.get("/api/v1/agents/workflow/{workflow_id}")
def get_workflow_status(workflow_id: UUID, db: Session = Depends(get_db)):
    job = db.query(models.WorkflowJob).filter(models.WorkflowJob.id == workflow_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Workflow job not found")

    return {
        "workflow_id": job.id,
        "status": job.status,
        "logs": [{"agent": log.agent_name, "status": log.status} for log in job.logs],
        "final_result": job.final_result,
    }


class TaskRequest(BaseModel):
    prompt: str


@app.get("/")
def read_root():
    return {"message": "Backend is live and running!"}


@app.post("/run-agent")
def run_agent(request: TaskRequest):
    task = test_agent_task.delay(request.prompt)
    return {"task_id": task.id, "message": "Agent task submitted to queue"}