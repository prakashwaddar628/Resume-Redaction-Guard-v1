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
    
    done = False
    while not done:
        print(f"--- Step {obs.step} ---")
        print(f"Observation records: {[r.record_id for r in obs.records]}")
        
        # Construct the prompt with rigorous rules
        system_prompt = (
            "You are an AI compliance agent interacting with the Talent-Audit-Env.\n"
            "Your task is to review the observation and choose ONE valid action: Sanitize, Categorize, or Flag.\n"
            "- Sanitize: Redact PII fields like 'phone', 'email', 'name', 'address'. Do not alter technical skills.\n"
            "- Categorize: Assign a TechCategory (e.g. 'Frontend', 'Backend', 'DevOps').\n"
            "- Flag: Mark risk level ('High', 'Low', 'Medium') based on conflicting claims.\n\n"
            "You MUST output raw JSON matching exactly ONE of these payload structures:\n"
            "1) {\"action_type\": \"Sanitize\", \"record_id\": \"...\", \"sanitize_payload\": {\"fields\": [\"phone\"]}}\n"
            "2) {\"action_type\": \"Categorize\", \"record_id\": \"...\", \"categorize_payload\": {\"category\": \"Backend\", \"confidence\": 1.0}}\n"
            "3) {\"action_type\": \"Flag\", \"record_id\": \"...\", \"flag_payload\": {\"risk_level\": \"High\", \"reason\": \"...\"}}"
        )

        try:
            print(f"Prompting LLM ({MODEL_NAME})...")
            response = client.chat.completions.create(
                model=MODEL_NAME,
                response_format={ "type": "json_object" },
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Decide action for obs: {obs.model_dump_json()}"}
                ]
            )
            
            result_json = json.loads(response.choices[0].message.content)
            print(f"LLM decided: {result_json['action_type']} on {result_json['record_id']}")
            
            # Parse into our Action model
            action = Action.model_validate(result_json)
            
            # Apply action in environment
            obs, reward, done, info = env.step(action)
            print(f"Reward: {reward.total:+.2f} -> {reward.feedback}\n")
            
        except Exception as e:
            print(f"Agent encountered error: {e}")
            break
            
    print(f"Agent finished. Terminal state tracking total reward: {env.state()['total_reward']:+.2f}")

if __name__ == "__main__":
    run_agent("pii_easy")
