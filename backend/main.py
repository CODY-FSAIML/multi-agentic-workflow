from fastapi import FastAPI
from pydantic import BaseModel
from worker import manager_agent

app = FastAPI()

class MissionRequest(BaseModel):
    prompt: str

# CHANGED THIS LINE TO MATCH YOUR 404 ERROR EXACTLY
@app.post("/api/v1/agents/workflow")
def start_mission(request: MissionRequest):
    task = manager_agent.delay(request.prompt)
    
    return {
        "status": "Manager assigned",
        "task_id": task.id,
        "message": "Check your Docker terminal logs to watch the agents communicate!"
    }