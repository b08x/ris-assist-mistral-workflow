# Radiology Information Systems Multi-Agent Workflow

A **Mistral AI Studio-compatible** multi-agent workflow for radiology IT support, based on the [ris-assist-opengap](https://github.com/b08x/ris-assist-opengap) repository.

## Overview

This workflow implements a hierarchical multi-agent system for overnight radiology IT support, following the same architecture as the OpenGAP specification but adapted for Mistral AI Studio's Managed Agents framework.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     RIS-ASSIST ORCHESTRATOR                  │
│  (claude-opus-4-6 / claude-sonnet-4-5 fallback)               │
│  - Classifies intake                                          │
│  - Delegates to specialist agents                             │
│  - Aggregates structured JSON contracts                       │
│  - Hands every artifact to human approver                    │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   TRIAGE AGENT  │ │  COMMS AGENT   │ │    KB AGENT    │
│  (claude-haiku) │ │  (claude-haiku) │ │ (claude-sonnet) │
│                 │ │                 │ │                 │
│ - Differential │ │ - Downtime     │ │ - Worklog to   │
│   driven Q&A    │ │   alerts       │ │   KB article    │
│ - Severity      │ │ - MIM updates   │ │ - Recurring     │
│   justification │ │ - Vendor tickets│ │   incident      │
│ - Escalation    │ │ - Shift turnover│ │   detection     │
│   packages      │ │ - Template     │ │ - Stale article │
│                 │ │   filling      │ │   flagging      │
└─────────────────┘ └─────────────────┘ └─────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌─────────────────────────────────────────┐
        │           HUMAN APPROVER                 │
        │  - Reviews all artifacts                 │
        │  - Never bypassed (DUTIES.md strict)     │
        │  - Approval gates:                       │
        │    * notification_release                │
        │    * kb_submission                       │
        │    * severity_commit                     │
        │    * escalation_page                     │
        └─────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │           HUMAN OPERATOR                  │
        │  - Sends notifications                    │
        │  - Submits KB articles                   │
        │  - Pages on-call staff                   │
        │  - Changes production state              │
        └─────────────────────────────────────────┘
```

## Key Features

### 1. **Strict Segregation of Duties (SOD)**
- **Drafter**: All agents (create drafts, recommend, flag)
- **Approver**: Human-only (review, approve, reject)
- **Executor**: Human-only (execute, send, publish, submit)
- No agent holds both drafter and approver roles
- No agent both drafts and releases an artifact

### 2. **Confidence Marking**
All conclusions carry explicit confidence marks:
- **confirmed**: Directly stated in ticket/worklog or cited source
- **likely**: Consistent with available evidence, not directly stated
- **possible**: Plausible given the differential, not yet supported

### 3. **Outstanding Items Discipline**
- Required fields not supplied get placeholder tokens
- Never inferred, never left silently blank
- Tracked and reported in approval packages

### 4. **Site Profile Integration**
- Site-specific facts come only from the site profile
- Never invented or guessed
- Profiles live outside this repo at user-confirmed paths
- Never committed, never searched for

### 5. **Read-Only Access**
- No state-changing action against any production system
- No HL7 segment/field parsing (separate forensics plugin)
- No identified PHI handling
- No direct ServiceNow writes (DEP-1)

## Workflows

### 1. **Triage Flow** (`workflows/triage-flow.yaml`)
```
new_ticket → classify → site-context → triage → severity → handoff
```
- Differential-driven ticket clarification
- One discriminating question at a time until routable
- Triage artifact with scope, timeline, confidence-marked differential
- SLA-vocabulary severity justification
- Approval-gated handoff (severity_commit gate)

### 2. **Communications Flow** (`workflows/comms-draft-flow.yaml`)
```
downtime_alert → resolve-variant → select-template → fill-slots → continuity → handoff
```
- Resolve event class × audience × channel
- Select template (site-specific or generic)
- Fill slots from stated facts only
- Maintain incident continuity for updates
- Approval-gated handoff (notification_release gate)

### 3. **Knowledge Base Flow** (`workflows/kb-draft-flow.yaml`)
```
incident_resolved → take-worklog → select-template → order-layers → draft-sections → 
field-checklist → write-file → render-docx → separate-suggestions → handoff
```
- Worklog as given (no supplementation)
- Triage-ordered HTML article
- ServiceNow-importable format
- Optional .docx render
- Approval-gated handoff (kb_submission gate)

## Agent Specifications

### Orchestrator Agent (`ris-assist`)
- **Model**: claude-opus-4-6 (fallback: claude-sonnet-4-5)
- **Role**: Classify intake, delegate, aggregate, hand off
- **Skills**: explainer, onboarding
- **Constraints**: temperature 0.2, max_tokens 8192
- **Runtime**: max_turns 50, timeout 300s

### Triage Agent
- **Model**: claude-haiku-4-5 (fallback: claude-sonnet-4-5)
- **Role**: Differential-driven ticket clarification
- **Skill**: troubleshoot
- **Constraints**: temperature 0.2, max_tokens 4096
- **Runtime**: max_turns 30, timeout 300s

### Communications Agent
- **Model**: claude-haiku-4-5 (fallback: claude-sonnet-4-5)
- **Role**: Incident communication drafting
- **Skill**: comms
- **Constraints**: temperature 0.2, max_tokens 8192
- **Runtime**: max_turns 30, timeout 300s

### Knowledge Base Agent
- **Model**: claude-sonnet-4-5 (fallback: claude-opus-4-6)
- **Role**: Knowledge capture from resolved incidents
- **Skill**: knowledge
- **Constraints**: temperature 0.2, max_tokens 16384
- **Runtime**: max_turns 30, timeout 300s

## Deployment

### Local Development

```bash
# Install dependencies
pip install mistralai-agents

# Set API key
export MISTRAL_API_KEY="your-api-key"

# Run locally
python workflows/ris_multi_agent_workflow.py
```

### Deploy with Mistral Studio

```bash
# Deploy to Mistral-managed infrastructure
agents deploy --config config/deployment.yaml

# Or self-host
agents serve --config config/deployment.yaml
```

### Configuration

Create `config/deployment.yaml`:

```yaml
# Deployment configuration for Mistral AI Studio
name: ris-assist-workflow
version: 0.2.0
description: Radiology IT support multi-agent workflow

model:
  preferred: mistral-large-4
  fallback:
    - mistral-small-4
  constraints:
    temperature: 0.2
    max_tokens: 8192

runtime:
  max_turns: 50
  timeout: 300

compliance:
  risk_tier: standard
  human_in_the_loop: always
  
agents:
  - name: ris-assist
    type: orchestrator
    model: mistral-large-4
    
  - name: triage
    type: subagent
    model: mistral-small-4
    delegation_mode: auto
    triggers:
      - "vague or incomplete ticket needs a discriminating question"
      - "where should this go"
      - "is this worth paging someone"
      
  - name: comms
    type: subagent
    model: mistral-small-4
    delegation_mode: auto
    triggers:
      - "draft a downtime notice"
      - "we need to tell clinical"
      - "send an update on the outage"
      
  - name: kb
    type: subagent
    model: mistral-small-4
    delegation_mode: auto
    triggers:
      - "resolved incident worth writing up"
      - "turn this into a KB article"
```

## File Structure

```
ris-assist-mistral-workflow/
├── README.md                    # This file
├── agents/                      # Agent implementations
│   ├── __init__.py
│   ├── orchestrator.py          # Main orchestrator agent
│   ├── triage.py                # Triage subagent
│   ├── comms.py                 # Communications subagent
│   └── kb.py                    # Knowledge Base subagent
│
├── workflows/                   # Workflow definitions
│   ├── __init__.py
│   ├── ris_data_models.py       # Data models for the workflow
│   └── ris_multi_agent_workflow.py  # Main workflow orchestrator
│
├── config/                      # Configuration files
│   ├── deployment.yaml          # Mistral Studio deployment config
│   └── site_profile.schema.json # Site profile schema
│
├── skills/                      # Skills (explainer, onboarding)
│   ├── __init__.py
│   ├── explainer.py
│   └── onboarding.py
│
├── tools/                       # Custom tools
│   └── __init__.py
│
└── tests/                       # Test cases
    ├── __init__.py
    ├── test_triage.py
    ├── test_comms.py
    └── test_kb.py
```

## Compliance

This workflow adheres to the following compliance frameworks:

### HIPAA-Adjacent Handling
- No PHI ingested
- Drafts only (no patient data)
- Redaction of sensitive information

### ITSM Change Control
- No state-changing actions against production
- All changes require human approval
- Audit logging of all decisions

### KCS-Style Knowledge Capture
- Article fidelity to worklog
- Suggestions separated from content
- Outstanding items tracked

### Segregation of Duties
- Structural enforcement via DUTIES.md
- No agent can approve its own work
- Human-only approver and executor roles

## Migration from OpenGAP

This implementation maintains full compatibility with the OpenGAP specification:

- **Identity**: SOUL.md persona preserved across all agents
- **Duties**: DUTIES.md segregation of duties enforced
- **Rules**: RULES.md constraints applied
- **Skills**: All skills preserved and accessible
- **Delegation**: Auto-delegation with triggers from agent.yaml

The workflow can be exported to other frameworks:

```bash
# Export to CrewAI
opengap export -f crewai

# Export to LangGraph
opengap export -f langgraph

# Export to OpenAI Agents
opengap export -f openai
```

## Example Usage

### Triage a New Ticket

```python
from workflows.ris_multi_agent_workflow import RISAgentSystem

# Create agent system
agent_system = RISAgentSystem(site_profile=my_site_profile)

# Process a new ticket
result = await agent_system.process_message(
    session_id="ticket-001",
    message="Users reporting that CT studies are not appearing in PACS...",
    context={
        "ticket_id": "TICKET-001",
        "reported_by": "CT_Technologist",
        "operating_context": "night_shift"
    }
)

# Get the triage artifact
artifact = result["triage_artifact"]
print(f"Recommended Queue: {artifact.recommended_queue}")
print(f"Confidence: {artifact.confidence}")
print(f"Outstanding Items: {artifact.outstanding_items}")

# Get approval package
handoff = result["handoff"]
print(f"Approval Gate: {handoff.gate}")
print(f"Approval Chain: {handoff.approval_chain}")
```

### Draft an Incident Communication

```python
result = await agent_system.process_message(
    session_id="incident-001",
    message="PACS system is experiencing downtime. CT and MRI modalities cannot send studies.",
    context={
        "audience": "CLINICAL",
        "event_type": "downtime_alert"
    }
)

draft = result["draft"]
print(f"Subject: {draft.subject}")
print(f"Body: {draft.body}")
print(f"Outstanding Items: {draft.outstanding_items}")
```

### Create a KB Article

```python
result = await agent_system.process_message(
    session_id="kb-001",
    message="Incident: CT studies not appearing in PACS... Resolution: Restarted interface service...",
    context={
        "profile_path": "/path/to/site/profile",
        "render_docx": True
    }
)

article = result["article"]
print(f"Title: {article.title}")
print(f"Article ID: {article.article_id}")
print(f"Cause Confidence: {article.cause_confidence}")
print(f"HTML Content: {article.content_html[:200]}...")
```

## Testing

Run the test suite:

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest tests/

# Run specific test
pytest tests/test_triage.py
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is based on the [ris-assist-opengap](https://github.com/b08x/ris-assist-opengap) repository and inherits its license.

## References

- [ris-assist-opengap Repository](https://github.com/b08x/ris-assist-opengap)
- [Mistral AI Studio Documentation](https://docs.mistral.ai/studio/agents/overview)
- [OpenGAP Specification](https://github.com/opengap-ai/spec)
- [KCS (Knowledge-Centered Service) Methodology](https://www.serviceinnovation.org/kcs/)
- [ITSM Best Practices](https://www.itil.org/)

## Non-Goals

This agent set **drafts and recommends only**. It does NOT:
- Send notifications, submit KB articles, page anyone
- Decide severity autonomously
- Parse HL7 at segment/field level
- Handle identified PHI
- Take any state-changing action against a production system

These boundaries are structural (DUTIES.md) not aspirational.
