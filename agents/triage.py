
"""
RIS Assist Orchestrator Agent

The main orchestrator for the Radiology Information Systems multi-agent workflow.
This agent classifies intake, delegates to specialist agents, aggregates results,
and hands every artifact to a human approver.

Model: claude-opus-4-6 (fallback: claude-sonnet-4-5)
Skills: explainer, onboarding
"""

import asyncio
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from workflows.ris_data_models import (
    AgentType,
    ApprovalPackage,
    Audience,
    CommunicationDraft,
    KBArticle,
    SeverityLevel,
    SiteProfile,
    Ticket,
    TriageArtifact,
    WorkflowTrigger,
)


class TriageAgent:
    """
    Differential-driven ticket clarification specialist.
    
    Asks the single most discriminating question at a time until the ticket
    is routable, then produces a triage artifact with scope, timeline,
    confidence-marked differential, recommended queue, and SLA-vocabulary
    severity justification.
    
    Model: claude-haiku-4-5 (fallback: claude-sonnet-4-5)
    Skill: troubleshoot
    """
    
    def __init__(self, site_profile: Optional[SiteProfile] = None):
        self.site_profile = site_profile or SiteProfile()
        self.name = AgentType.TRIAGE.value
        self.description = "Differential-driven ticket clarification for radiology IT support"
        self.model_preferred = "claude-haiku-4-5"
        self.model_fallback = ["claude-sonnet-4-5"]
        
    def classify_ticket(self, ticket: Ticket) -> Dict[str, Any]:
        """
        Normalize ticket text; extract stated scope, timeline, symptoms.
        
        This is the first step in the triage workflow (workflows/triage-flow.yaml).
        """
        # Extract scope from description
        scope = self._extract_scope(ticket.description)
        
        # Extract timeline
        timeline = self._extract_timeline(ticket.description)
        
        # Extract symptoms
        symptoms = self._extract_symptoms(ticket.description)
        
        # Extract stated facts
        stated_facts = self._extract_facts(ticket.description)
        
        return {
            "normalized_ticket": {
                "ticket_id": ticket.ticket_id,
                "title": ticket.title,
                "description": ticket.description,
                "scope": scope,
                "timeline": timeline,
                "symptoms": symptoms,
                "stated_facts": stated_facts
            },
            "scope": scope,
            "timeline": timeline,
            "symptoms": symptoms,
            "stated_facts": stated_facts
        }
    
    def _extract_scope(self, description: str) -> str:
        """Extract the scope from ticket description."""
        # Look for system names
        systems = ["RIS", "PACS", "EHR", "HL7", "CT", "MRI", "Modality", "Interface"]
        found = [s for s in systems if s in description]
        if found:
            return f"{', '.join(found)} affected"
        return "General system issue"
    
    def _extract_timeline(self, description: str) -> str:
        """Extract timeline information."""
        # Look for time indicators
        time_keywords = ["started", "since", "for", "hours", "minutes", "days"]
        lines = description.split("\n")
        for line in lines:
            if any(kw in line.lower() for kw in time_keywords):
                return line.strip()
        return "Timeline not specified"
    
    def _extract_symptoms(self, description: str) -> List[str]:
        """Extract symptoms from description."""
        # Split by sentences/lines and look for action verbs
        symptoms = []
        lines = description.split("\n")
        for line in lines:
            line_lower = line.lower()
            if any(verb in line_lower for verb in ["not", "cannot", "failing", "error", "down", "unavailable"]):
                symptoms.append(line.strip())
        return symptoms if symptoms else ["Symptoms not clearly stated"]
    
    def _extract_facts(self, description: str) -> List[str]:
        """Extract explicitly stated facts."""
        facts = []
        lines = description.split("\n")
        for line in lines:
            line_lower = line.lower()
            # Look for factual statements
            if any(kw in line_lower for kw in ["no recent", "affecting", "only", "confirmed", "verified"]):
                facts.append(line.strip())
        return facts if facts else ["No explicit facts stated"]
    
    def get_site_context(self, profile_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Read-only lookup of systems, interfaces, identifier_formats,
        sla_tiers, escalation_matrix, downtime_procedures.
        
        This is step 2 in the triage workflow.
        """
        # If profile_path is provided, would read from there
        # For now, use the site_profile passed to constructor
        return {
            "systems": self.site_profile.systems,
            "interfaces": self.site_profile.interfaces,
            "identifier_formats": self.site_profile.identifier_formats,
            "sla_tiers": self.site_profile.sla_tiers,
            "escalation_matrix": self.site_profile.escalation_matrix,
            "downtime_procedures": self.site_profile.downtime_procedures
        }
    
    def ask_discriminating_question(
        self, 
        normalized_ticket: Dict[str, Any],
        site_context: Dict[str, Any],
        operating_context: str = "night_shift"
    ) -> Tuple[str, bool]:
        """
        Ask the single most discriminating question at a time.
        
        Night shift: ask the change-window question first - it inverts the
        differential prior, and the prior still carries a likely/possible mark.
        
        Returns: (question, is_routable)
        """
        # Check if we should ask about change window
        asked_questions = normalized_ticket.get("asked_questions", [])
        
        if "change_window" not in asked_questions:
            return "Was there any recent change or maintenance window that might be related?", False
        
        # Check if ticket is routable
        if self._is_routable(normalized_ticket, site_context):
            return "", True  # No more questions, it's routable
        
        # Ask next discriminating question based on scope
        scope = normalized_ticket.get("scope", "")
        if "PACS" in scope:
            return "Are other modalities (MRI, CT, etc.) also affected, or only specific ones?", False
        elif "RIS" in scope:
            return "Is this affecting all users or specific ones?", False
        elif "HL7" in scope or "interface" in scope.lower():
            return "Which specific interface is experiencing issues?", False
        else:
            return "Which systems are you unable to access?", False
    
    def _is_routable(self, normalized_ticket: Dict[str, Any], site_context: Dict[str, Any]) -> bool:
        """Determine if the ticket is routable based on confidence."""
        # Check if we have enough information
        scope = normalized_ticket.get("scope", "")
        symptoms = normalized_ticket.get("symptoms", [])
        
        # If we have clear scope and symptoms, it might be routable
        if scope and len(symptoms) > 0:
            # Check if we can map to a known queue
            systems = site_context.get("systems", [])
            for system in systems:
                if system in scope:
                    return True
        
        return False
    
    def justify_severity(
        self, 
        normalized_ticket: Dict[str, Any], 
        site_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Justify severity in the site's own SLA vocabulary, citing sla_tiers,
        or state that no matching tier exists.
        
        This is step 4 in the triage workflow.
        """
        scope = normalized_ticket.get("scope", "")
        symptoms = normalized_ticket.get("symptoms", [])
        description = normalized_ticket.get("description", "")
        
        sla_tiers = site_context.get("sla_tiers", {})
        
        # Determine severity based on impact
        severity = SeverityLevel.SEV3
        justification = ""
        
        # Check for SEV1 criteria (production down, clinical impact)
        if any(kw in description.lower() for kw in ["downtime", "unavailable", "cannot access"]):
            if any(kw in scope for kw in ["PACS", "RIS", "EHR"]):
                severity = SeverityLevel.SEV1
                justification = f"SEV1: Production system downtime. Matches sla_tiers['{severity.value}']: {sla_tiers.get(severity.value, {}).get('description', 'Immediate response required')}"
        
        # Check for SEV2 criteria (degraded service, partial outage)
        elif any(kw in description.lower() for kw in ["intermittent", "slow", "degraded", "some users"]):
            severity = SeverityLevel.SEV2
            justification = f"SEV2: Degraded service. Matches sla_tiers['{severity.value}']: {sla_tiers.get(severity.value, {}).get('description', 'Degraded service')}"
        
        # Default to SEV3
        else:
            severity = SeverityLevel.SEV3
            justification = f"SEV3: Minor issue. Matches sla_tiers['{severity.value}']: {sla_tiers.get(severity.value, {}).get('description', 'Minor impact')}"
        
        return {
            "severity": severity,
            "justification": justification
        }
    
    def create_triage_artifact(
        self,
        ticket: Ticket,
        site_context: Dict[str, Any],
        operating_context: str = "night_shift"
    ) -> TriageArtifact:
        """
        Create a complete triage artifact.
        
        This combines steps 3-5 of the triage workflow and returns the final
        artifact with all required fields.
        """
        # Step 1: Classify
        classification = self.classify_ticket(ticket)
        
        # Step 2: Build differential
        differential = self._build_differential(classification, site_context)
        
        # Step 3: Determine recommended queue
        recommended_queue = self._determine_queue(classification, site_context)
        
        # Step 4: Justify severity
        severity_result = self.justify_severity(classification, site_context)
        
        # Step 5: Create artifact
        return TriageArtifact(
            ticket_id=ticket.ticket_id,
            scope=classification["scope"],
            timeline=classification["timeline"],
            differential=differential,
            recommended_queue=recommended_queue,
            severity_justification=severity_result["justification"],
            confidence=0.85,  # Would be calculated based on information completeness
            outstanding_items=self._get_outstanding_items(classification, site_context)
        )
    
    def _build_differential(
        self, 
        classification: Dict[str, Any], 
        site_context: Dict[str, Any]
    ) -> List[Any]:
        """Build a confidence-marked differential diagnosis."""
        scope = classification.get("scope", "")
        symptoms = classification.get("symptoms", [])
        
        differential = []
        
        # Add likely diagnoses based on scope and symptoms
        if "PACS" in scope and any("not appearing" in s.lower() for s in symptoms):
            differential.append({
                "diagnosis": "PACS connectivity issue",
                "confidence": "likely",
                "evidence": "Studies not appearing in PACS"
            })
            differential.append({
                "diagnosis": "RIS order status mismatch",
                "confidence": "possible",
                "evidence": "RIS shows order as completed"
            })
        elif "RIS" in scope:
            differential.append({
                "diagnosis": "RIS database issue",
                "confidence": "likely",
                "evidence": "Orders not processing correctly"
            })
        elif any("interface" in s.lower() for s in [scope] + symptoms):
            differential.append({
                "diagnosis": "HL7 interface problem",
                "confidence": "likely",
                "evidence": "Interface-related symptoms"
            })
        
        # Add dead branches (things we ruled out)
        # In a real implementation, these would be tracked during Q&A
        
        return differential
    
    def _determine_queue(
        self, 
        classification: Dict[str, Any], 
        site_context: Dict[str, Any]
    ) -> str:
        """Determine the recommended queue based on scope."""
        scope = classification.get("scope", "")
        escalation_matrix = site_context.get("escalation_matrix", {})
        
        if "PACS" in scope:
            return "PACS_Team"
        elif "RIS" in scope:
            return "RIS_Team"
        elif any(kw in scope for kw in ["HL7", "interface", "Integration"]):
            return "Interface_Team"
        elif "CT" in scope or "MRI" in scope:
            return "Modality_Team"
        else:
            return "General_Support"
    
    def _get_outstanding_items(
        self, 
        classification: Dict[str, Any], 
        site_context: Dict[str, Any]
    ) -> List[str]:
        """Identify outstanding items that need clarification."""
        outstanding = []
        
        # Check if change window was asked
        # In a real implementation, we'd track asked questions
        outstanding.append("Confirm if any recent changes were made")
        
        # Check scope clarity
        scope = classification.get("scope", "")
        if scope == "General system issue":
            outstanding.append("Clarify which specific systems are affected")
        
        # Check timeline
        timeline = classification.get("timeline", "")
        if timeline == "Timeline not specified":
            outstanding.append("Determine when the issue started")
        
        return outstanding
    
    def create_approval_package(
        self, 
        artifact: TriageArtifact,
        severity_justification: str
    ) -> ApprovalPackage:
        """
        Package triage artifact, severity justification, and dead-branch
        reasoning for the human approver.
        
        Gate: severity_commit (DUTIES.md)
        """
        return ApprovalPackage(
            artifact=artifact,
            reasoning=f"Triage completed with confidence {artifact.confidence}. "
                     f"Recommended queue: {artifact.recommended_queue}",
            dead_branches=[
                {
                    "path": "change_window",
                    "reason": "Not yet confirmed if recent changes occurred"
                }
            ],
            outstanding_items=artifact.outstanding_items,
            approval_chain=["IT_Manager", "Clinical_Lead"],
            gate="severity_commit",
            requires_approval=True
        )
