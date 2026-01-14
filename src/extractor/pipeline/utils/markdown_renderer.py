
import json
import pandas as pd
import io
from pathlib import Path
from typing import Dict, Any, List, Optional

class MarkdownRenderer:
    """
    Handles presentation logic for turning extracted content into Markdown.
    Decouples formatting from data fetching.
    """
    
    def __init__(self, proofs_map: Dict[str, Any] = None, pipeline_dir: Path = None):
        self.proofs_map = proofs_map or {}
        self.pipeline_dir = pipeline_dir

    def format_markdown_table(self, csv_data: str) -> str:
        """Convert CSV string to Markdown table format."""
        try:
            if not csv_data or not csv_data.strip():
                return ""
            df = pd.read_csv(io.StringIO(csv_data))
            if df.empty:
                return ""
            return df.to_markdown(index=False)
        except Exception:
            return f"```csv\n{csv_data}\n```"

    def get_proof_info(self, asset_id: str) -> Dict[str, str]:
        """Resolve proof status and details for an asset."""
        if asset_id not in self.proofs_map:
            return {
                "icon": "❓",
                "text": "Pending",
                "strategy": "unknown",
                "theorem": "`coverage_missing`",
                "code": "",
                "result": "",
                "status": "pending"
            }
        
        p = self.proofs_map[asset_id]
        status = p.get('status', 'pending')
        
        info = {
            "strategy": p.get('strategy', "unknown"),
            "code": p.get('code', ""),
            "result": p.get('result', ""),
            "status": status
        }

        if status == 'verified':
            info["icon"] = "✅"
            info["text"] = "Verified"
        elif status == 'failed':
            info["icon"] = "❌"
            info["text"] = "Failed"
        else:
            info["icon"] = "⚠️"
            info["text"] = status

        # Extract theorem name snippet
        code_txt = info["code"] or ""
        if "theorem" in code_txt:
            try:
                parts = code_txt.split("theorem", 1)[1].strip().split()
                if parts:
                    info["theorem"] = f"`{parts[0]}`"
                else:
                    info["theorem"] = "`theorem...`"
            except IndexError:
                info["theorem"] = "`theorem...`"
        else:
            snippet = code_txt.replace("\n", " ")[:20]
            info["theorem"] = f"`{snippet}...`" if snippet else "`no_code`"
            
        return info

    def render_summary_table(self, req_items: List[Any]) -> List[str]:
        """Generate the Requirement Proof Summary table lines."""
        if not req_items:
            return []
            
        lines = [
            "",
            "### Requirement Proof Summary",
            "",
            "| ID | Type | Status | Theorem |",
            "| :--- | :--- | :--- | :--- |"
        ]
        
        for _, _, _, meta_json, asset_id in req_items:
            meta = json.loads(meta_json) if meta_json else {}
            req_id = meta.get('req_id') or "REQ-UNKNOWN"
            req_type = (meta.get('type') or "FUNCTION").upper()
            if meta.get('is_conditional'): req_type = "CONDITIONAL"
            
            p_info = self.get_proof_info(asset_id)
            
            lines.append(f"| **{req_id}** | {req_type} | {p_info['icon']} {p_info['text']} | {p_info['theorem']} |")
        
        lines.append("")
        lines.append("")
        return lines

    def render_inline_proof(self, asset_id: str) -> List[str]:
        """Generate inline proof details block."""
        if asset_id not in self.proofs_map:
            return []
            
        p_info = self.get_proof_info(asset_id)
        
        code_snippet = p_info['code'].replace("\n", " ")
        if len(code_snippet) > 100: code_snippet = code_snippet[:100] + "..."
        
        result_msg = p_info['result'].replace("\n", " ")
        if len(result_msg) > 100: result_msg = result_msg[:100] + "..."

        lines = [
            ">",
            ">",
            "> <details>",
            f"> <summary>{p_info['icon']} <b>Proof:</b> {p_info['text']} ({p_info['strategy']})</summary>",
            ">",
            "> ```lean",
            f"> {code_snippet}",
            "> ```"
        ]
        if p_info['result']:
            lines.append(f"> *Result: {result_msg}*")
        lines.append("> </details>")
        return lines

    def render_text(self, content: str) -> List[str]:
        if content and content.strip():
            return [content.strip(), ""]
        return []

    def render_table(self, content: str, meta: Dict[str, Any]) -> List[str]:
        lines = []
        title = meta.get('title') or "Table"
        desc = meta.get('desc') or ""
        lines.append(f"### {title}")
        if desc:
            lines.append(f"> *{desc}*")
        lines.append("")
        
        table_md = self.format_markdown_table(content)
        if not table_md:
             lines.append("> ⚠️ **Warning: Table data could not be extracted or is empty.**")
        else:
            lines.append(table_md)
        lines.append("")
        return lines

    def render_figure(self, content: str, meta: Dict[str, Any]) -> List[str]:
        lines = []
        title = meta.get('title') or "Figure"
        desc = meta.get('desc') or ""
        
        # Compute relative path for portability if pipeline_dir is set
        img_rel = "unknown.png"
        if content:
            try:
                img_abs = Path(content)
                if self.pipeline_dir and img_abs.is_absolute():
                     # Try to make relative
                     try:
                        img_rel = img_abs.relative_to(self.pipeline_dir)
                     except ValueError:
                        # Not under pipeline dir
                        img_rel = img_abs.name
                else:
                    img_rel = Path(content).name
            except Exception:
                img_rel = content

        lines.append(f"### {title}")
        lines.append(f"![{title}]({img_rel})")
        if desc:
            lines.append(f"> *{desc}*")
        lines.append("")
        return lines

    def render_requirement(self, content: str, meta: Dict[str, Any], asset_id: str) -> List[str]:
        lines = []
        req_id = meta.get('req_id') or "REQ-UNKNOWN"
        citation = meta.get('citation') or ""
        req_type = meta.get('type') or "requirement"
        is_cond = bool(meta.get('is_conditional', False))
        
        type_tag = ""
        if is_cond:
            type_tag = " [CONDITIONAL]"
        elif req_type and req_type.lower() != "requirement":
             type_tag = f" [{req_type.upper()}]"

        lines.append(f"> **[{req_id}]{type_tag}** {content}")
        if citation:
             lines.append(f"> *Source: \"{citation}\"*")
        
        lines.extend(self.render_inline_proof(asset_id))
        lines.append("")
        return lines
