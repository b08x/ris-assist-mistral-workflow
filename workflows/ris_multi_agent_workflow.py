
"""
RIS Assist Main Orchestrator

The main entry point for the Radiology Information Systems multi-agent workflow.
This module provides the orchestrator that classifies intake, delegates to
specialist agents, aggregates results, and hands every artifact to a human approver.

Model: claude-opus-4-6 (fallback: claude-sonnet-4-5)
"""

import sys
from pathlib import Path

# Ensure the parent directory is in sys.path for imports when running as a script
# This handles the case when running: python workflows/ris_multi_agent_workflow.py
if __name__ == "__main__" and __package__ is None:
    script_dir = Path(__file__).parent.parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

import asyncio
from dataclasses import asdict
from typing import Any, Dict, List, Optional

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
from agents.triage import TriageAgent
from agents.comms import CommunicationsAgent
from agents.kb import KnowledgeBaseAgent


class RISOrchestrator:
    """
    Radiology IT Support Orchestrator.
    
    This is the main orchestrator agent (ris-assist) that:
    1. Classifies intake based on triggers
    2. Delegates to specialist agents (triage, comms, kb)
    3. Aggregates structured JSON contracts
    4. Hands every artifact to a human approver
    
    The orchestrator maintains strict segregation of duties (SOD) - it
    drafts and recommends only, never executes.
    """
    
    def __init__(
        self, 
        site_profile: Optional[SiteProfile] = None,
        comms_profile: Optional[Dict[str, Any]] = None
    ):
        self.site_profile = site_profile or SiteProfile()
        self.comms_profile = comms_profile or {}
        self.name = AgentType.ORCHESTRATOR.value
        self.description = "Overnight radiology IT support assistant orchestrator"
        self.model_preferred = "claude-opus-4-6"
        self.model_fallback = ["claude-sonnet-4-5"]
        
        # Initialize sub-agents
        self.triage_agent = TriageAgent(self.site_profile)
        self.comms_agent = CommunicationsAgent(self.comms_profile)
        self.kb_agent = KnowledgeBaseAgent(self.site_profile)
        
        # Track active sessions
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    def classify_trigger(self, user_input: str) -> WorkflowTrigger:
        """
        Classify user input to determine workflow trigger.
        
        Based on delegation triggers from agent.yaml.
        """
        input_lower = user_input.lower()
        
        # Triage triggers (from agent.yaml delegation triggers)
        triage_trigger_keywords = [
            "vague ticket", "where should this go", "is this worth paging",
            "justify a severity", "escalation package", "new ticket", "triage",
            "vague or incomplete", "severity"
        ]
        if any(kw in input_lower for kw in triage_trigger_keywords):
            return WorkflowTrigger.NEW_TICKET
        
        # Communications triggers
        comms_trigger_keywords = [
            "draft a downtime notice", "we need to tell clinical",
            "send an update on the outage", "all clear", "mim update",
            "vendor ticket", "shift turnover", "tune notification",
            "downtime", "outage", "notification", "alert"
        ]
        if any(kw in input_lower for kw in comms_trigger_keywords):
            return WorkflowTrigger.DOWNTIME_ALERT
        
        # KB triggers
        kb_trigger_keywords = [
            "resolved incident", "turn this into a kb article",
            "same question keeps recurring", "is there an article",
            "stale check", "incident resolved", "recurring"
        ]
        if any(kw in input_lower for kw in kb_trigger_keywords):
            return WorkflowTrigger.INCIDENT_RESOLVED
        
        # Default to triage for new tickets
        return WorkflowTrigger.NEW_TICKET
    
    async def route_to_agent(
        self, 
        trigger: WorkflowTrigger, 
        user_input: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Route the request to the appropriate specialist agent.
        
        This implements the delegation logic from agent.yaml.
        """
        
        if trigger in [WorkflowTrigger.NEW_TICKET, WorkflowTrigger.ESCALATION_REQUEST]:
            # Parse ticket from input
            ticket = self._parse_ticket(user_input, context)
            
            # Run triage workflow
            result = await self._run_triage_workflow(ticket, context)
            return {"agent": AgentType.TRIAGE.value, "result": result}
        
        elif trigger in [
            WorkflowTrigger.DOWNTIME_ALERT, WorkflowTrigger.INCIDENT_UPDATE,
            WorkflowTrigger.ALL_CLEAR, WorkflowTrigger.VENDOR_TICKET,
            WorkflowTrigger.CHANGE_NARRATIVE, WorkflowTrigger.SHIFT_TURNOVER
        ]:
            # Run communications workflow
            result = await self._run_comms_workflow(user_input, context)
            return {"agent": AgentType.COMMS.value, "result": result}
        
        elif trigger in [
            WorkflowTrigger.INCIDENT_RESOLVED, WorkflowTrigger.RECURRING_SYMPTOM,
            WorkflowTrigger.STALE_CHECK
        ]:
            # Run KB workflow
            result = await self._run_kb_workflow(user_input, context)
            return {"agent": AgentType.KB.value, "result": result}
        
        else:
            return {"error": f"Unknown trigger: {trigger}"}
    
    def _parse_ticket(self, user_input: str, context: Dict[str, Any]) -> Ticket:
        """Parse a ticket from user input."""
        return Ticket(
            ticket_id=context.get("ticket_id", "TICKET-001"),
            title=context.get("title", "Untitled Ticket"),
            description=user_input,
            reported_by=context.get("reported_by", "unknown"),
            reported_at=context.get("reported_at", "2024-01-01T00:00:00Z"),
            systems_affected=context.get("systems_affected", []),
            severity=context.get("severity"),
            status=context.get("status", "NEW"),
            metadata=context.get("metadata", {})
        )
    
    async def _run_triage_workflow(
        self, 
        ticket: Ticket, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run the triage workflow (workflows/triage-flow.yaml).
        
        Steps:
        1. classify: Normalize ticket text; extract stated scope, timeline, symptoms
        2. site-context: Read-only lookup of site-specific information
        3. triage: Ask discriminating questions until routable
        4. severity: Justify severity in SLA vocabulary
        5. handoff: Package for human approval
        """
        print(f"[ORCHESTRATOR] Running triage workflow for ticket {ticket.ticket_id}")
        
        # Step 1: Classify
        classification = self.triage_agent.classify_ticket(ticket)
        
        # Step 2: Site context
        site_context = self.triage_agent.get_site_context(
            context.get("profile_path")
        )
        
        # Step 3: Triage (create artifact)
        triage_result = self.triage_agent.create_triage_artifact(
            ticket, 
            site_context,
            context.get("operating_context", "night_shift")
        )
        
        # Step 4: Severity justification
        severity_result = self.triage_agent.justify_severity(
            classification["normalized_ticket"], 
            site_context
        )
        
        # Step 5: Create handoff package
        handoff = self.triage_agent.create_approval_package(
            triage_result,
            severity_result["justification"]
        )
        
        return {
            "classification": classification,
            "triage_artifact": triage_result,
            "severity_justification": severity_result,
            "site_context": site_context,
            "handoff": handoff
        }
    
    async def _run_comms_workflow(
        self, 
        user_input: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run the communications workflow (workflows/comms-draft-flow.yaml).
        
        Steps:
        1. resolve-variant: Resolve event class x audience x channel
        2. select-template: Select appropriate template
        3. fill-slots: Fill template with stated facts only
        4. continuity: Maintain incident continuity for updates
        5. handoff: Package for human approval
        """
        print(f"[ORCHESTRATOR] Running communications workflow")
        
        # Determine audience from context or input
        audience = context.get("audience")
        if isinstance(audience, str):
            audience = getattr(Audience, audience.upper())
        
        # Get previous communications if this is an update
        previous_comms = context.get("previous_communications", [])
        
        # Step 1-5: Create complete communication draft
        comms_draft = self.comms_agent.create_communication_draft(
            event_facts=user_input,
            comms_profile_path=context.get("comms_profile_path"),
            audience=audience,
            previous_communications=previous_comms
        )
        
        # Create handoff package
        handoff = self.comms_agent.create_approval_package(comms_draft)
        
        return {
            "draft": comms_draft,
            "handoff": handoff
        }
    
    async def _run_kb_workflow(
        self, 
        user_input: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run the knowledge base workflow (workflows/kb-draft-flow.yaml).
        
        Steps:
        1. take-worklog: Accept worklog as given
        2. select-template: Select KB article template
        3. order-layers: Order diagnostic layers
        4. draft-sections: Draft article sections
        5. field-checklist: Run field checklist
        6. write-file: Write to file
        7. separate-suggestions: Separate suggestions from content
        8. handoff: Package for human approval
        """
        print(f"[ORCHESTRATOR] Running KB workflow")
        
        # Use the input as the worklog
        worklog = user_input
        
        # Create KB article
        kb_article = self.kb_agent.create_kb_article(
            worklog=worklog,
            profile_path=context.get("profile_path"),
            output_dir=context.get("output_dir", "."),
            render_docx=context.get("render_docx", False)
        )
        
        # Create handoff package
        handoff = self.kb_agent.create_approval_package(kb_article)
        
        return {
            "article": kb_article,
            "handoff": handoff
        }
    
    async def handle_request(
        self, 
        user_input: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for handling user requests.
        
        This method:
        1. Classifies the trigger based on user input
        2. Routes to the appropriate specialist agent
        3. Aggregates results
        4. Returns the handoff package for human approval
        
        Every artifact requires human approval before release (DUTIES.md strict).
        """
        context = context or {}
        
        # Classify trigger
        trigger = self.classify_trigger(user_input)
        print(f"[ORCHESTRATOR] Classified trigger: {trigger.value}")
        
        # Route to agent
        result = await self.route_to_agent(trigger, user_input, context)
        
        # Add metadata
        result["trigger"] = trigger.value
        result["orchestrator"] = self.name
        result["timestamp"] = "2024-01-01T00:00:00Z"  # Would use actual timestamp
        
        # Ensure handoff package exists
        if "handoff" not in result:
            # Create a generic approval package
            artifact = result.get("triage_artifact") or result.get("draft") or result.get("article")
            result["handoff"] = ApprovalPackage(
                artifact=artifact,
                reasoning=f"Result from {result.get('agent', 'unknown')} agent",
                outstanding_items=result.get("outstanding_items", []),
                approval_chain=result.get("approval_chain", ["IT_Manager"]),
                gate="human_approval"
            )
        
        return result
    
    def get_approval_gate(self, result: Dict[str, Any]) -> str:
        """Get the approval gate for a result."""
        if "handoff" in result and isinstance(result["handoff"], ApprovalPackage):
            return result["handoff"].gate
        return "human_approval"
    
    def get_outstanding_items(self, result: Dict[str, Any]) -> List[str]:
        """Get outstanding items from a result."""
        if "handoff" in result and isinstance(result["handoff"], ApprovalPackage):
            return result["handoff"].outstanding_items
        return result.get("outstanding_items", [])
    
    def get_approval_chain(self, result: Dict[str, Any]) -> List[str]:
        """Get the approval chain for a result."""
        if "handoff" in result and isinstance(result["handoff"], ApprovalPackage):
            return result["handoff"].approval_chain
        return result.get("approval_chain", [])


class RISAgentSystem:
    """
    Mistral AI Studio-compatible agent system for Radiology Information Systems.
    
    This class provides the integration layer between the RIS multi-agent
    workflow and Mistral AI Studio's Managed Agents framework.
    """
    
    def __init__(
        self,
        site_profile: Optional[SiteProfile] = None,
        comms_profile: Optional[Dict[str, Any]] = None,
        model_config: Optional[Dict[str, Any]] = None
    ):
        self.site_profile = site_profile
        self.comms_profile = comms_profile
        self.model_config = model_config or {}
        
        # Initialize orchestrator
        self.orchestrator = RISOrchestrator(site_profile, comms_profile)
        
        # Track sessions
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process a message in a session."""
        context = context or {}
        
        # Get or create session
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "created_at": "2024-01-01T00:00:00Z",
                "messages": [],
                "context": {}
            }
        
        session = self.sessions[session_id]
        
        # Add message to session
        session["messages"].append({
            "role": "user",
            "content": message,
            "timestamp": "2024-01-01T00:00:00Z"
        })
        
        # Process with orchestrator
        result = await self.orchestrator.handle_request(message, context)
        
        # Add result to session
        session["messages"].append({
            "role": "assistant",
            "content": result,
            "timestamp": "2024-01-01T00:00:00Z"
        })
        
        return result
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session details."""
        return self.sessions.get(session_id)
    
    async def list_sessions(self) -> List[str]:
        """List all active sessions."""
        return list(self.sessions.keys())
    
    def get_approval_gate(self, result: Dict[str, Any]) -> str:
        """Get the approval gate for a result."""
        return self.orchestrator.get_approval_gate(result)
    
    def get_outstanding_items(self, result: Dict[str, Any]) -> List[str]:
        """Get outstanding items from a result."""
        return self.orchestrator.get_outstanding_items(result)
    
    def get_approval_chain(self, result: Dict[str, Any]) -> List[str]:
        """Get the approval chain for a result."""
        return self.orchestrator.get_approval_chain(result)


async def main():
    """Main entry point for testing the RIS multi-agent workflow."""
    
    print("=" * 80)
    print("Radiology Information Systems Multi-Agent Workflow")
    print("Mistral AI Studio Integration Test")
    print("=" * 80)
    print()
    
    # Create site profile
    site_profile = SiteProfile(
        systems=["RIS", "PACS", "EHR", "HL7_Interface"],
        interfaces=["RIS-PACS", "PACS-EHR", "HL7_Engine"],
        identifier_formats={
            "patient_id": "MRN",
            "order_id": "Accession",
            "study_id": "SOP_Instance_UID"
        },
        sla_tiers={
            "SEV1": {
                "description": "Production system downtime",
                "response_time": "15 minutes",
                "resolution_time": "4 hours"
            },
            "SEV2": {
                "description": "Degraded service",
                "response_time": "1 hour",
                "resolution_time": "24 hours"
            },
            "SEV3": {
                "description": "Minor issue",
                "response_time": "4 hours",
                "resolution_time": "72 hours"
            },
            "SEV4": {
                "description": "Low priority",
                "response_time": "24 hours",
                "resolution_time": "1 week"
            }
        },
        escalation_matrix={
            "SEV1": ["OnCall_Engineer", "IT_Manager", "Clinical_Lead"],
            "SEV2": ["Senior_Technician", "IT_Manager"],
            "SEV3": ["Technician", "Senior_Technician"],
            "SEV4": ["Help_Desk"]
        },
        downtime_procedures={
            "PACS": "Notify Clinical Lead immediately",
            "RIS": "Notify IT Manager and Clinical Lead"
        }
    )
    
    # Create comms profile
    comms_profile = {
        "downtime_alert_clinical_email": "DOWNTIME_CLINICAL_TEMPLATE",
        "downtime_alert_technical_email": "DOWNTIME_TECHNICAL_TEMPLATE",
        "incident_update_technical_email": "UPDATE_TECHNICAL_TEMPLATE"
    }
    
    # Create agent system
    agent_system = RISAgentSystem(site_profile, comms_profile)
    
    # Test 1: Triage workflow
    print("Test 1: Triage Workflow")
    print("-" * 40)
    
    ticket_input = """
    Users reporting that CT studies are not appearing in PACS.
    RIS shows the orders as completed. No recent changes to the system.
    Issue started approximately 2 hours ago and is intermittent.
    Affecting only CT modality.
    """
    
    result = await agent_system.process_message(
        session_id="test-session-1",
        message=ticket_input,
        context={
            "ticket_id": "TICKET-001",
            "title": "CT Studies Not in PACS",
            "reported_by": "CT_Technologist",
            "operating_context": "night_shift"
        }
    )
    
    print(f"Trigger: {result.get('trigger')}")
    print(f"Agent: {result.get('agent')}")
    triage_artifact = result.get('triage_artifact')
    if triage_artifact:
        print(f"Scope: {triage_artifact.scope}")
        print(f"Recommended Queue: {triage_artifact.recommended_queue}")
        print(f"Confidence: {triage_artifact.confidence}")
        print(f"Outstanding Items: {triage_artifact.outstanding_items}")
    print(f"Approval Gate: {agent_system.get_approval_gate(result)}")
    print(f"Approval Chain: {agent_system.get_approval_chain(result)}")
    print()
    
    # Test 2: Communications workflow
    print("Test 2: Communications Workflow")
    print("-" * 40)
    
    comms_input = """
    PACS system is experiencing downtime. CT and MRI modalities cannot send studies.
    Estimated duration: 2 hours. Impact: Radiology department cannot perform image interpretation.
    Status: Investigating
    """
    
    result = await agent_system.process_message(
        session_id="test-session-2",
        message=comms_input,
        context={
            "audience": "CLINICAL",
            "comms_profile_path": "/path/to/comms/profile"
        }
    )
    
    print(f"Trigger: {result.get('trigger')}")
    print(f"Agent: {result.get('agent')}")
    draft = result.get('draft')
    if draft:
        print(f"Event Type: {draft.event_type}")
        print(f"Audience: {draft.audience.value}")
        print(f"Subject: {draft.subject}")
        print(f"Template Used: {draft.template_used}")
        print(f"Outstanding Items: {draft.outstanding_items}")
    print(f"Approval Gate: {agent_system.get_approval_gate(result)}")
    print()
    
    # Test 3: KB workflow
    print("Test 3: Knowledge Base Workflow")
    print("-" * 40)
    
    kb_input = """
    Incident: CT studies not appearing in PACS
    Scope: RIS-PACS integration for CT modality
    Timeline: Started 2024-01-01 02:00, resolved 2024-01-01 04:30
    Symptoms: CT studies completed in RIS but not visible in PACS
    Diagnosis: HL7 interface queue was stuck
    Cause: Memory leak in interface service causing queue processing to halt
    Resolution: Restarted interface service, cleared stuck messages
    Prevention: Monitor interface queue depths, set up alerts for stuck queues
    """
    
    result = await agent_system.process_message(
        session_id="test-session-3",
        message=kb_input,
        context={
            "profile_path": "/path/to/site/profile",
            "output_dir": "/tmp/kb_articles",
            "render_docx": False
        }
    )
    
    print(f"Trigger: {result.get('trigger')}")
    print(f"Agent: {result.get('agent')}")
    article = result.get('article')
    if article:
        print(f"Article Title: {article.title}")
        print(f"Article ID: {article.article_id}")
        print(f"Cause: {article.cause}")
        print(f"Cause Confidence: {article.cause_confidence}")
        print(f"Layers: {article.layers}")
        print(f"Outstanding Items: {article.outstanding_items}")
        print(f"Suggestions: {article.suggestions}")
    print(f"Approval Gate: {agent_system.get_approval_gate(result)}")
    print()
    
    print("=" * 80)
    print("All tests completed successfully!")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Deploy with Mistral Studio: agents deploy --config config/deployment.yaml")
    print("2. Or run locally: python workflows/ris_multi_agent_workflow.py")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
