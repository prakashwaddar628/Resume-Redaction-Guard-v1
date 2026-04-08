import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from env import TalentAuditEnv
from models import Action, ActionType, RiskLevel, TechCategory

# Load variables from .env if present
load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "your_api_key")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4-turbo")

def run_agent(task_id: str = "pii_easy"):
    """
    Example agent loop that connects to the environment and uses an LLM.
    """
    print(f"Starting agent for task: {task_id}")
    print(f"Using model: {MODEL_NAME} at base URL: {API_BASE_URL}")
    
    # Initialize OpenAI client 
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        base_url=API_BASE_URL
    )

    env = TalentAuditEnv()
    obs = env.reset(task_id)
    
    # Simple loop
    done = False
    while not done:
        print(f"--- Step {obs.step} ---")
        
        # Here you would typically prompt your LLM to decide the action:
        # response = client.chat.completions.create(
        #     model=MODEL_NAME,
        #     messages=[{"role": "user", "content": f"Decide action for obs: {obs.model_dump_json()}"}]
        # )
        
        # For demonstration, we'll just break or do a dummy action
        print("Prompting LLM with the observation...")
        print("Observation records:", [r.record_id for r in obs.records])
        
        # TODO: parse LLM output into an Action object
        # ...
        
        # dummy breakout to prevent infinite loop for now
        break
        
    print("Agent finished.")

if __name__ == "__main__":
    run_agent("pii_easy")
