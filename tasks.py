"""
tasks.py — Talent-Audit-Env
Defines the three canonical tasks:
  - Easy   (pii_easy):   Remove phone numbers from a single JSON record.
  - Medium (pii_medium): Categorize 5 resumes by tech-stack + remove all PII.
  - Hard   (audit_hard): Detect cross-record conflicts and flag High-Risk profiles.

Each task function returns a TaskSpec dict consumed by TalentAuditEnv.__init__().
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Set

from models import TechCategory


# ---------------------------------------------------------------------------
# Shared PII field lists
# ---------------------------------------------------------------------------

PII_FIELDS: Set[str] = {"name", "email", "phone", "address", "linkedin", "github_personal"}


# ---------------------------------------------------------------------------
# Raw fixture data  (representative synthetic resumes)
# ---------------------------------------------------------------------------

_RESUME_ALICE: Dict[str, Any] = {
    "name": "Alice Johnson",
    "email": "alice.j@example.com",
    "phone": "+1-800-555-0101",
    "address": "42 Maple Street, Boston, MA 02101",
    "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes"],
    "experience": [
        {
            "title": "Senior Backend Engineer",
            "company": "TechCorp",
            "years": 4,
            "stack": ["Python", "Django", "Redis"],
        }
    ],
    "education": "B.Sc. Computer Science, MIT 2015",
    "certifications": ["AWS Solutions Architect"],
    "years_experience": 4,
}

_RESUME_BOB: Dict[str, Any] = {
    "name": "Bob Martinez",
    "email": "bob.m@personal.net",
    "phone": "077-555-0202",
    "address": "18 Oak Ave, Austin, TX 78701",
    "skills": ["React", "TypeScript", "GraphQL", "AWS Amplify", "Tailwind CSS"],
    "experience": [
        {
            "title": "Frontend Developer",
            "company": "StartupX",
            "years": 2,
            "stack": ["Vue.js", "Nuxt", "CSS"],
        }
    ],
    "education": "B.Eng. Software Engineering, UT Austin 2019",
    "certifications": [],
    "years_experience": 2,
}

_RESUME_CAROL: Dict[str, Any] = {
    "name": "Carol Okafor",
    "email": "carol@devops.io",
    "phone": "+44 7700 900300",
    "address": "7 King's Road, London, UK EC1A 1BB",
    "skills": ["Terraform", "Ansible", "Jenkins", "AWS", "GCP", "Linux", "Bash"],
    "experience": [
        {
            "title": "DevOps Engineer",
            "company": "CloudBuilders Ltd",
            "years": 5,
            "stack": ["Kubernetes", "Helm", "ArgoCD"],
        }
    ],
    "education": "M.Sc. Systems Engineering, UCL 2017",
    "certifications": ["CKA", "GCP Professional DevOps Engineer"],
    "years_experience": 5,
}

_RESUME_DAN: Dict[str, Any] = {
    "name": "Dan Kim",
    "email": "d.kim@datasci.org",
    "phone": "555-303-0404",
    "address": "99 Silicon Blvd, San Francisco, CA 94105",
    "skills": ["Python", "PyTorch", "TensorFlow", "Pandas", "Spark", "SQL"],
    "experience": [
        {
            "title": "ML Engineer",
            "company": "DataLabs",
            "years": 3,
            "stack": ["Scikit-learn", "Airflow", "MLflow"],
        }
    ],
    "education": "Ph.D. Machine Learning, Stanford 2020",
    "certifications": ["Google Professional ML Engineer"],
    "years_experience": 3,
}

_RESUME_EVA: Dict[str, Any] = {
    "name": "Eva Rossi",
    "email": "eva.r@fullstack.dev",
    "phone": "+39 02 1234 5678",
    "address": "Via Roma 55, Milan, Italy 20121",
    "skills": ["Node.js", "React", "MongoDB", "Express.js", "Docker"],
    "experience": [
        {
            "title": "Full Stack Developer",
            "company": "DigitalAgency",
            "years": 3,
            "stack": ["Next.js", "PostgreSQL", "Redis"],
        }
    ],
    "education": "B.Sc. Information Systems, Bocconi 2018",
    "certifications": [],
    "years_experience": 3,
}

# ---------------------------------------------------------------------------
# Conflict-laden fixture for the Hard task
# Records deliberately contain cross-record inconsistencies
# ---------------------------------------------------------------------------

_RESUME_FRANK: Dict[str, Any] = {
    "name": "Frank Nguyen",
    "email": "frank.n@consulting.biz",
    "phone": "800-555-0505",
    "address": "88 Harbor View, Seattle, WA 98101",
    # CONFLICT: claims 8 years experience but graduated 4 years ago
    "skills": ["Java", "Spring Boot", "Microservices", "Kafka", "gRPC"],
    "experience": [
        {
            "title": "Principal Software Engineer",
            "company": "MegaCorp",
            "years": 8,          # ← conflicts with graduation year below
            "stack": ["Java", "AWS", "Kubernetes"],
        }
    ],
    "education": "B.Sc. Computer Engineering, UW 2022",  # only 4 years ago
    "certifications": ["AWS Certified Developer"],
    "years_experience": 8,       # claimed; conflicts with education date
    "conflict_notes": "claimed_years_vs_graduation_mismatch",
}

_RESUME_GRACE: Dict[str, Any] = {
    "name": "Grace Patel",
    "email": "grace.p@jobs.net",
    "phone": "+1 650 555 0606",
    "address": "10 Valley Dr, Palo Alto, CA 94301",
    # CONFLICT: listed as both QA Engineer and ML Engineer in experience
    "skills": ["Selenium", "Python", "pytest", "Cypress", "BDD"],
    "experience": [
        {
            "title": "QA Engineer",
            "company": "QualityFirst",
            "years": 4,
            "stack": ["Selenium", "Java", "TestRail"],
        },
        {
            "title": "ML Engineer",    # ← role conflict — unrelated career pivot with no bridge
            "company": "AIStartup",
            "years": 4,               # overlapping dates (both simultaneous, 4 yrs each = 8 yrs but only 5 total)
            "stack": ["PyTorch", "Hugging Face"],
        },
    ],
    "education": "B.Tech QA Systems, IIT 2019",
    "certifications": [],
    "years_experience": 5,            # conflicts with 4+4 = 8 claimed above
    "conflict_notes": "overlapping_concurrent_roles",
}

_RESUME_HENRY: Dict[str, Any] = {
    "name": "Henry Osei",
    "email": "h.osei@example.org",
    "phone": "020 7946 0707",
    "address": "3 Crown Street, Manchester, UK M1 1AB",
    # Clean profile — no conflicts; keep for contrast
    "skills": ["Go", "Rust", "Distributed Systems", "gRPC", "Kubernetes"],
    "experience": [
        {
            "title": "Systems Engineer",
            "company": "InfraCore",
            "years": 6,
            "stack": ["Go", "etcd", "Prometheus"],
        }
    ],
    "education": "M.Eng. Computer Science, Manchester 2017",
    "certifications": ["CKA", "Certified Go Developer"],
    "years_experience": 6,
}


# ---------------------------------------------------------------------------
# Ground-truth answer keys (used by the grader in env.py)
# ---------------------------------------------------------------------------

GROUND_TRUTH: Dict[str, Any] = {
    "pii_easy": {
        "record_id": "r001",
        "must_redact_fields": ["phone"],
        "must_preserve_fields": ["skills", "experience", "education", "certifications"],
    },
    "pii_medium": {
        "records": {
            "r001": {"category": TechCategory.BACKEND,   "pii_fields": list(PII_FIELDS)},
            "r002": {"category": TechCategory.FRONTEND,  "pii_fields": list(PII_FIELDS)},
            "r003": {"category": TechCategory.DEVOPS,    "pii_fields": list(PII_FIELDS)},
            "r004": {"category": TechCategory.DATA,      "pii_fields": list(PII_FIELDS)},
            "r005": {"category": TechCategory.FULLSTACK, "pii_fields": list(PII_FIELDS)},
        }
    },
    "audit_hard": {
        "high_risk_ids": {"r006", "r007"},   # Frank + Grace have conflicts
        "low_risk_ids":  {"r008"},           # Henry is clean
        "conflict_types": {
            "r006": "claimed_years_vs_graduation_mismatch",
            "r007": "overlapping_concurrent_roles",
        },
    },
}


# ---------------------------------------------------------------------------
# TaskSpec builders
# ---------------------------------------------------------------------------

def _make_record(record_id: str, raw: Dict[str, Any], source: str) -> Dict[str, Any]:
    """Helper — returns a ResumeRecord-compatible dict."""
    return {"record_id": record_id, "raw": copy.deepcopy(raw), "source_file": source}


def build_easy_task() -> Dict[str, Any]:
    """
    Easy — Remove phone number from a single JSON record.
    The agent must issue exactly one Sanitize action targeting 'phone'.
    Technical skills, experience, and certifications must remain intact.
    """
    return {
        "task_id": "pii_easy",
        "difficulty": "easy",
        "description": (
            "A single resume record is presented. "
            "Remove ALL phone numbers from the record without touching "
            "any technical skills, work experience, or certifications."
        ),
        "max_steps": 5,
        "records": [
            _make_record("r001", _RESUME_ALICE, "alice_resume.json"),
        ],
        "ground_truth": GROUND_TRUTH["pii_easy"],
        "reward_scheme": {
            "pii_removal": 0.8,
            "data_loss": -0.5,
        },
    }


def build_medium_task() -> Dict[str, Any]:
    """
    Medium — Categorize 5 resumes by Tech Stack AND remove all PII (Names/Emails).
    Agent must issue both Categorize and Sanitize actions per record.
    """
    return {
        "task_id": "pii_medium",
        "difficulty": "medium",
        "description": (
            "Five resume records are presented. For each record: "
            "(1) Categorize it by its primary tech stack, and "
            "(2) Remove all PII including names, emails, phones, and addresses. "
            "Technical skills and work history must NOT be altered."
        ),
        "max_steps": 20,
        "records": [
            _make_record("r001", _RESUME_ALICE, "alice_resume.json"),
            _make_record("r002", _RESUME_BOB,   "bob_resume.json"),
            _make_record("r003", _RESUME_CAROL, "carol_resume.json"),
            _make_record("r004", _RESUME_DAN,   "dan_resume.json"),
            _make_record("r005", _RESUME_EVA,   "eva_resume.json"),
        ],
        "ground_truth": GROUND_TRUTH["pii_medium"],
        "reward_scheme": {
            "categorization": 0.2,
            "pii_removal": 0.8,
            "data_loss": -0.5,
        },
    }


def build_hard_task() -> Dict[str, Any]:
    """
    Hard — Identify conflicting information across multiple files and
    flag High-Risk profiles while keeping technical skills intact.
    Agent should:
      - Detect role/date conflicts in Frank and Grace's records.
      - Flag those two as High-Risk using a Flag action.
      - Correctly leave Henry's record un-flagged (or at Low-risk).
      - NOT delete any technical skills during flagging.
    """
    return {
        "task_id": "audit_hard",
        "difficulty": "hard",
        "description": (
            "Three resume records are presented. Analyze them for inconsistencies: "
            "mismatched employment dates, overlapping roles, or implausible claims. "
            "Flag profiles that contain conflicts as High-Risk. "
            "Profiles without conflicts should be left unflagged or flagged as Low-Risk. "
            "Under NO circumstances may technical skills be removed during this task."
        ),
        "max_steps": 15,
        "records": [
            _make_record("r006", _RESUME_FRANK, "frank_resume.json"),
            _make_record("r007", _RESUME_GRACE, "grace_resume.json"),
            _make_record("r008", _RESUME_HENRY, "henry_resume.json"),
        ],
        "ground_truth": GROUND_TRUTH["audit_hard"],
        "reward_scheme": {
            "conflict_detect": 0.3,   # per correct High-Risk flag
            "false_flag": -0.3,       # per incorrectly flagged clean record
            "data_loss": -0.5,        # per skill deleted during flagging
        },
    }


# ---------------------------------------------------------------------------
# Task registry (used by the environment)
# ---------------------------------------------------------------------------

TASK_REGISTRY: Dict[str, Dict[str, Any]] = {
    "pii_easy":   build_easy_task(),
    "pii_medium": build_medium_task(),
    "audit_hard": build_hard_task(),
}


def get_task(task_id: str) -> Dict[str, Any]:
    """Return a deep copy of the named task spec (so env state is isolated)."""
    if task_id not in TASK_REGISTRY:
        raise KeyError(
            f"Unknown task '{task_id}'. Available: {list(TASK_REGISTRY.keys())}"
        )
    return copy.deepcopy(TASK_REGISTRY[task_id])


def list_tasks() -> List[Dict[str, str]]:
    """Return a manifest-friendly list of available tasks."""
    return [
        {
            "id": spec["task_id"],
            "difficulty": spec["difficulty"],
            "description": spec["description"],
            "max_steps": str(spec["max_steps"]),
        }
        for spec in TASK_REGISTRY.values()
    ]
