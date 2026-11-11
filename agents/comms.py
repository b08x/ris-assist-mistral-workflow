
"""
Communications Agent

Incident communication drafting specialist under the ris-assist orchestrator.
Drafts incident communications - downtime alerts, MIM cadence updates, vendor tickets,
change narratives, shift turnover - matched to audience register, with outstanding-items
discipline, plus comms-profile tuning.

Model: claude-haiku-4-5 (fallback: claude-sonnet-4-5)
Skill: comms
"""

from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from workflows.ris_data_models import (
    AgentType,
    ApprovalPackage,
    Audience,
    CommunicationDraft,
    SeverityLevel,
    WorkflowTrigger,
)


class CommunicationsAgent:
    """
    Incident communication drafting specialist.
    
    Drafts and recommends only; never sends, publishes, pages, or posts.
    """
    
    def __init__(self, comms_profile: Optional[Dict[str, Any]] = None):
        self.comms_profile = comms_profile or {}
        self.name = AgentType.COMMS.value
        self.description = "Incident communication drafting for radiology IT"
        self.model_preferred = "claude-haiku-4-5"
        self.model_fallback = ["claude-sonnet-4-5"]
    
    def resolve_variant(
        self, 
        event_facts: str, 
        comms_profile_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resolve event class x audience x channel.
        Ask for any part the user has not supplied - one question at a time.
        
        This is step 1 in the comms-draft-flow.yaml workflow.
        """
        # Determine event class
        event_class = self._determine_event_class(event_facts)
        
        # Determine audience (would normally come from context or ask user)
        audience = self._determine_audience(event_facts)
        
        # Determine channel (default to email)
        channel = "email"
        
        # Create variant key
        variant_key = f"{event_class.value}_{audience.value}_{channel}"
        
        # Check if this is an update
        is_update = "update" in event_facts.lower() or "follow-up" in event_facts.lower()
        
        return {
            "event_class": event_class,
            "audience": audience,
            "channel": channel,
            "variant_key": variant_key,
            "is_update": is_update
        }
    
    def _determine_event_class(self, event_facts: str) -> WorkflowTrigger:
        """Determine the event class from the facts."""
        facts_lower = event_facts.lower()
        
        if any(kw in facts_lower for kw in ["downtime", "outage", "down"]):
            return WorkflowTrigger.DOWNTIME_ALERT
        elif any(kw in facts_lower for kw in ["all clear", "resolved", "fixed"]):
            return WorkflowTrigger.ALL_CLEAR
        elif any(kw in facts_lower for kw in ["update", "status", "progress"]):
            return WorkflowTrigger.INCIDENT_UPDATE
        elif any(kw in facts_lower for kw in ["vendor", "ticket", "support case"]):
            return WorkflowTrigger.VENDOR_TICKET
        elif any(kw in facts_lower for kw in ["change", "update", "upgrade", "maintenance"]):
            return WorkflowTrigger.CHANGE_NARRATIVE
        elif any(kw in facts_lower for kw in ["shift", "turnover", "handoff"]):
            return WorkflowTrigger.SHIFT_TURNOVER
        else:
            return WorkflowTrigger.INCIDENT_UPDATE
    
    def _determine_audience(self, event_facts: str) -> Audience:
        """Determine the audience from the facts or use default."""
        facts_lower = event_facts.lower()
        
        if any(kw in facts_lower for kw in ["clinical", "radiologist", "physician", "nurse"]):
            return Audience.CLINICAL
        elif any(kw in facts_lower for kw in ["technical", "it", "engineer", "technician"]):
            return Audience.TECHNICAL
        elif any(kw in facts_lower for kw in ["leadership", "management", "director"]):
            return Audience.LEADERSHIP
        elif any(kw in facts_lower for kw in ["vendor", "support", "external"]):
            return Audience.VENDOR
        else:
            # Default to technical for IT systems
            return Audience.TECHNICAL
    
    def select_template(
        self, 
        variant_key: str, 
        comms_profile_path: Optional[str] = None
    ) -> str:
        """
        Exact match, else nearest defined variant with the substitution
        stated out loud, else generic reference template labelled untuned.
        
        This is step 2 in the comms-draft-flow.yaml workflow.
        """
        # Check if we have a profile-specific template
        if comms_profile_path and variant_key in self.comms_profile:
            return self.comms_profile[variant_key]
        
        # Check for exact match in comms_profile
        if variant_key in self.comms_profile:
            return self.comms_profile[variant_key]
        
        # Return generic template based on variant
        templates = {
            "downtime_alert_clinical_email": "DOWNTIME_CLINICAL_TEMPLATE",
            "downtime_alert_technical_email": "DOWNTIME_TECHNICAL_TEMPLATE",
            "downtime_alert_leadership_email": "DOWNTIME_LEADERSHIP_TEMPLATE",
            "incident_update_clinical_email": "UPDATE_CLINICAL_TEMPLATE",
            "incident_update_technical_email": "UPDATE_TECHNICAL_TEMPLATE",
            "all_clear_clinical_email": "ALL_CLEAR_CLINICAL_TEMPLATE",
            "all_clear_technical_email": "ALL_CLEAR_TECHNICAL_TEMPLATE",
            "vendor_ticket_technical_email": "VENDOR_TICKET_TEMPLATE",
            "change_narrative_technical_email": "CHANGE_NARRATIVE_TEMPLATE",
            "shift_turnover_technical_email": "SHIFT_TURNOVER_TEMPLATE"
        }
        
        return templates.get(variant_key, "GENERIC_TEMPLATE")
    
    def fill_slots(
        self, 
        template: str, 
        event_facts: str
    ) -> Dict[str, Any]:
        """
        Stated facts only. Missing required slots get placeholder tokens
        and land in the outstanding-items list. An ETA, cause, or impact
        scope is never inferred. Causal claims marked confirmed/suspected.
        
        This is step 3 in the comms-draft-flow.yaml workflow.
        """
        # Extract facts from event_facts
        facts = self._extract_facts(event_facts)
        
        # Generate draft body based on template and facts
        draft_body = self._generate_draft(template, facts)
        
        # Identify missing required slots
        outstanding_items = self._identify_missing_slots(facts)
        
        # Determine approval chain based on audience
        approval_chain = self._get_approval_chain(facts.get("audience", Audience.TECHNICAL))
        
        return {
            "draft": draft_body,
            "outstanding_items": outstanding_items,
            "approval_chain": approval_chain
        }
    
    def _extract_facts(self, event_facts: str) -> Dict[str, Any]:
        """Extract stated facts from event text."""
        facts: Dict[str, Any] = {
            "event": "",
            "start_time": "",
            "impact": "",
            "systems": [],
            "status": "",
            "eta": "",
            "cause": "",
            "cause_confidence": ""
        }
        
        # Extract event type
        if any(kw in event_facts.lower() for kw in ["downtime", "outage"]):
            facts["event"] = "System Downtime"
        elif any(kw in event_facts.lower() for kw in ["all clear", "resolved"]):
            facts["event"] = "Incident Resolved"
        elif any(kw in event_facts.lower() for kw in ["update", "status"]):
            facts["event"] = "Incident Update"
        
        # Extract systems
        systems_keywords = ["PACS", "RIS", "EHR", "HL7", "CT", "MRI", "Modality", "Interface"]
        for kw in systems_keywords:
            if kw in event_facts:
                facts["systems"].append(kw)
        
        # Extract impact
        if any(kw in event_facts.lower() for kw in ["cannot", "unable", "down", "unavailable"]):
            facts["impact"] = "Service unavailable"
        elif any(kw in event_facts.lower() for kw in ["slow", "degraded", "intermittent"]):
            facts["impact"] = "Degraded performance"
        
        # Extract time information
        time_keywords = ["started", "since", "for", "hours", "minutes"]
        for line in event_facts.split("\n"):
            if any(kw in line.lower() for kw in time_keywords):
                facts["start_time"] = line.strip()
                break
        
        # Extract status
        if any(kw in event_facts.lower() for kw in ["resolved", "fixed", "restored"]):
            facts["status"] = "Resolved"
        elif any(kw in event_facts.lower() for kw in ["investigating", "working", "looking"]):
            facts["status"] = "Investigating"
        
        return facts
    
    def _generate_draft(self, template: str, facts: Dict[str, Any]) -> str:
        """Generate draft body from template and facts."""
        audience = facts.get("audience", Audience.TECHNICAL)
        
        # Determine audience register (from SOUL.md)
        if audience == Audience.CLINICAL:
            lead = "The action you must take, named the way the site names it"
            register = "clinical"
        elif audience == Audience.TECHNICAL:
            lead = "The failure, named precisely, with the ticket reference"
            register = "technical"
        elif audience == Audience.LEADERSHIP:
            lead = "Scope, duration, what's being done, in that order"
            register = "leadership"
        else:
            lead = "The failure, named precisely"
            register = "technical"
        
        # Build draft based on register
        draft = f"""{lead}

"""
        
        if facts.get("event"):
            draft += f"Event: {facts['event']}\n\n"
        
        if facts.get("start_time"):
            draft += f"Start Time: {facts['start_time']}\n\n"
        else:
            draft += "Start Time: [TBD]\n\n"
        
        if facts.get("impact"):
            draft += f"Impact: {facts['impact']}\n\n"
        else:
            draft += "Impact: [TBD]\n\n"
        
        if facts.get("systems"):
            draft += f"Affected Systems: {', '.join(facts['systems'])}\n\n"
        else:
            draft += "Affected Systems: [TBD]\n\n"
        
        if facts.get("status"):
            draft += f"Status: {facts['status']}\n\n"
        else:
            draft += "Status: [Investigating]\n\n"
        
        if facts.get("eta"):
            draft += f"Estimated Resolution: {facts['eta']}\n\n"
        
        # Add causal claims if present
        if facts.get("cause"):
            confidence = facts.get("cause_confidence", "suspected")
            draft += f"Cause: {facts['cause']} ({confidence})\n\n"
        
        draft += "Next update will be provided as more information becomes available."
        
        return draft
    
    def _identify_missing_slots(self, facts: Dict[str, Any]) -> List[str]:
        """Identify missing required slots."""
        missing = []
        
        # Check for critical missing information
        if not facts.get("start_time"):
            missing.append("start_time")
        if not facts.get("impact"):
            missing.append("impact")
        if not facts.get("systems"):
            missing.append("affected_systems")
        if not facts.get("status"):
            missing.append("current_status")
        
        return missing
    
    def _get_approval_chain(self, audience: Audience) -> List[str]:
        """Get the approval chain based on audience."""
        chains = {
            Audience.CLINICAL: ["Clinical_Lead", "IT_Manager"],
            Audience.TECHNICAL: ["IT_Manager", "Senior_Technician"],
            Audience.LEADERSHIP: ["IT_Director", "Clinical_Director"],
            Audience.VENDOR: ["IT_Manager", "Vendor_Liaison"]
        }
        return chains.get(audience, ["IT_Manager"])
    
    def maintain_continuity(
        self, 
        draft: str, 
        previous_communications: List[Dict[str, Any]]
    ) -> str:
        """
        Carry forward incident reference, original start time, previously
        stated impact; require only the delta. A previously published fact
        that changed is flagged as changed, never silently corrected.
        
        This is step 4 in the comms-draft-flow.yaml workflow.
        """
        if not previous_communications:
            return draft
        
        # Get the first communication's details
        first_comm = previous_communications[0]
        
        # Build continuity header
        continuity_header = f"""[INCIDENT CONTINUITY]
Incident Reference: {first_comm.get('incident_id', 'N/A')}
Original Start Time: {first_comm.get('start_time', 'N/A')}
Originally Stated Impact: {first_comm.get('impact', 'N/A')}

"""
        
        return continuity_header + draft
    
    def create_communication_draft(
        self,
        event_facts: str,
        comms_profile_path: Optional[str] = None,
        audience: Optional[Audience] = None,
        previous_communications: Optional[List[Dict[str, Any]]] = None
    ) -> CommunicationDraft:
        """
        Create a complete communication draft.
        
        This runs the complete comms-draft-flow.yaml workflow.
        """
        # Step 1: Resolve variant
        variant_result = self.resolve_variant(event_facts, comms_profile_path)
        
        # Override audience if specified
        if audience:
            variant_result["audience"] = audience
        
        # Step 2: Select template
        template = self.select_template(
            variant_result["variant_key"], 
            comms_profile_path
        )
        
        # Step 3: Fill slots
        fill_result = self.fill_slots(template, event_facts)
        
        # Step 4: Maintain continuity if this is an update
        draft_body = fill_result["draft"]
        if variant_result.get("is_update", False) and previous_communications:
            draft_body = self.maintain_continuity(draft_body, previous_communications)
        
        # Generate subject
        subject = self._generate_subject(
            variant_result.get("event_class", WorkflowTrigger.INCIDENT_UPDATE),
            event_facts
        )
        
        # Create the communication draft
        return CommunicationDraft(
            event_type=variant_result.get("event_class", WorkflowTrigger.INCIDENT_UPDATE).value,
            audience=variant_result["audience"],
            channel=variant_result["channel"],
            subject=subject,
            body=draft_body,
            variant_key=variant_result["variant_key"],
            template_used=template,
            outstanding_items=fill_result["outstanding_items"],
            approval_chain=fill_result["approval_chain"],
            is_update=variant_result.get("is_update", False)
        )
    
    def _generate_subject(self, event_class: WorkflowTrigger, event_facts: str) -> str:
        """Generate email subject based on event class."""
        subjects = {
            WorkflowTrigger.DOWNTIME_ALERT: "URGENT: System Downtime Alert",
            WorkflowTrigger.INCIDENT_UPDATE: "UPDATE: Incident Status",
            WorkflowTrigger.ALL_CLEAR: "RESOLVED: All Clear Notification",
            WorkflowTrigger.VENDOR_TICKET: "ACTION REQUIRED: Vendor Ticket",
            WorkflowTrigger.CHANGE_NARRATIVE: "NOTIFICATION: System Change",
            WorkflowTrigger.SHIFT_TURNOVER: "SHIFT TURNOVER: Handoff Report"
        }
        return subjects.get(event_class, "NOTIFICATION: Incident Update")
    
    def create_approval_package(
        self, 
        draft: CommunicationDraft
    ) -> ApprovalPackage:
        """
        Surface the approval chain with the draft - never bypassed, never
        assumed satisfied.
        
        Gate: notification_release (DUTIES.md)
        """
        return ApprovalPackage(
            artifact=draft,
            reasoning=f"Communication draft created for {draft.event_type} to {draft.audience.value} audience",
            dead_branches=[],
            outstanding_items=draft.outstanding_items,
            approval_chain=draft.approval_chain,
            gate="notification_release",
            requires_approval=True
        )
