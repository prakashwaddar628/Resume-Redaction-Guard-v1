"""
models.py — Talent-Audit-Env
Pydantic data models for the OpenEnv-compliant Talent Audit environment.
Covers: Observation (resume snippet), Action (agent decision), Reward (graded outcome).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
import re


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ActionType(str, Enum):
    """All legal actions an agent may take inside TalentAuditEnv."""
    SANITIZE   = "Sanitize"    # Remove / redact PII from one or more fields
    CATEGORIZE = "Categorize"  # Assign a job-role / tech-stack label
    FLAG       = "Flag"        # Mark a profile as High-Risk


class RiskLevel(str, Enum):
    LOW    = "Low"
    MEDIUM = "Medium"
    HIGH   = "High"


class TechCategory(str, Enum):
    """Canonical job-role categories used during Categorize actions."""
    FRONTEND   = "Frontend"
    BACKEND    = "Backend"
    FULLSTACK  = "Fullstack"
    DEVOPS     = "DevOps"
    DATA       = "Data / ML"
    MOBILE     = "Mobile"
    SECURITY   = "Security"
    QA         = "QA / Testing"
    MANAGEMENT = "Management"
    OTHER      = "Other"


# ---------------------------------------------------------------------------
# Observation  (environment → agent)
# ---------------------------------------------------------------------------

class ResumeRecord(BaseModel):
    """A single resume record inside an Observation."""

    record_id: str = Field(..., description="Unique identifier for this resume record.")
    raw: Dict[str, Any] = Field(
        ...,
        description=(
            "Semi-structured JSON of the resume.  May contain keys such as "
            "'name', 'email', 'phone', 'address', 'skills', 'experience', etc."
        ),
    )
    source_file: Optional[str] = Field(
        None, description="Originating filename, if loaded from disk."
    )

    # -- Derived helpers (not stored) -----------------------------------------

    def has_pii(self) -> bool:
        """Heuristic check: does raw data contain obvious PII values?"""
        pii_patterns = [
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",  # email
            r"\b(?:\+?\d[\d\s\-().]{7,}\d)\b",                            # phone
        ]
        text = str(self.raw)
        return any(re.search(p, text) for p in pii_patterns)

    def technical_skills(self) -> List[str]:
        """Extract skills / tech stack from raw data (best-effort)."""
        skills = self.raw.get("skills", [])
        if isinstance(skills, list):
            return [str(s) for s in skills]
        if isinstance(skills, str):
            return [s.strip() for s in skills.split(",")]
        return []


class Observation(BaseModel):
    """
    The full observation object handed to the agent at each step.
    It may contain one or more ResumeRecord objects (task-dependent).
    """

    task_id: str = Field(..., description="Identifier of the active task.")
    step: int = Field(0, ge=0, description="Current step index within the episode.")
    records: List[ResumeRecord] = Field(
        ..., min_length=1, description="One or more resume records to process."
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Extra context the environment may pass (e.g. cross-record conflict hints)."
        ),
    )
    done: bool = Field(False, description="True when the episode has terminated.")

    @field_validator("records")
    @classmethod
    def records_not_empty(cls, v: List[ResumeRecord]) -> List[ResumeRecord]:
        if not v:
            raise ValueError("Observation must contain at least one ResumeRecord.")
        return v


# ---------------------------------------------------------------------------
# Action  (agent → environment)
# ---------------------------------------------------------------------------

class SanitizePayload(BaseModel):
    """Payload for ActionType.SANITIZE — specifies which record + fields to redact."""

    record_id: str = Field(..., description="ID of the record to sanitize.")
    fields: List[str] = Field(
        ...,
        min_length=1,
        description="Field names to redact (e.g. ['name', 'email', 'phone']).",
    )
    replacement: str = Field(
        "[REDACTED]",
        description="Token to substitute for the original PII value.",
    )


class CategorizePayload(BaseModel):
    """Payload for ActionType.CATEGORIZE — assigns a tech-stack label to a record."""

    record_id: str = Field(..., description="ID of the record to categorize.")
    category: TechCategory = Field(
        ..., description="Assigned job-role / tech-stack category."
    )
    confidence: float = Field(
        1.0, ge=0.0, le=1.0, description="Agent's confidence in this categorization."
    )


class FlagPayload(BaseModel):
    """Payload for ActionType.FLAG — marks a profile as High-Risk."""

    record_id: str = Field(..., description="ID of the record to flag.")
    risk_level: RiskLevel = Field(..., description="Assessed risk level.")
    reason: str = Field(
        ...,
        min_length=5,
        description="Human-readable justification for flagging (min 5 chars).",
    )
    preserve_skills: bool = Field(
        True,
        description=(
            "Must remain True — technical skills MUST NOT be removed during flagging."
        ),
    )

    @field_validator("preserve_skills")
    @classmethod
    def must_preserve_skills(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "preserve_skills must be True; flagging must never delete technical skills."
            )
        return v


class Action(BaseModel):
    """
    The action object sent by the agent to TalentAuditEnv.step().
    Exactly one of sanitize / categorize / flag must be populated.
    """

    action_type: ActionType
    sanitize: Optional[SanitizePayload]   = None
    categorize: Optional[CategorizePayload] = None
    flag: Optional[FlagPayload]           = None

    @model_validator(mode="after")
    def payload_consistency(self) -> "Action":
        mapping = {
            ActionType.SANITIZE:   self.sanitize,
            ActionType.CATEGORIZE: self.categorize,
            ActionType.FLAG:       self.flag,
        }
        active = mapping[self.action_type]
        if active is None:
            raise ValueError(
                f"action_type is '{self.action_type}' but the corresponding "
                f"payload field is None."
            )
        # Ensure no unrelated payload is populated
        for atype, payload in mapping.items():
            if atype != self.action_type and payload is not None:
                raise ValueError(
                    f"action_type is '{self.action_type}' but payload for "
                    f"'{atype}' is also set — only one payload is allowed."
                )
        return self

    # -- Convenience constructors --------------------------------------------

    @classmethod
    def sanitize_action(
        cls,
        record_id: str,
        fields: List[str],
        replacement: str = "[REDACTED]",
    ) -> "Action":
        return cls(
            action_type=ActionType.SANITIZE,
            sanitize=SanitizePayload(
                record_id=record_id, fields=fields, replacement=replacement
            ),
        )

    @classmethod
    def categorize_action(
        cls,
        record_id: str,
        category: Union[TechCategory, str],
        confidence: float = 1.0,
    ) -> "Action":
        return cls(
            action_type=ActionType.CATEGORIZE,
            categorize=CategorizePayload(
                record_id=record_id,
                category=TechCategory(category),
                confidence=confidence,
            ),
        )

    @classmethod
    def flag_action(
        cls,
        record_id: str,
        risk_level: Union[RiskLevel, str],
        reason: str,
    ) -> "Action":
        return cls(
            action_type=ActionType.FLAG,
            flag=FlagPayload(
                record_id=record_id,
                risk_level=RiskLevel(risk_level),
                reason=reason,
                preserve_skills=True,
            ),
        )


# ---------------------------------------------------------------------------
# Reward  (environment → agent, returned by step())
# ---------------------------------------------------------------------------

class RewardBreakdown(BaseModel):
    """Granular reward components for interpretability."""

    categorization:  float = Field(0.0, description="+0.2 per correct categorization.")
    pii_removal:     float = Field(0.0, description="+0.8 per successful PII removal.")
    data_loss:       float = Field(0.0, description="-0.5 per accidental skill deletion.")
    conflict_detect: float = Field(0.0, description="+0.3 for correct conflict detection.")
    false_flag:      float = Field(0.0, description="-0.3 for incorrect risk flagging.")


class Reward(BaseModel):
    """
    Full reward signal returned after each step.
    total = sum of all breakdown components.
    """

    total: float = Field(0.0, description="Aggregated scalar reward for this step.")
    breakdown: RewardBreakdown = Field(default_factory=RewardBreakdown)
    feedback: str = Field("", description="Natural-language feedback from the grader.")
    is_terminal: bool = Field(
        False, description="True when this reward ends the episode."
    )

    @model_validator(mode="after")
    def sync_total(self) -> "Reward":
        bd = self.breakdown
        computed = (
            bd.categorization
            + bd.pii_removal
            + bd.data_loss
            + bd.conflict_detect
            + bd.false_flag
        )
        # Allow caller to override total; if zero and breakdown nonzero → sync
        if self.total == 0.0 and computed != 0.0:
            object.__setattr__(self, "total", round(computed, 4))
        return self

    # -- Convenience constructors --------------------------------------------

    @classmethod
    def for_correct_categorization(cls, feedback: str = "") -> "Reward":
        bd = RewardBreakdown(categorization=0.2)
        return cls(total=0.2, breakdown=bd, feedback=feedback or "Correct categorization.")

    @classmethod
    def for_pii_removal(cls, feedback: str = "") -> "Reward":
        bd = RewardBreakdown(pii_removal=0.8)
        return cls(total=0.8, breakdown=bd, feedback=feedback or "PII successfully removed.")

    @classmethod
    def for_data_loss(cls, feedback: str = "") -> "Reward":
        bd = RewardBreakdown(data_loss=-0.5)
        return cls(
            total=-0.5,
            breakdown=bd,
            feedback=feedback or "Data loss: technical skill deleted accidentally.",
        )

    @classmethod
    def zero(cls, feedback: str = "") -> "Reward":
        return cls(total=0.0, feedback=feedback)
