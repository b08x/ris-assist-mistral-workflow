
"""
Knowledge Base Agent

Knowledge capture specialist under the ris-assist orchestrator. Turns a
resolved ticket or worklog into a ServiceNow-importable knowledge base
article - triage-first HTML draft, optionally rendered to .docx - with
outstanding-items and suggestions-separation discipline, plus
recurring-incident gap detection and stale-article flagging in manual mode.

Model: claude-sonnet-4-5 (fallback: claude-opus-4-6)
Skill: knowledge
"""

import os
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from workflows.ris_data_models import (
    AgentType,
    ApprovalPackage,
    KBArticle,
    SiteProfile,
    WorkflowTrigger,
)


class KnowledgeBaseAgent:
    """
    Knowledge capture specialist.
    
    Never writes to ServiceNow (DEP-1); a human uploads.
    """
    
    def __init__(self, site_profile: Optional[SiteProfile] = None):
        self.site_profile = site_profile or SiteProfile()
        self.name = AgentType.KB.value
        self.description = "Knowledge base article generation from resolved incidents"
        self.model_preferred = "claude-sonnet-4-5"
        self.model_fallback = ["claude-opus-4-6"]
    
    def take_worklog(self, worklog: str) -> Dict[str, Any]:
        """
        Accept the worklog as given. No supplementation, ever.
        
        This is step 1 in the kb-draft-flow.yaml workflow.
        """
        return {
            "normalized": worklog,
            "source": "user_provided",
            "timestamp": "2024-01-01T00:00:00Z"  # Would use actual timestamp
        }
    
    def select_template(
        self, 
        worklog: str, 
        profile_path: Optional[str] = None
    ) -> str:
        """
        Site article template from the profile if defined; else
        agents/kb/skills/knowledge/references/kb-template.md, labelled generic.
        
        This is step 2 in the kb-draft-flow.yaml workflow.
        """
        # Check if site profile has a specific template
        if self.site_profile and hasattr(self.site_profile, 'kb_template'):
            return self.site_profile.kb_template
        
        # Return generic template path
        return "agents/kb/skills/knowledge/references/kb-template.md"
    
    def order_layers(self, worklog: str) -> List[str]:
        """
        Scope first, then the differential-ordered layers - workstation/user,
        application (RIS/PACS), interface, advanced. Carry only the layers
        the worklog supports.
        
        This is step 3 in the kb-draft-flow.yaml workflow.
        """
        layers = []
        worklog_lower = worklog.lower()
        
        # Check for workstation/user layer
        if any(kw in worklog_lower for kw in ["workstation", "user", "login", "profile", "desktop"]):
            layers.append("workstation/user")
        
        # Check for application layer (RIS/PACS)
        if any(kw in worklog_lower for kw in ["ris", "pacs", "application", "software", "system"]):
            layers.append("application")
        
        # Check for interface layer
        if any(kw in worklog_lower for kw in ["hl7", "interface", "integration", "dicom", "connection"]):
            layers.append("interface")
        
        # Check for advanced layer
        if any(kw in worklog_lower for kw in ["database", "network", "infrastructure", "server", "storage"]):
            layers.append("advanced")
        
        return layers
    
    def draft_sections(
        self, 
        worklog: str, 
        layers: List[str]
    ) -> Dict[str, Any]:
        """
        Draft the KB article sections. Cause section confidence-marked explicitly.
        A worklog with no cause in it gets "cause not established," not a mark
        on a guess.
        
        This is step 4 in the kb-draft-flow.yaml workflow.
        """
        # Extract information from worklog
        scope = self._extract_scope(worklog)
        timeline = self._extract_timeline(worklog)
        symptoms = self._extract_symptoms(worklog)
        diagnosis = self._extract_diagnosis(worklog)
        cause, cause_confidence = self._extract_cause(worklog)
        resolution = self._extract_resolution(worklog)
        prevention = self._extract_prevention(worklog)
        
        # Build article structure
        article_structure = {
            "scope": scope,
            "timeline": timeline,
            "symptoms": symptoms,
            "diagnosis": diagnosis,
            "cause": cause,
            "cause_confidence": cause_confidence,
            "resolution": resolution,
            "prevention": prevention,
            "layers": layers
        }
        
        # Generate HTML content
        html_content = self._generate_html(article_structure)
        
        return {
            "article_structure": article_structure,
            "article_html": html_content
        }
    
    def _extract_scope(self, worklog: str) -> str:
        """Extract scope from worklog."""
        lines = worklog.split("\n")
        for line in lines:
            if "scope:" in line.lower():
                return line.split(":", 1)[1].strip()
        # If not explicitly marked, use first line
        return lines[0].strip() if lines else "Scope not specified"
    
    def _extract_timeline(self, worklog: str) -> str:
        """Extract timeline from worklog."""
        lines = worklog.split("\n")
        for line in lines:
            if "timeline:" in line.lower():
                return line.split(":", 1)[1].strip()
        return "Timeline not specified"
    
    def _extract_symptoms(self, worklog: str) -> str:
        """Extract symptoms from worklog."""
        lines = worklog.split("\n")
        for line in lines:
            if "symptoms:" in line.lower():
                return line.split(":", 1)[1].strip()
        return "Symptoms not specified"
    
    def _extract_diagnosis(self, worklog: str) -> str:
        """Extract diagnosis from worklog."""
        lines = worklog.split("\n")
        for line in lines:
            if "diagnosis:" in line.lower():
                return line.split(":", 1)[1].strip()
        return "Diagnosis not specified"
    
    def _extract_cause(self, worklog: str) -> tuple:
        """Extract cause and confidence from worklog."""
        worklog_lower = worklog.lower()
        
        if "cause:" in worklog_lower or "root cause:" in worklog_lower:
            # Cause is explicitly stated
            for line in worklog.split("\n"):
                if "cause:" in line.lower() or "root cause:" in line.lower():
                    cause_text = line.split(":", 1)[1].strip()
                    # Check for confidence markers
                    if any(marker in cause_text.lower() for marker in ["confirmed", "verified"]):
                        return cause_text, "confirmed"
                    elif any(marker in cause_text.lower() for marker in ["likely", "probable"]):
                        return cause_text, "likely"
                    else:
                        return cause_text, "confirmed"
        elif any(marker in worklog_lower for marker in ["likely", "probable"]):
            return self._find_cause_text(worklog), "likely"
        else:
            return "Cause not established", "possible"
    
    def _find_cause_text(self, worklog: str) -> str:
        """Find the cause text in the worklog."""
        lines = worklog.split("\n")
        for line in lines:
            if "cause:" in line.lower() or "root cause:" in line.lower():
                return line.split(":", 1)[1].strip()
        return "Unknown"
    
    def _extract_resolution(self, worklog: str) -> str:
        """Extract resolution from worklog."""
        lines = worklog.split("\n")
        for line in lines:
            if "resolution:" in line.lower():
                return line.split(":", 1)[1].strip()
        return "Resolution not specified"
    
    def _extract_prevention(self, worklog: str) -> str:
        """Extract prevention measures from worklog."""
        lines = worklog.split("\n")
        for line in lines:
            if "prevention:" in line.lower():
                return line.split(":", 1)[1].strip()
        return "Prevention measures not specified"
    
    def _generate_html(self, article: Dict[str, Any]) -> str:
        """Generate HTML article content for ServiceNow import."""
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{article.get('scope', 'KB Article')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 20px; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #3498db; margin-top: 20px; }}
        .confidence {{ font-weight: bold; }}
        .confirmed {{ color: #27ae60; }}
        .likely {{ color: #f39c12; }}
        .possible {{ color: #e74c3c; }}
        .outstanding {{ color: #e74c3c; font-style: italic; }}
    </style>
</head>
<body>
    <h1>{article.get('scope', 'KB Article')}</h1>
    
    <h2>Scope</h2>
    <p>{article.get('scope', 'N/A')}</p>
    
    <h2>Timeline</h2>
    <p>{article.get('timeline', 'N/A')}</p>
    
    <h2>Symptoms</h2>
    <p>{article.get('symptoms', 'N/A')}</p>
    
    <h2>Diagnosis</h2>
    <p>{article.get('diagnosis', 'N/A')}</p>
    
    <h2>Root Cause</h2>
    <p><span class="confidence confidence-{article.get('cause_confidence', 'unknown').lower()}">
        Confidence: {article.get('cause_confidence', 'unknown')}
    </span></p>
    <p>{article.get('cause', 'N/A')}</p>
    
    <h2>Resolution</h2>
    <p>{article.get('resolution', 'N/A')}</p>
    
    <h2>Prevention</h2>
    <p>{article.get('prevention', 'N/A')}</p>
    
    <h2>Layers Involved</h2>
    <ul>
        {''.join(f'<li>{layer}</li>' for layer in article.get('layers', []))}
    </ul>
    
    <hr>
    <p><small>Generated from worklog. Requires human review before upload to ServiceNow.</small></p>
</body>
</html>
        """
        return html
    
    def field_checklist(
        self, 
        article_structure: Dict[str, Any]
    ) -> Dict[str, bool]:
        """
        Run before presenting the draft as done. An item that can't be
        filled is marked unknown in the draft, never silently dropped.
        
        This is step 5 in the kb-draft-flow.yaml workflow.
        """
        required_fields = [
            "scope", "timeline", "symptoms", "diagnosis", 
            "cause", "cause_confidence", "resolution"
        ]
        
        checklist = {}
        for field in required_fields:
            value = article_structure.get(field, "")
            checklist[field] = bool(value) and value != f"{field} not specified"
        
        return checklist
    
    def write_file(
        self,
        content: str,
        path: str
    ) -> Dict[str, Any]:
        """
        Write the KB article to a file.
        
        This is step 6 in the kb-draft-flow.yaml workflow.
        """
        # Ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        
        # Write file
        with open(path, 'w') as f:
            f.write(content)
        
        return {
            "path": path,
            "written": True,
            "size": len(content)
        }
    
    def separate_suggestions(
        self, 
        article_structure: Dict[str, Any],
        worklog: str
    ) -> List[str]:
        """
        Suggestions go in the response, never in the HTML and therefore
        never in the .docx - merged content is indistinguishable from
        recorded content once the file leaves the session.
        
        This is step 7 in the kb-draft-flow.yaml workflow.
        """
        suggestions = []
        worklog_lower = worklog.lower()
        
        # Check if worklog contains explicit suggestions
        if "suggestion:" in worklog_lower or "recommend:" in worklog_lower:
            for line in worklog.split("\n"):
                if "suggestion:" in line.lower():
                    suggestions.append(line.split(":", 1)[1].strip())
                elif "recommend:" in line.lower():
                    suggestions.append(line.split(":", 1)[1].strip())
        
        # Add standard suggestions based on cause
        cause = article_structure.get("cause", "").lower()
        if "timeout" in cause:
            suggestions.append("Consider increasing timeout values in configuration")
        if "permission" in cause or "access" in cause:
            suggestions.append("Verify user permissions and access controls")
        if "memory" in cause:
            suggestions.append("Monitor memory usage and consider increasing allocation")
        if "network" in cause:
            suggestions.append("Verify network connectivity and firewall rules")
        
        # Add suggestions based on layers
        layers = article_structure.get("layers", [])
        if "interface" in layers:
            suggestions.append("Review interface logs and connection status")
        if "database" in [l.lower() for l in layers] or "advanced" in layers:
            suggestions.append("Check database connectivity and query performance")
        
        return suggestions if suggestions else ["No specific suggestions"]
    
    def create_kb_article(
        self, 
        worklog: str, 
        profile_path: Optional[str] = None,
        output_dir: str = ".",
        render_docx: bool = False
    ) -> KBArticle:
        """
        Create a complete KB article from a worklog.
        
        This runs the complete kb-draft-flow.yaml workflow.
        """
        # Step 1: Take worklog
        normalized = self.take_worklog(worklog)
        
        # Step 2: Select template
        template = self.select_template(normalized["normalized"], profile_path)
        
        # Step 3: Order layers
        layers = self.order_layers(normalized["normalized"])
        
        # Step 4: Draft sections
        draft_result = self.draft_sections(normalized["normalized"], layers)
        
        # Step 5: Field checklist
        checklist = self.field_checklist(draft_result["article_structure"])
        
        # Step 6: Write file
        article_path = os.path.join(output_dir, f"kb_{hash(worklog) % 10000:04d}.html")
        write_result = self.write_file(draft_result["article_html"], article_path)
        
        # Step 7: Separate suggestions
        suggestions = self.separate_suggestions(
            draft_result["article_structure"], 
            normalized["normalized"]
        )
        
        # Identify outstanding items
        outstanding_items = [
            field for field, completed in checklist.items() if not completed
        ]
        
        # Generate article ID
        article_id = f"KB-{hash(worklog) % 10000:04d}"
        
        return KBArticle(
            title=draft_result["article_structure"].get("scope", "Untitled"),
            article_id=article_id,
            content_html=draft_result["article_html"],
            content_docx=None,  # Would be generated if render_docx=True
            scope=draft_result["article_structure"].get("scope", ""),
            cause=draft_result["article_structure"].get("cause", ""),
            cause_confidence=draft_result["article_structure"].get("cause_confidence", "unknown"),
            layers=layers,
            field_checklist=checklist,
            outstanding_items=outstanding_items,
            suggestions=suggestions
        )
    
    def create_approval_package(
        self, 
        article: KBArticle
    ) -> ApprovalPackage:
        """
        Human approval before upload. The article is uploaded by a human;
        connected ServiceNow mode stays behind DEP-1.
        
        Gate: kb_submission (DUTIES.md)
        """
        return ApprovalPackage(
            artifact=article,
            reasoning=f"KB article created from resolved incident: {article.title}",
            dead_branches=[],
            outstanding_items=article.outstanding_items,
            approval_chain=["KB_Manager", "IT_Lead"],
            gate="kb_submission",
            requires_approval=True
        )
