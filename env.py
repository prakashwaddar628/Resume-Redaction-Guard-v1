"""
env.py — Talent-Audit-Env
OpenEnv-compliant environment class: TalentAuditEnv.

Implements:
  reset(task_id)  → Observation
  step(action)    → (Observation, Reward, done, info)
  state()         → dict

Reward logic:
  +0.2  correct categorization
  +0.8  successful PII removal (all targeted PII gone, no skills lost)
  -0.5  data loss (technical skill deleted accidentally)
  +0.3  correct conflict/High-Risk detection  (hard task)
  -0.3  false flag  (incorrectly flagging a clean record)
"""

from __future__ import annotations

import copy
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from models import (
    Action,
    ActionType,
    Observation,
    Reward,
    RewardBreakdown,
    ResumeRecord,
    RiskLevel,
    TechCategory,
)
from tasks import PII_FIELDS, get_task


# ---------------------------------------------------------------------------
# PII detection helpers
# ---------------------------------------------------------------------------

_PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(
        r"(?:(?:\+?\d{1,3}[\s\-.]?)?"
        r"(?:\(?\d{1,4}\)?)[\s\-.]?"
        r"\d{3,5}[\s\-.]?\d{4,6})"
    ),
}

_TECH_SKILL_KEYWORDS: Set[str] = {
    # Languages
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
    "ruby", "swift", "kotlin", "scala", "r", "bash", "shell", "haskell",
    # Frameworks / libs
    "react", "vue", "angular", "svelte", "next.js", "nuxt", "fastapi",
    "django", "flask", "spring", "express.js", "node.js", "rails",
    # DevOps / Infra
    "docker", "kubernetes", "terraform", "ansible", "jenkins", "helm",
    "argocd", "github actions", "gitlab ci", "aws", "gcp", "azure",
    "linux", "nginx", "prometheus", "grafana",
    # Data / ML
    "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy", "spark",
    "airflow", "mlflow", "hugging face", "sql", "postgresql", "mongodb",
    "redis", "kafka", "elasticsearch",
    # Misc
    "graphql", "grpc", "rest", "microservices", "ci/cd", "etcd",
}


def _contains_pii(value: Any) -> bool:
    text = str(value)
    return any(p.search(text) for p in _PII_PATTERNS.values())


# Fields that contain ONLY PII and must never be treated as technical
_STRICT_PII_FIELDS: Set[str] = {
    "name", "email", "phone", "address", "linkedin",
    "github_personal", "mobile", "tel", "contact",
}

# Fields that are definitively technical (never PII)
_STRICT_TECH_FIELDS: Set[str] = {
    "skills", "experience", "certifications", "education",
    "projects", "tech_stack", "stack", "years_experience",
}


def _is_technical_field(field_name: str, value: Any) -> bool:
    """Return True only if a field definitively holds technical / professional data."""
    fname = field_name.lower()
    # Hard deny: PII-only fields are never technical
    if fname in _STRICT_PII_FIELDS:
        return False
    # Hard allow: well-known technical fields
    if fname in _STRICT_TECH_FIELDS:
        return True
    # Heuristic for unknown fields
    text = str(value).lower()
    return any(kw in text for kw in _TECH_SKILL_KEYWORDS)


def _redact_value(value: Any, replacement: str) -> Any:
    """Return a redacted copy of value (works for str, list, nested dict)."""
    if isinstance(value, str):
        return replacement
    if isinstance(value, list):
        return [replacement if not _is_technical_field("", item) else item for item in value]
    if isinstance(value, dict):
        # Redact only string leaves that look like PII
        result = {}
        for k, v in value.items():
            result[k] = replacement if isinstance(v, str) and _contains_pii(v) else v
        return result
    return replacement


# ---------------------------------------------------------------------------
# Grader helpers
# ---------------------------------------------------------------------------

def _skills_intact(original: Dict[str, Any], current: Dict[str, Any]) -> bool:
    """Return True if the 'skills' list is unchanged."""
    return original.get("skills", []) == current.get("skills", [])


def _experience_intact(original: Dict[str, Any], current: Dict[str, Any]) -> bool:
    """Return True if the 'experience' block is unchanged."""
    return original.get("experience", []) == current.get("experience", [])


def _pii_removed(raw: Dict[str, Any], target_fields: List[str]) -> bool:
    """Return True when all target fields are [REDACTED] or absent."""
    for field in target_fields:
        value = raw.get(field, "[REDACTED]")
        if isinstance(value, str) and _contains_pii(value):
            return False
        if isinstance(value, str) and value not in ("[REDACTED]", "", "N/A"):
            # Field present and non-empty — may still have PII
            if field.lower() in {"name", "email", "phone", "address", "linkedin"}:
                return False
    return True


# ---------------------------------------------------------------------------
# TalentAuditEnv
# ---------------------------------------------------------------------------

class TalentAuditEnv:
    """
    OpenEnv-compliant environment for Automated HR Data Compliance auditing.

    Lifecycle
    ---------
    env = TalentAuditEnv()
    obs = env.reset("pii_easy")
    while not done:
        action = agent.act(obs)
        obs, reward, done, info = env.step(action)
    summary = env.state()
    """

    ENV_NAME    = "talent-audit-env"
    ENV_VERSION = "1.0.0"

    def __init__(self) -> None:
        self._task_spec: Optional[Dict[str, Any]] = None
        self._episode_id: Optional[str] = None

        # Working copies of records {record_id: raw_dict}
        self._records:          Dict[str, Dict[str, Any]] = {}
        self._original_records: Dict[str, Dict[str, Any]] = {}

        # Per-record bookkeeping
        self._categorized: Dict[str, TechCategory] = {}
        self._flagged:     Dict[str, RiskLevel]    = {}

        # Episode tracking
        self._step_count:   int   = 0
        self._total_reward: float = 0.0
        self._done:         bool  = True
        self._history:      List[Dict[str, Any]] = []
        self._started_at:   Optional[float] = None

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def reset(self, task_id: str = "pii_easy") -> Observation:
        """
        Begin a new episode for the specified task.

        Parameters
        ----------
        task_id : one of 'pii_easy', 'pii_medium', 'audit_hard'

        Returns
        -------
        Observation  — the initial observation.
        """
        self._task_spec = get_task(task_id)
        self._episode_id = str(uuid.uuid4())

        self._records = {}
        self._original_records = {}
        for rec_dict in self._task_spec["records"]:
            rid = rec_dict["record_id"]
            raw = copy.deepcopy(rec_dict["raw"])
            self._records[rid] = raw
            self._original_records[rid] = copy.deepcopy(raw)

        self._categorized  = {}
        self._flagged      = {}
        self._step_count   = 0
        self._total_reward = 0.0
        self._done         = False
        self._history      = []
        self._started_at   = time.time()

        return self._build_observation()

    def step(self, action: Action) -> Tuple[Observation, Reward, bool, Dict[str, Any]]:
        """
        Apply an agent action to the environment.

        Parameters
        ----------
        action : Action  — validated Action model instance.

        Returns
        -------
        observation : Observation
        reward      : Reward
        done        : bool
        info        : dict  (diagnostic metadata)
        """
        if self._done:
            raise RuntimeError(
                "Episode is done. Call reset() before stepping."
            )
        if self._task_spec is None:
            raise RuntimeError("Environment not initialised. Call reset() first.")

        self._step_count += 1
        max_steps = self._task_spec["max_steps"]

        reward, info = self._apply_action(action)
        self._total_reward = round(self._total_reward + reward.total, 4)

        # Record history entry
        self._history.append({
            "step": self._step_count,
            "action_type": action.action_type.value,
            "reward": reward.total,
            "feedback": reward.feedback,
        })

        # Check terminal conditions
        if self._step_count >= max_steps:
            self._done = True
            reward.is_terminal = True
            info["termination_reason"] = "max_steps_reached"

        obs = self._build_observation()
        return obs, reward, self._done, info

    def state(self) -> Dict[str, Any]:
        """
        Return the complete current state of the environment.
        Useful for debugging, logging, and post-episode analysis.
        """
        return {
            "env_name":      self.ENV_NAME,
            "env_version":   self.ENV_VERSION,
            "episode_id":    self._episode_id,
            "task_id":       self._task_spec["task_id"] if self._task_spec else None,
            "difficulty":    self._task_spec["difficulty"] if self._task_spec else None,
            "step_count":    self._step_count,
            "total_reward":  self._total_reward,
            "done":          self._done,
            "records":       copy.deepcopy(self._records),
            "categorized":   {k: v.value for k, v in self._categorized.items()},
            "flagged":       {k: v.value for k, v in self._flagged.items()},
            "history":       list(self._history),
            "elapsed_s":     round(time.time() - self._started_at, 3)
                             if self._started_at else None,
        }

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _build_observation(self) -> Observation:
        resume_records = [
            ResumeRecord(
                record_id=rid,
                raw=copy.deepcopy(raw),
                source_file=next(
                    (r["source_file"] for r in self._task_spec["records"]
                     if r["record_id"] == rid),
                    None,
                ),
            )
            for rid, raw in self._records.items()
        ]
        return Observation(
            task_id=self._task_spec["task_id"],
            step=self._step_count,
            records=resume_records,
            context={
                "difficulty":   self._task_spec["difficulty"],
                "max_steps":    self._task_spec["max_steps"],
                "description":  self._task_spec["description"],
                "categorized":  {k: v.value for k, v in self._categorized.items()},
                "flagged":      {k: v.value for k, v in self._flagged.items()},
            },
            done=self._done,
        )

    def _apply_action(
        self, action: Action
    ) -> Tuple[Reward, Dict[str, Any]]:
        """
        Route action to the appropriate grader and return (Reward, info).
        """
        if action.action_type == ActionType.SANITIZE:
            return self._grade_sanitize(action)
        if action.action_type == ActionType.CATEGORIZE:
            return self._grade_categorize(action)
        if action.action_type == ActionType.FLAG:
            return self._grade_flag(action)
        raise ValueError(f"Unhandled action type: {action.action_type}")

    # -- Sanitize grader -----------------------------------------------------

    def _grade_sanitize(
        self, action: Action
    ) -> Tuple[Reward, Dict[str, Any]]:
        payload = action.sanitize
        rid = payload.record_id

        if rid not in self._records:
            return (
                Reward.zero(feedback=f"Unknown record_id '{rid}'."),
                {"error": "unknown_record"},
            )

        raw      = self._records[rid]
        original = self._original_records[rid]
        fields   = payload.fields
        repl     = payload.replacement

        data_loss      = 0.0
        pii_removed    = 0.0
        lost_skills    = []
        redacted_count = 0
        info: Dict[str, Any] = {"record_id": rid, "fields_targeted": fields}

        for field in fields:
            if field not in raw:
                info.setdefault("warnings", []).append(f"Field '{field}' not found.")
                continue

            # ── Data-loss check ─────────────────────────────────────────────
            if _is_technical_field(field, raw[field]):
                data_loss -= 0.5
                lost_skills.append(field)
                # Still redact — to observe, but penalise
                raw[field] = repl
                info.setdefault("data_loss", []).append(field)
                continue

            # ── Actually redact ──────────────────────────────────────────────
            raw[field] = repl
            redacted_count += 1

        # Skills / experience still intact?
        if not _skills_intact(original, raw) and "skills" not in fields:
            data_loss -= 0.5
            info["warning"] = "Skills list was inadvertently altered."

        # Evaluate PII removal quality ─────────────────────────────────────
        # +0.8 if at least one PII field was cleanly redacted with no data loss
        task_gt = self._task_spec["ground_truth"]
        record_gt = task_gt.get("records", {}).get(rid, {})
        pii_must: List[str] = record_gt.get(
            "pii_fields", task_gt.get("must_redact_fields", [])
        )

        # Count how many of the requested fields were legitimate PII (not tech)
        clean_pii_redacted = redacted_count  # fields we redacted without penalty
        if clean_pii_redacted > 0 and data_loss == 0.0:
            # Award per-step reward for safe PII removal
            pii_removed += 0.8
        elif clean_pii_redacted > 0 and data_loss < 0.0:
            # Partial: some PII removed but also caused data loss
            pii_removed += 0.4

        # Build reward
        bd = RewardBreakdown(
            pii_removal=pii_removed,
            data_loss=data_loss,
        )
        total = round(pii_removed + data_loss, 4)
        feedback_parts = []
        if pii_removed > 0:
            feedback_parts.append(f"PII removed from {clean_pii_redacted} field(s).")
        if lost_skills:
            feedback_parts.append(
                f"DATA LOSS: technical field(s) {lost_skills} were redacted."
            )
        if not feedback_parts:
            feedback_parts.append("No PII redacted (check field list or field is already clean).")

        reward = Reward(
            total=total,
            breakdown=bd,
            feedback=" ".join(feedback_parts),
        )
        info["reward_total"] = total
        return reward, info

    # -- Categorize grader ---------------------------------------------------

    def _grade_categorize(
        self, action: Action
    ) -> Tuple[Reward, Dict[str, Any]]:
        payload = action.categorize
        rid     = payload.record_id
        cat     = payload.category

        if rid not in self._records:
            return (
                Reward.zero(feedback=f"Unknown record_id '{rid}'."),
                {"error": "unknown_record"},
            )

        if rid in self._categorized:
            return (
                Reward.zero(feedback=f"Record '{rid}' already categorised."),
                {"warning": "duplicate_categorize"},
            )

        # Check against ground truth
        task_gt  = self._task_spec["ground_truth"]
        gt_records = task_gt.get("records", {})
        correct_cat: Optional[TechCategory] = None

        if rid in gt_records:
            correct_cat = gt_records[rid].get("category")

        self._categorized[rid] = cat

        if correct_cat is not None and cat == correct_cat:
            reward = Reward(
                total=0.2,
                breakdown=RewardBreakdown(categorization=0.2),
                feedback=f"Correct! '{rid}' is {cat.value}.",
            )
            return reward, {"record_id": rid, "category": cat.value, "correct": True}
        elif correct_cat is not None:
            reward = Reward.zero(
                feedback=(
                    f"Incorrect category for '{rid}'. "
                    f"Got {cat.value}, expected {correct_cat.value}."
                )
            )
            return reward, {"record_id": rid, "category": cat.value, "correct": False}
        else:
            # Hard task — no category GT; still record
            reward = Reward(
                total=0.1,
                breakdown=RewardBreakdown(categorization=0.1),
                feedback=f"Categorised '{rid}' as {cat.value} (no GT to verify).",
            )
            return reward, {"record_id": rid, "category": cat.value, "correct": None}

    # -- Flag grader ---------------------------------------------------------

    def _grade_flag(
        self, action: Action
    ) -> Tuple[Reward, Dict[str, Any]]:
        payload    = action.flag
        rid        = payload.record_id
        risk_level = payload.risk_level

        if rid not in self._records:
            return (
                Reward.zero(feedback=f"Unknown record_id '{rid}'."),
                {"error": "unknown_record"},
            )

        raw      = self._records[rid]
        original = self._original_records[rid]

        # Verify skills not touched
        if not _skills_intact(original, raw):
            bd = RewardBreakdown(data_loss=-0.5)
            return (
                Reward(
                    total=-0.5,
                    breakdown=bd,
                    feedback="DATA LOSS: skills were modified during flagging.",
                ),
                {"record_id": rid, "data_loss": True},
            )

        task_gt       = self._task_spec["ground_truth"]
        high_risk_ids = task_gt.get("high_risk_ids", set())
        low_risk_ids  = task_gt.get("low_risk_ids",  set())

        self._flagged[rid] = risk_level

        # Correct High-Risk flag
        if rid in high_risk_ids and risk_level == RiskLevel.HIGH:
            bd = RewardBreakdown(conflict_detect=0.3)
            reward = Reward(
                total=0.3,
                breakdown=bd,
                feedback=(
                    f"Correct! '{rid}' is High-Risk. "
                    f"Reason accepted: {payload.reason[:80]}"
                ),
            )
            return reward, {"record_id": rid, "correct_flag": True}

        # False positive — clean record incorrectly flagged as High-Risk
        if rid in low_risk_ids and risk_level == RiskLevel.HIGH:
            bd = RewardBreakdown(false_flag=-0.3)
            reward = Reward(
                total=-0.3,
                breakdown=bd,
                feedback=f"False flag: '{rid}' is a clean record.",
            )
            return reward, {"record_id": rid, "false_positive": True}

        # Mild penalty for under-flagging a known High-Risk record
        if rid in high_risk_ids and risk_level != RiskLevel.HIGH:
            reward = Reward.zero(
                feedback=(
                    f"Under-flagged '{rid}': should be High-Risk, "
                    f"got {risk_level.value}."
                )
            )
            return reward, {"record_id": rid, "under_flagged": True}

        # Neutral — no GT information for this record
        reward = Reward.zero(feedback=f"Flagged '{rid}' as {risk_level.value} (no GT).")
        return reward, {"record_id": rid, "correct_flag": None}
