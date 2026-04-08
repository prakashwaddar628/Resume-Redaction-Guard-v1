# Talent-Audit-Env 🛡️

> **An OpenEnv-compliant Reinforcement Learning environment for Automated HR Data Compliance.**

Agents learn to sanitise PII, categorise resumes by tech-stack, and detect conflicting career claims — all without sacrificing the integrity of technical skills data.

---

## Project Structure

```
Resume-Redaction-Guard-v1/
├── models.py        # Pydantic schemas: Observation, Action, Reward
├── tasks.py         # Task definitions (Easy / Medium / Hard) + fixture data
├── env.py           # TalentAuditEnv — core OpenEnv environment class
├── main.py          # FastAPI server (OpenEnv HTTP API)
├── run_demo.py      # CLI demo with oracle agents
├── openenv.yaml     # OpenEnv manifest
├── requirements.txt
└── Dockerfile
```

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the CLI demo (all 3 tasks)
python run_demo.py

# 3. Or run a single task
python run_demo.py --task pii_easy
python run_demo.py --task pii_medium
python run_demo.py --task audit_hard

# 4. Start the backend HTTP API server
uvicorn main:app --reload --port 8000
# → Swagger UI: http://localhost:8000/docs

# 5. Connect and launch the premium Next.js frontend
cd frontend
npm install
npm run dev
# → View UI: http://localhost:3000
```

---

## Docker

```bash
# Build
docker build -t talent-audit-env:1.0.0 .

# Run (API server)
docker run -p 8000:8000 talent-audit-env:1.0.0

# Run (CLI demo)
docker run talent-audit-env:1.0.0 python run_demo.py
```

---

## Environment API

### Python API

```python
from env import TalentAuditEnv
from models import Action, TechCategory, RiskLevel

env = TalentAuditEnv()

# --- Easy task ---
obs = env.reset("pii_easy")
action = Action.sanitize_action("r001", ["phone"])
obs, reward, done, info = env.step(action)
print(reward.total, reward.feedback)         # +0.8  PII removed from 1 field(s).

# --- Medium task ---
obs = env.reset("pii_medium")
action = Action.categorize_action("r001", TechCategory.BACKEND, confidence=0.95)
obs, reward, done, info = env.step(action)   # +0.2

action = Action.sanitize_action("r001", ["name", "email", "phone", "address"])
obs, reward, done, info = env.step(action)   # +0.8

# --- Hard task ---
obs = env.reset("audit_hard")
action = Action.flag_action("r006", RiskLevel.HIGH,
    reason="Claimed 8 years exp but graduated only 4 years ago.")
obs, reward, done, info = env.step(action)   # +0.3

summary = env.state()
print(summary["total_reward"])
```

### HTTP API (FastAPI)

| Method | Endpoint          | Description                        |
|--------|-------------------|------------------------------------|
| GET    | `/health`         | Liveness check                     |
| GET    | `/manifest`       | Returns parsed `openenv.yaml`      |
| GET    | `/tasks`          | Lists all registered tasks         |
| POST   | `/reset?task_id=` | Start a new episode                |
| POST   | `/step`           | Apply an action, get reward        |
| GET    | `/state`          | Full current environment state     |

---

## Tasks

| ID           | Difficulty | Max Steps | Goal |
|--------------|-----------|-----------|------|
| `pii_easy`   | Easy       | 5         | Remove phone number from 1 record |
| `pii_medium` | Medium     | 20        | Categorise + full PII removal across 5 records |
| `audit_hard` | Hard       | 15        | Detect conflicts, flag High-Risk profiles |

---

## Reward Scheme

| Signal            | Value  | Condition                                          |
|-------------------|--------|----------------------------------------------------|
| `pii_removal`     | `+0.8` | PII fields cleanly redacted, no technical data lost |
| `categorization`  | `+0.2` | Correct TechCategory assigned                       |
| `data_loss`       | `-0.5` | Technical skill / experience field deleted          |
| `conflict_detect` | `+0.3` | Genuinely conflicting profile flagged as High-Risk  |
| `false_flag`      | `-0.3` | Clean profile incorrectly flagged as High-Risk      |

---

## Models at a Glance

### `Observation`
```python
class Observation(BaseModel):
    task_id: str
    step: int
    records: List[ResumeRecord]   # ≥ 1 resume records
    context: Optional[Dict]       # task metadata, categorized/flagged state
    done: bool
```

### `Action`
```python
# Exactly one payload must be set
Action.sanitize_action(record_id, fields, replacement="[REDACTED]")
Action.categorize_action(record_id, category, confidence=1.0)
Action.flag_action(record_id, risk_level, reason)
```

### `Reward`
```python
class Reward(BaseModel):
    total: float
    breakdown: RewardBreakdown    # per-signal breakdown
    feedback: str                 # natural-language explanation
    is_terminal: bool
```

---

## OpenEnv Compliance

The `openenv.yaml` manifest declares:
- **observation_space** — `models.Observation`
- **action_space** — union of Sanitize | Categorize | Flag
- **reward_space** — scalar in `[-1.5, 2.0]`
- **tasks** — all three difficulty levels
- **evaluation metrics** — PII recall, category accuracy, data integrity, conflict F1
- **scoring formula** — weighted composite score
