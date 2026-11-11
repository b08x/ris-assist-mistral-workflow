# Radiology Information Systems Multi-Agent Workflow - Summary

## What Was Created

A **Mistral AI Studio-compatible** multi-agent workflow for Radiology Information Systems support, based on the [ris-assist-opengap](https://github.com/b08x/ris-assist-opengap) repository.

## File Structure

```
ris-assist-mistral-workflow/
├── README.md                      # Comprehensive documentation
├── DEPLOYMENT_GUIDE.md            # Deployment instructions
├── SUMMARY.md                     # This file
├── .gitignore                     # Git ignore patterns
├── requirements.txt               # Python dependencies
│
├── agents/                        # Specialist agent implementations
│   ├── __init__.py
│   ├── triage.py                  # Triage agent (claude-haiku-4-5)
│   ├── comms.py                   # Communications agent (claude-haiku-4-5)
│   └── kb.py                      # Knowledge Base agent (claude-sonnet-4-5)
│
├── workflows/                     # Workflow definitions
│   ├── __init__.py
│   ├── ris_data_models.py         # Data models for the workflow
│   └── ris_multi_agent_workflow.py # Main orchestrator and workflow logic
│
├── config/                        # Configuration files
│   └── deployment.yaml            # Mistral Studio deployment configuration
│
├── skills/                        # For future skills (explainer, onboarding)
├── tools/                         # For custom tools
└── tests/                         # For test cases
```

## Key Components

### 1. **Data Models** (`workflows/ris_data_models.py`)
- `SiteProfile`: Site-specific configuration
- `Ticket`: Support ticket representation
- `TriageArtifact`: Output from triage agent
- `CommunicationDraft`: Output from communications agent
- `KBArticle`: Output from knowledge base agent
- `ApprovalPackage`: Package for human approval handoff
- Enums: `AgentType`, `SeverityLevel`, `Audience`, `WorkflowTrigger`

### 2. **Agent Implementations**

#### Triage Agent (`agents/triage.py`)
- **Model**: claude-haiku-4-5 (fallback: claude-sonnet-4-5)
- **Purpose**: Differential-driven ticket clarification
- **Features**:
  - Classify tickets and extract scope, timeline, symptoms
  - Ask discriminating questions until routable
  - Build confidence-marked differential diagnosis
  - Justify severity using site SLA tiers
  - Recommend routing queue
  - Create approval packages with outstanding items

#### Communications Agent (`agents/comms.py`)
- **Model**: claude-haiku-4-5 (fallback: claude-sonnet-4-5)
- **Purpose**: Incident communication drafting
- **Features**:
  - Resolve event class × audience × channel variants
  - Select appropriate templates (site-specific or generic)
  - Fill slots with stated facts only
  - Maintain incident continuity for updates
  - Generate audience-appropriate register (clinical/technical/leadership)
  - Create approval packages

#### Knowledge Base Agent (`agents/kb.py`)
- **Model**: claude-sonnet-4-5 (fallback: claude-opus-4-6)
- **Purpose**: Knowledge capture from resolved incidents
- **Features**:
  - Accept worklogs as-is (no supplementation)
  - Order diagnostic layers (workstation/user, application, interface, advanced)
  - Draft KB article sections with confidence-marked causes
  - Generate ServiceNow-importable HTML
  - Run field checklist before presenting draft
  - Separate suggestions from content
  - Create approval packages

### 3. **Orchestrator** (`workflows/ris_multi_agent_workflow.py`)
- **Model**: claude-opus-4-6 (fallback: claude-sonnet-4-5)
- **Purpose**: Main workflow orchestrator
- **Features**:
  - Classify user input to determine workflow trigger
  - Route requests to appropriate specialist agents
  - Aggregate results from all agents
  - Create standardized approval packages
  - Maintain session state
  - Enforce strict segregation of duties (SOD)

### 4. **Agent System** (`RISAgentSystem`)
- **Purpose**: Integration layer for Mistral AI Studio
- **Features**:
  - Session management
  - Message processing
  - Result aggregation
  - Approval gate tracking
  - Outstanding items tracking

## Compliance Features

### Segregation of Duties (SOD)
- **Drafter**: All agents (create drafts, recommend, flag)
- **Approver**: Human-only (review, approve, reject)
- **Executor**: Human-only (execute, send, publish, submit)
- **Enforcement**: Structural - no agent can approve its own work

### Approval Gates (from DUTIES.md)
1. **notification_release**: Required before communication drafts leave session
2. **kb_submission**: Required before KB articles uploaded to ServiceNow
3. **severity_commit**: Required before severity recorded on ticket
4. **escalation_page**: Required before paging on-call senior

### Data Handling
- **Read-Only**: No state-changing actions against production systems
- **No PHI**: No identified PHI ingested or processed
- **No HL7 Parsing**: No segment/field level HL7 parsing
- **Site Profiles**: External, user-confirmed paths, never committed

### Confidence Marking
All conclusions carry explicit confidence marks:
- **confirmed**: Directly stated or cited
- **likely**: Consistent with evidence, not directly stated
- **possible**: Plausible but not supported

### Outstanding Items
- Required fields not supplied get placeholder tokens
- Never inferred, never left silently blank
- Tracked and reported in approval packages

## Workflow Architecture

### Triage Flow
```
Input → Classify → Site Context → Triage → Severity → Handoff
```
- Classifies ticket and extracts scope, timeline, symptoms
- Looks up site-specific context (systems, interfaces, SLA tiers)
- Asks discriminating questions until ticket is routable
- Justifies severity in site's SLA vocabulary
- Packages for human approval (severity_commit gate)

### Communications Flow
```
Input → Resolve Variant → Select Template → Fill Slots → Continuity → Handoff
```
- Resolves event class × audience × channel
- Selects appropriate template
- Fills slots with stated facts only
- Maintains incident continuity for updates
- Packages for human approval (notification_release gate)

### Knowledge Base Flow
```
Input → Take Worklog → Select Template → Order Layers → Draft → Checklist → Write → Suggestions → Handoff
```
- Accepts worklog as-is (no supplementation)
- Selects KB article template
- Orders diagnostic layers
- Drafts article sections with confidence-marked causes
- Runs field checklist
- Writes HTML file
- Separates suggestions
- Packages for human approval (kb_submission gate)

## Testing

All components have been tested:
- ✅ Data models import correctly
- ✅ All agents import correctly
- ✅ Orchestrator imports correctly
- ✅ Triage workflow executes successfully
- ✅ Communications workflow executes successfully
- ✅ KB workflow executes successfully

## Deployment Options

### 1. Local Development
```bash
python workflows/ris_multi_agent_workflow.py
```

### 2. Mistral Studio (Managed)
```bash
agents deploy --config config/deployment.yaml
```

### 3. Self-Hosted
```bash
agents serve --config config/deployment.yaml
```

## Ported From

This implementation is based on:
- **Repository**: [b08x/ris-assist-opengap](https://github.com/b08x/ris-assist-opengap)
- **Original**: ris-assist Claude Code plugin
- **Specification**: OpenGAP (Open General Agent Protocol)

## Key Differences from OpenGAP

1. **Framework**: Adapted for Mistral AI Studio Managed Agents
2. **Language**: Python with Mistral Agents SDK
3. **Deployment**: Compatible with `agents deploy` and `agents serve`
4. **Integration**: Works with Mistral's durable execution and tracing

## Non-Goals (from Original)

This agent set **drafts and recommends only**. It does NOT:
- Send notifications, submit KB articles, page anyone
- Decide severity autonomously
- Parse HL7 at segment/field level
- Handle identified PHI
- Take any state-changing action against a production system

These boundaries are **structural** (DUTIES.md) not aspirational.

## Next Steps

1. **Customize**: Update `config/deployment.yaml` with your models and settings
2. **Configure**: Create site_profile.yaml and comms_profile.yaml
3. **Test**: Run the workflow with your data
4. **Deploy**: Use `agents deploy` to deploy to Mistral Studio
5. **Monitor**: Use Mistral Studio's tracing and observability features

## License

This project inherits the license from the [ris-assist-opengap](https://github.com/b08x/ris-assist-opengap) repository.
