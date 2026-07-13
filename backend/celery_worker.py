import os
from uuid import UUID

from celery import Celery
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from database import SessionLocal
import models

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery_app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)

# Ensure tasks aren't lost if a container crashes mid-execution
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1

# Production-grade LLM Caller with automatic rate limit handling
@retry(wait=wait_exponential(min=2, max=10), stop=stop_after_attempt(3))
def call_llm_api(system_prompt: str, user_prompt: str) -> str:
    api_key = os.getenv("LLM_API_KEY")
    url = "https://api.groq.com/openai/v1/chat/completions" 
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        # Change this line to the current supported model
        "model": "llama-3.3-70b-versatile", 
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        # This will print the actual error if it's not a 200 OK
        if response.status_code != 200:
            print(f"LLM API ERROR: {response.status_code} - {response.text}")
        response.raise_for_status() 
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"REQUEST EXCEPTION: {e}")
        raise e

@celery_app.task(name="run_multi_agent_workflow")
def run_multi_agent_workflow(job_id: str, prompt: str):
    db = SessionLocal()
    try:
        job_uuid = UUID(job_id)
        # Update main status
        job = db.query(models.WorkflowJob).filter(models.WorkflowJob.id == job_uuid).first()
        job.status = "processing"
        db.commit()

        # --- STATE MACHINE LOOP ---
        state = {"original_prompt": prompt, "current_context": ""}

        # Agent 1: The Researcher/Planner
        log1 = models.AgentLog(job_id=job_id, agent_name="Researcher", status="processing")
        db.add(log1)
        db.commit()

        research_sys = "You are an expert research agent. Break down the user prompt into structural components."
        state["current_context"] = call_llm_api(research_sys, state["original_prompt"])
        
        log1.status = "completed"
        log1.output_data = {"result": state["current_context"]}
        db.commit()

        # Agent 2: The Refiner/Writer
        log2 = models.AgentLog(job_id=job_id, agent_name="Refiner", status="processing")
        db.add(log2)
        db.commit()

        refiner_sys = "You are a professional synthesis agent. Take the research data and package it into a cohesive final delivery."
        final_output = call_llm_api(refiner_sys, state["current_context"])
        
        log2.status = "completed"
        log2.output_data = {"result": final_output}
        
        # Finalize the entire workflow
        job.status = "completed"
        job.final_result = {"output": final_output}
        db.commit()

    except Exception as e:
        if 'job' in locals():
            job.status = "failed"
            job.final_result = {"error": str(e)}
            db.commit()
        raise e
    finally:
        db.close()