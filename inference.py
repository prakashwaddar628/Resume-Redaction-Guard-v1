import os
import json
from openai import OpenAI

# Required Environment Variables
API_URL = os.getenv("API_BASE_URL")
MODEL = os.getenv("MODEL_NAME")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=API_URL)

def run_evaluation():
    # Example logic
    task_id = "pii_easy"
    print(f"[START] Task: {task_id}")
    
    # Mocking a step
    print(f"[STEP] Action: Redact_Email | Reward: 0.8 | Done: False")
    
    # End of task
    print(f"[END] Task: {task_id} | Final Score: 0.85")

if __name__ == "__main__":
    run_evaluation()