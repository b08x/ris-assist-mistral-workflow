# Deployment Guide for RIS Assist Multi-Agent Workflow

## Quick Start

### 1. Install Dependencies

```bash
# Clone the repository
git clone <repository-url> ris-assist-mistral-workflow
cd ris-assist-mistral-workflow

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Mistral AI Agents SDK
pip install mistralai-agents
```

### 2. Set Up API Key

```bash
# Set your Mistral API key
export MISTRAL_API_KEY="your-mistral-api-key"
```

### 3. Run Locally

```bash
# Run the workflow
python workflows/ris_multi_agent_workflow.py
```

## Deploy to Mistral Studio

### Mistral-Managed Deployment

```bash
# Deploy to Mistral's managed infrastructure
agents deploy --config config/deployment.yaml

# Check deployment status
agents status

# View logs
agents logs
```

### Self-Hosted Deployment

```bash
# Run self-hosted
agents serve --config config/deployment.yaml

# The agent will be available at http://localhost:8000
```

## Configuration

### Site Profile

Create a `site_profile.yaml` file (do NOT commit this to version control):

```yaml
systems:
  - RIS
  - PACS
  - EHR
  - HL7_Interface

interfaces:
  - RIS-PACS
  - PACS-EHR
  - HL7_Engine

identifier_formats:
  patient_id: "MRN"
  order_id: "Accession"
  study_id: "SOP_Instance_UID"

sla_tiers:
  SEV1:
    description: "Production system downtime"
    response_time: "15 minutes"
    resolution_time: "4 hours"
  SEV2:
    description: "Degraded service"
    response_time: "1 hour"
    resolution_time: "24 hours"

escalation_matrix:
  SEV1:
    - OnCall_Engineer
    - IT_Manager
    - Clinical_Lead
```

## Usage Examples

### Example 1: Triage a New Ticket

```python
from workflows.ris_data_models import SiteProfile
from workflows.ris_multi_agent_workflow import RISAgentSystem

site_profile = SiteProfile(
    systems=["RIS", "PACS", "EHR"],
    sla_tiers={"SEV1": {"description": "Production down"}},
    escalation_matrix={"SEV1": ["OnCall", "Manager"]}
)

agent_system = RISAgentSystem(site_profile)

result = await agent_system.process_message(
    session_id="ticket-001",
    message="CT studies not appearing in PACS",
    context={"ticket_id": "TICKET-001", "reported_by": "CT_Tech"}
)

artifact = result["triage_artifact"]
print(f"Recommended Queue: {artifact.recommended_queue}")
```

### Example 2: Draft Communication

```python
result = await agent_system.process_message(
    session_id="incident-001",
    message="PACS system is experiencing downtime",
    context={"audience": "CLINICAL"}
)

draft = result["draft"]
print(f"Subject: {draft.subject}")
```

### Example 3: Create KB Article

```python
result = await agent_system.process_message(
    session_id="kb-001",
    message="Incident resolved: CT studies not appearing in PACS...",
    context={"output_dir": "/tmp/kb_articles"}
)

article = result["article"]
print(f"Article ID: {article.article_id}")
```

## Testing

```bash
pip install pytest pytest-asyncio
pytest
```

## Compliance

- **HIPAA-Adjacent**: No PHI ingested, drafts only
- **ITSM Change Control**: No state-changing actions
- **KCS Knowledge Capture**: Article fidelity to worklog
- **Segregation of Duties**: Structural enforcement

## Approval Gates

| Gate | Description | Approvers |
|------|-------------|-----------|
| notification_release | Communication drafts | IT_Manager, Clinical_Lead |
| kb_submission | KB articles | KB_Manager, IT_Lead |
| severity_commit | Severity assignments | IT_Manager, Clinical_Lead |
| escalation_page | Paging on-call | IT_Manager |

## Migration from OpenGAP

This implementation maintains full compatibility with the OpenGAP specification from [ris-assist-opengap](https://github.com/b08x/ris-assist-opengap).
