from celery import Celery, chain
import os

# Initialize Celery (Ensuring it matches your Docker setup)
celery = Celery(__name__)
celery.conf.broker_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery.conf.result_backend = os.getenv("REDIS_URL", "redis://redis:6379/0")

# ---------------------------------------------------------
# SUB-AGENT 1: The Extractor
# ---------------------------------------------------------
@celery.task(name="extractor_agent")
def extractor_agent(prompt: str):
    print(f"\n[Agent 1 - Extractor] Analyzing prompt: '{prompt}'")
    # TODO: Add real LLM logic here later
    mock_keywords = ["distributed systems", "automation", "python"]
    print(f"[Agent 1 - Extractor] Found keywords: {mock_keywords}")
    
    # The return value of this task is automatically passed to the next task in the chain
    return mock_keywords

# ---------------------------------------------------------
# SUB-AGENT 2: The Generator
# ---------------------------------------------------------
@celery.task(name="generator_agent")
def generator_agent(keywords: list):
    print(f"\n[Agent 2 - Generator] Writing content based on: {keywords}")
    # TODO: Add real LLM logic here later
    final_output = f"Here is a generated report focusing on {', '.join(keywords)}."
    print(f"[Agent 2 - Generator] Finished writing: '{final_output}'\n")
    
    return final_output

# ---------------------------------------------------------
# THE MANAGER AGENT
# ---------------------------------------------------------
@celery.task(name="manager_agent")
def manager_agent(prompt: str):
    print(f"\n[Manager Agent] Received new mission: '{prompt}'")
    print(f"[Manager Agent] Delegating to Extractor and Generator...")
    
    # A Celery 'chain' passes the output of the first task into the input of the second
    workflow = chain(
        extractor_agent.s(prompt), 
        generator_agent.s()
    )
    
    # Execute the workflow in the background
    workflow.apply_async()
    return "Workflow delegated to sub-agents."