
"""
Radiology Information Systems Multi-Agent Workflow

A Mistral AI Studio-compatible multi-agent workflow based on the ris-assist-opengap
repository (https://github.com/b08x/ris-assist-opengap).

This workflow implements the same architecture as the OpenGAP specification:
- Orchestrator (ris-assist) classifies intake and delegates to specialist agents
- Triage agent: Differential-driven ticket clarification
- Communications agent: Incident communication drafting  
- Knowledge Base agent: KB article generation from resolved incidents

Key Features:
- Strict segregation of duties (SOD) - agents draft, humans approve
- Read-only access to production systems (no state-changing actions)
- All artifacts require human approval before release
- Confidence marking on all conclusions (confirmed/likely/possible)
- Outstanding items tracking for incomplete information
- Site profile integration for site-specific knowledge

Mistral AI Studio Integration:
    This workflow is designed to work with Mistral AI Studio's Managed Agents
    and can be deployed using the Agents SDK.

Usage:
    # Local testing
    python workflows/ris_multi_agent_workflow.py
    
    # Deploy with Mistral Studio
    agents deploy --config config/deployment.yaml

Ported from: github.com/b08x/ris-assist (Claude Code plugin)
OpenGAP template: github.com/b08x/ris-assist-opengap
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class AgentType(Enum):
    """Agent types in the RIS multi-agent system."""
    ORCHESTRATOR = "orchestrator"
    TRIAGE = "triage"
    COMMS = "comms"
    KB = "kb"


class SeverityLevel(Enum):
    """Severity levels for radiology IT incidents (from site profile SLA tiers)."""
    SEV1 = "SEV1"
    SEV2 = "SEV2"  
    SEV3 = "SEV3"
    SEV4 = "SEV4"


class Audience(Enum):
    """Audience types for communications (from SOUL.md audience register)."""
    CLINICAL = "clinical"
    TECHNICAL = "technical"
    LEADERSHIP = "leadership"
    VENDOR = "vendor"


class WorkflowTrigger(Enum):
    """Triggers for workflow activation (from agent.yaml delegation triggers)."""
    NEW_TICKET = "new_ticket"
    ESCALATION_REQUEST = "escalation_request"
    DOWNTIME_ALERT = "downtime_alert"
    INCIDENT_UPDATE = "incident_update"
    ALL_CLEAR = "all_clear"
    VENDOR_TICKET = "vendor_ticket"
    CHANGE_NARRATIVE = "change_narrative"
    SHIFT_TURNOVER = "shift_turnover"
    INCIDENT_RESOLVED = "incident_resolved"
    RECURRING_SYMPTOM = "recurring_symptom"
    STALE_CHECK = "stale_check"


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class SiteProfile:
    """Site-specific configuration and context (from onboarding skill)."""
    systems: List[str] = field(default_factory=list)
    interfaces: List[str] = field(default_factory=list)
    identifier_formats: Dict[str, str] = field(default_factory=dict)
    sla_tiers: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    escalation_matrix: Dict[str, List[str]] = field(default_factory=dict)
    downtime_procedures: Dict[str, str] = field(default_factory=dict)
    notification_templates: Dict[str, str] = field(default_factory=dict)


@dataclass  
class Ticket:
    """Represents a radiology IT support ticket."""
    ticket_id: str
    title: str
    description: str
    reported_by: str
    reported_at: str
    systems_affected: List[str] = field(default_factory=list)
    severity: Optional[SeverityLevel] = None
    status: str = "NEW"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DifferentialItem:
    """A single item in the differential diagnosis."""
    diagnosis: str
    confidence: str  # confirmed, likely, possible
    evidence: str


@dataclass
class TriageArtifact:
    """Output from the triage agent (from workflows/triage-flow.yaml)."""
    ticket_id: str
    scope: str
    timeline: str
    recommended_queue: str
    severity_justification: str
    differential: List[DifferentialItem] = field(default_factory=list)
    escalation_package: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    outstanding_items: List[str] = field(default_factory=list)


@dataclass
class CommunicationDraft:
    """Output from the communications agent (from workflows/comms-draft-flow.yaml)."""
    event_type: str
    audience: Audience
    channel: str
    subject: str
    body: str
    variant_key: str
    template_used: str
    outstanding_items: List[str] = field(default_factory=list)
    approval_chain: List[str] = field(default_factory=list)
    is_update: bool = False


@dataclass
class KBArticle:
    """Output from the knowledge base agent (from workflows/kb-draft-flow.yaml)."""
    title: str
    article_id: str
    content_html: str
    scope: str
    cause: str
    cause_confidence: str  # confirmed/likely/possible
    content_docx: Optional[bytes] = None
    layers: List[str] = field(default_factory=list)
    field_checklist: Dict[str, bool] = field(default_factory=dict)
    outstanding_items: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ApprovalPackage:
    """Package for human approval handoff (from DUTIES.md)."""
    artifact: Any
    reasoning: str
    gate: str  # notification_release, kb_submission, severity_commit, escalation_page
    requires_approval: bool = True
    dead_branches: List[Dict[str, Any]] = field(default_factory=list)
    outstanding_items: List[str] = field(default_factory=list)
    approval_chain: List[str] = field(default_factory=list)
