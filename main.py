"""
Main entry point for RIS Assist Multi-Agent Workflow

This file provides the agent instance required by Mistral AI Agents SDK.
The `agents deploy` and `agents serve` commands look for a variable named
`agent` in this module.

Usage:
    agents deploy          # Deploy to Mistral Studio
    agents serve          # Run locally
    python main.py        # Run directly
"""

import os
from mistralai import agents
from workflows.ris_data_models import SiteProfile
from workflows.ris_multi_agent_workflow import RISOrchestrator

# Create site profile from environment or defaults
site_profile = SiteProfile(
    systems=os.getenv("RIS_SYSTEMS", "RIS,PACS,EHR").split(","),
    interfaces=os.getenv("RIS_INTERFACES", "RIS-PACS,PACS-EHR").split(","),
    sla_tiers={
        "SEV1": {"description": "Production system downtime", "response_time": "15 minutes"},
        "SEV2": {"description": "Degraded service", "response_time": "1 hour"},
        "SEV3": {"description": "Minor issue", "response_time": "4 hours"},
        "SEV4": {"description": "Low priority", "response_time": "24 hours"},
    },
    escalation_matrix={
        "SEV1": ["OnCall_Engineer", "IT_Manager", "Clinical_Lead"],
        "SEV2": ["Senior_Technician", "IT_Manager"],
        "SEV3": ["Technician", "Senior_Technician"],
        "SEV4": ["Help_Desk"],
    },
)

# Create the orchestrator
orchestrator = RISOrchestrator(site_profile=site_profile)

# Create the Mistral Agent
# This is the entry point that Mistral AI Agents SDK expects
agent = agents.Agent(
    name="ris-assist",
    description="Radiology IT Support Multi-Agent Orchestrator",
    model="mistral-large-4",
)

# For direct execution
if __name__ == "__main__":
    import asyncio
    import sys
    
    async def main():
        print("RIS Assist Multi-Agent Workflow")
        print("=" * 60)
        print()
        print("Usage:")
        print("  agents deploy          # Deploy to Mistral Studio")
        print("  agents serve          # Run locally")
        print("  python main.py        # Run directly")
        print()
        print("Environment variables:")
        print("  MISTRAL_API_KEY       # Required")
        print("  RIS_SYSTEMS           # Optional: comma-separated systems")
        print("  RIS_INTERFACES        # Optional: comma-separated interfaces")
        print()
        
        # If no arguments, start an interactive session
        if len(sys.argv) == 1:
            print("Starting interactive session...")
            print("Type 'exit' to quit")
            print()
            
            while True:
                try:
                    user_input = input(">>> ")
                    if user_input.lower() in ['exit', 'quit', 'q']:
                        break
                    
                    # Process the input through the orchestrator
                    result = await orchestrator.handle_request(user_input, {})
                    
                    print(f"\nAgent: {result.get('agent')}")
                    print(f"Trigger: {result.get('trigger')}")
                    
                    if 'triage_artifact' in result:
                        artifact = result['triage_artifact']
                        print(f"Scope: {artifact.scope}")
                        print(f"Queue: {artifact.recommended_queue}")
                    
                    if 'draft' in result:
                        draft = result['draft']
                        print(f"Subject: {draft.subject}")
                    
                    if 'article' in result:
                        article = result['article']
                        print(f"Title: {article.title}")
                    
                    print(f"Approval Gate: {orchestrator.get_approval_gate(result)}")
                    print()
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"Error: {e}")
                    import traceback
                    traceback.print_exc()
                    print()
    
    asyncio.run(main())
