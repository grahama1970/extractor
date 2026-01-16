#!/usr/bin/env python3
"""
Stage 08: Focused Requirement Extraction

Uses parallel_acompletions_iter for batch LLM processing.

1. Query "Clean Corpus" from DuckDB (Sections + Clean Blocks + Tables).
2. Filter for relevant sections (heuristic: "shall", "must", or Table).
3. Batch prompt the LLM to extract requirements with VERBATIM citation snippets.
4. Store results in the `requirements` table.
"""

import asyncio
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import duckdb
import json_repair
from dotenv import find_dotenv, load_dotenv
from loguru import logger
from rapidfuzz import fuzz
from scillm.batch import parallel_acompletions_iter

from extractor.pipeline.utils.db.connection import get_connection
from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight
from extractor.pipeline.utils.diagnostics import get_run_id
from extractor.pipeline.utils.step_sanity import run_step_sanity

load_dotenv(find_dotenv(usecwd=True), override=False)

STEP_NAME = "08_extract_requirements"

# Configuration
THRESHOLD_CONFIDENCE = 0.5
THRESHOLD_CITATION_MATCH = 80.0
SORT_ORDER_PAGE_MULTIPLIER = 10000
SORT_ORDER_BLOCK_INCREMENT = 10
CONCURRENCY = int(os.getenv("STAGE08_CONCURRENCY", "8"))
MODEL = os.getenv("CHUTES_TEXT_MODEL", "openai/gpt-4o")


def load_pdf_profile(pdf_path: Path) -> Dict[str, Any]:
    """Load PDF-specific extraction profile with requirement examples.
    
    Searches for:
    1. {pdf_name}_profile.json in same directory as PDF
    2. {pdf_name}_profile.json in project root
    3. requirement_patterns.yaml in same directory as PDF (YAML patterns)
    4. Falls back to empty profile if not found
    """
    if not pdf_path or not pdf_path.exists():
        logger.warning("No PDF path provided for profile loading")
        return {}
    
    pdf_name = pdf_path.stem  # e.g., "BHT_CV32A65X"
    profile_name = f"{pdf_name}_profile.json"
    
    # Search locations for JSON profile
    search_paths = [
        pdf_path.parent / profile_name,  # Same dir as PDF
        Path.cwd() / profile_name,        # Project root
    ]
    
    for profile_path in search_paths:
        if profile_path.exists():
            try:
                profile = json.loads(profile_path.read_text())
                logger.info(f"Loaded extraction profile from {profile_path}")
                return profile
            except Exception as e:
                logger.warning(f"Failed to load profile {profile_path}: {e}")
    
    # Also check for YAML patterns file (fixture pattern)
    # Search multiple locations since PDF may be in results dir, not fixture dir
    yaml_search_paths = [
        pdf_path.parent / "requirement_patterns.yaml",  # Same dir as PDF
        # Standard fixture locations
        Path(__file__).resolve().parents[4] / "tools" / "tasks_loop" / "fixtures" / pdf_name / "requirement_patterns.yaml",
        Path(__file__).resolve().parents[4] / "tools" / "tasks_loop" / "fixtures" / pdf_name.replace("source", "") / "requirement_patterns.yaml",
        # Also check for patterns based on common fixture naming (e.g., BHT_Mutant_Eq)
        Path.cwd() / "fixtures" / pdf_name / "requirement_patterns.yaml",
        Path.cwd() / "tools" / "tasks_loop" / "fixtures" / pdf_name / "requirement_patterns.yaml",
    ]
    
    for yaml_patterns_path in yaml_search_paths:
        if yaml_patterns_path.exists():
            try:
                import yaml
                patterns = yaml.safe_load(yaml_patterns_path.read_text())
                logger.info(f"Loaded requirement patterns from {yaml_patterns_path}")
                return {"requirement_patterns": patterns}
            except Exception as e:
                logger.warning(f"Failed to load YAML patterns {yaml_patterns_path}: {e}")
    
    # Fallback to Global Domain Patterns
    global_config = Path.cwd() / "data" / "config" / "domain_patterns.yml"
    if global_config.exists():
        try:
            import yaml
            patterns = yaml.safe_load(global_config.read_text())
            logger.info(f"Loaded global domain patterns from {global_config}")
            return {"requirement_patterns": patterns}
        except Exception as e:
            logger.warning(f"Failed to load global config {global_config}: {e}")

    logger.info(f"No profile found for {pdf_name}, using defaults")
    return {}


def ensure_requirements_metadata_column(con: duckdb.DuckDBPyConnection) -> None:
    """Ensure requirements.metadata_json exists for bbox metadata."""
    cols = con.execute("PRAGMA table_info('requirements')").fetchall()
    names = {c[1] for c in cols}
    if "metadata_json" not in names:
        con.execute("ALTER TABLE requirements ADD COLUMN metadata_json VARCHAR")


def _load_section_bbox_map(pipeline_dir: Path) -> Dict[str, Dict[str, Any]]:
    sections_json = pipeline_dir / "04_section_builder" / "json_output" / "04_sections.json"
    if not sections_json.exists():
        return {}
    try:
        data = json.loads(sections_json.read_text())
    except Exception:
        return {}
    by_id: Dict[str, Dict[str, Any]] = {}
    for sec in data.get("sections") or []:
        sid = sec.get("id") or sec.get("section_id")
        if sid is None:
            continue
        by_id[str(sid)] = sec
    return by_id


def _match_bbox_from_blocks(
    citation: str,
    blocks: List[Tuple[Any, Any, Any, Any, Any, Any]],
) -> Tuple[int, List[float]] | None:
    needle = (citation or "").strip().lower()
    if not needle:
        return None
    best = None
    best_score = 0.0
    for page, x0, y0, x1, y1, text in blocks:
        if not text:
            continue
        candidate = str(text).lower()
        if needle in candidate:
            return int(page), [float(x0), float(y0), float(x1), float(y1)]
        score = fuzz.partial_ratio(needle, candidate)
        if score > best_score:
            best_score = score
            best = (page, x0, y0, x1, y1)
    if best and best_score >= THRESHOLD_CITATION_MATCH:
        page, x0, y0, x1, y1 = best
        return int(page), [float(x0), float(y0), float(x1), float(y1)]
    return None


def _match_bbox_from_tables(
    citation: str,
    tables: List[Tuple[Any, Any, Any, Any, Any, Any]],
) -> Tuple[int, List[float]] | None:
    needle = (citation or "").strip().lower()
    if not needle:
        return None
    best = None
    best_score = 0.0
    for page, x0, y0, x1, y1, csv_data in tables:
        if not csv_data:
            continue
        candidate = str(csv_data).lower()
        if needle in candidate:
            return int(page), [float(x0), float(y0), float(x1), float(y1)]
        score = fuzz.partial_ratio(needle, candidate)
        if score > best_score:
            best_score = score
            best = (page, x0, y0, x1, y1)
    if best and best_score >= THRESHOLD_CITATION_MATCH:
        page, x0, y0, x1, y1 = best
        return int(page), [float(x0), float(y0), float(x1), float(y1)]
    return None


def _resolve_requirement_bbox(
    *,
    citation: str,
    is_table_row: bool,
    section_id: str,
    page_start: int | None,
    blocks: List[Tuple[Any, Any, Any, Any, Any, Any]],
    tables: List[Tuple[Any, Any, Any, Any, Any, Any]],
    section_map: Dict[str, Dict[str, Any]],
    debug: bool,
) -> Tuple[int, List[float], str]:
    if is_table_row:
        match = _match_bbox_from_tables(citation, tables)
        if match:
            return match[0], match[1], "table"
    match = _match_bbox_from_blocks(citation, blocks)
    if match:
        return match[0], match[1], "block"

    if debug:
        raise RuntimeError(
            f"Missing bbox for requirement (section={section_id}) citation match failed."
        )

    sec = section_map.get(str(section_id)) or {}
    bbox = sec.get("bbox")
    if isinstance(bbox, list) and len(bbox) == 4:
        page = int(sec.get("page_start", page_start or 0) or 0)
        return page, [float(v) for v in bbox], "section"

    page = int(page_start or 0)
    return page, [0.0, 0.0, 0.0, 0.0], "unknown"

def get_section_content(con: duckdb.DuckDBPyConnection, section_id: str) -> Tuple[str, List[str], List[str]]:
    """Fetches text, tables, and figures for a section."""
    blocks = con.execute("""
        SELECT text 
        FROM blocks 
        WHERE section_id = ?
        AND id IN (SELECT id FROM v_clean_blocks)
        ORDER BY page, round(y0/10)*10, x0
    """, [section_id]).fetchall()
    
    text_content = "\n".join([b[0] for b in blocks if b[0]])
    
    tables = con.execute("""
        SELECT csv_data 
        FROM tables 
        WHERE section_id = ?
    """, [section_id]).fetchall()
    table_content = [t[0] for t in tables if t[0]]
    
    figures = con.execute("""
        SELECT image_path 
        FROM figures 
        WHERE section_id = ?
    """, [section_id]).fetchall()
    figure_content = [f[0] for f in figures if f[0]]
    
    return text_content, table_content, figure_content


def heuristic_is_relevant(text: str, tables: List[str]) -> bool:
    """Fast filter to skip sections unlikely to contain requirements."""
    if tables:
        return True
    
    keywords = ["shall", "must", "require", "constraint", "comply", "will", "should", "tied to"]
    text_lower = text.lower()
    for kw in keywords:
        if kw in text_lower:
            return True
    return False


def convert_tables_to_requirements(
    con: duckdb.DuckDBPyConnection,
    profile: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Convert merged tables (S05c output) directly to requirement entities.
    
    This is used when the profile specifies `tables_are_requirements: true`.
    In BHT documents, tables like Table 4-2, Table 4-3 define behavioral specs,
    not just data. We treat each table as a requirement.
    
    Args:
        con: DuckDB connection with populated `tables` table.
        profile: Extraction profile with requirement_patterns.
        
    Returns:
        List of requirement dicts ready for DB insertion.
    """
    patterns = profile.get("requirement_patterns", {})
    if not patterns.get("tables_are_requirements", False):
        return []
    
    logger.info("Converting tables to requirements (tables_are_requirements=true)")
    
    # Query merged tables from S05c
    tables = con.execute("""
        SELECT id, section_id, llm_title, llm_description, csv_data, page, x0, y0, x1, y1
        FROM tables
    """).fetchall()
    
    requirements = []
    for t_id, sec_id, title, desc, csv_data, page, x0, y0, x1, y1 in tables:
        # Generate requirement text from table title/description
        req_text = f"{title or 'Table'}: {desc or 'Defines behavioral specification.'}"
        if csv_data:
            # Extract first row as summary if available
            lines = csv_data.strip().split("\n")
            if len(lines) > 1:
                req_text += f" Data columns: {lines[0]}"
        
        req_id = f"TBL-{t_id[:8].upper()}" if t_id else "TBL-UNKNOWN"
        
        requirements.append({
            "id": t_id,  # Use table ID as requirement ID (linkage)
            "req_id": req_id,
            "text": req_text,
            "type": "table_requirement",
            "section_id": sec_id,
            "citation_snippet": title or "Table",
            "confidence": 1.0,  # Deterministic - we know it's a table
            "is_table_row": True,
            "source": "table_promotion",
            "page": page,
            "bbox": [x0 or 0, y0 or 0, x1 or 0, y1 or 0],
        })
    
    logger.info(f"Promoted {len(requirements)} tables to requirements")
    return requirements


def verify_citation(snippet: str, full_text: str, table_texts: List[str]) -> float:
    """Checks if the snippet exists in the source text or tables."""
    if not snippet:
        return 0.0
        
    score_text = fuzz.partial_ratio(snippet.lower(), full_text.lower())
    if score_text >= THRESHOLD_CITATION_MATCH:
        return score_text
        
    for tbl in table_texts:
        score_tbl = fuzz.partial_ratio(snippet.lower(), tbl.lower())
        if score_tbl >= THRESHOLD_CITATION_MATCH:
            return score_tbl
            
    return score_text


def extract_requirements_deterministic(text: str, profile: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Extract requirements using deterministic regex patterns to anchor LLM.
    
    This prevents hallucinations by finding clear requirement statements first.
    LLM then validates/classifies these rather than generating from scratch.
    """
    profile = profile or {}
    results = []
    
    # Get patterns from profile or use defaults
    patterns = profile.get("requirement_patterns", {})
    modal_verbs = patterns.get("modal_verbs", ["shall", "must", "will"])
    id_prefixes = patterns.get("id_prefixes", ["REQ-"])
    
    # Build dynamic pattern that captures FULL requirement until sentence boundary
    # E.g., if id_prefixes = ["REQ-BHT-", "REQ-"], pattern matches both
    # Pattern: REQ-XXX: ... text until (period + space/newline) OR (double newline) OR (next REQ-)
    # Use lookahead to stop at boundaries without consuming them
    prefix_pattern = '|'.join(re.escape(p) for p in id_prefixes)
    formal_pattern = rf'({prefix_pattern}[\w-]+):\s*(.+?)(?=\.\s+[A-Z]|\n\n|{prefix_pattern}|$)'
    
    for match in re.finditer(formal_pattern, text, re.IGNORECASE | re.DOTALL):
        req_id = match.group(1)
        req_text = match.group(2).strip()
        results.append({
            "id": req_id,
            "text": req_text,
            "citation_snippet": match.group(0),
            "source": "regex_formal"
        })
    
    # Pattern 2: Sentences with shall/must/will (no explicit ID)
    modal_pattern = r'([^.]+?(?:' + '|'.join(modal_verbs) + r')[^.]+?\.)'
    for match in re.finditer(modal_pattern, text, re.IGNORECASE):
        sentence = match.group(1).strip()
        # Skip if already captured by Pattern 1
        if any(r["citation_snippet"] in sentence for r in results):
            continue
        results.append({
            "id": None,
            "text": sentence,
            "citation_snippet": sentence,
            "source": "regex_modal"
        })
    
    # Pattern 3: Conditional requirements (When X: Y, If X, Y)
    conditional_patterns = patterns.get("conditional_patterns", [])
    conditional_keywords = patterns.get("conditional_keywords", ["when", "if"])
    
    for cp in conditional_patterns:
        pattern_str = cp.get("pattern")
        source = cp.get("source", "conditional")
        if not pattern_str:
            continue
        try:
            for match in re.finditer(pattern_str, text, re.IGNORECASE | re.DOTALL):
                condition = match.group("condition") if "condition" in match.groupdict() else ""
                req_text = match.group("text").strip() if "text" in match.groupdict() else match.group(0).strip()
                # Skip if already captured
                if any(req_text in r.get("text", "") for r in results):
                    continue
                results.append({
                    "id": None,
                    "text": req_text,
                    "citation_snippet": match.group(0),
                    "source": source,
                    "is_conditional": True,
                    "condition": condition.strip() if condition else None
                })
        except re.error as e:
            logger.warning(f"Invalid conditional pattern '{pattern_str}': {e}")
    
    # Also flag existing results as conditional if they contain conditional keywords
    for r in results:
        if not r.get("is_conditional"):
            text_lower = r.get("text", "").lower()
            for kw in conditional_keywords:
                # Use word boundary check: keyword at start, after punctuation, or surrounded by spaces
                kw_lower = kw.lower()
                if (
                    text_lower.startswith(kw_lower + " ") or
                    f" {kw_lower} " in text_lower or
                    f": {kw_lower} " in text_lower or  # Handle "REQ-XXX: If ..."
                    f"- {kw_lower} " in text_lower or  # Handle "- If ..."
                    re.search(rf'\b{re.escape(kw_lower)}\b', text_lower)  # Word boundary
                ):
                    r["is_conditional"] = True
                    break
    
    logger.info(f"Deterministic extraction found {len(results)} requirement candidates")
    return results


def build_prompt(title: str, text: str, tables: List[str], profile: Dict[str, Any] = None, deterministic_reqs: List[Dict[str, Any]] = None) -> Tuple[str, str]:
    """Build extraction prompt.
    
    Returns: (system_message, user_message)
    """
    # System message - NO profile complexity, just hard explicit instructions
    system_msg = """You are a Senior Systems Engineer extracting formal requirements from a specification.

TASK:
Read the provided text and extract EVERY sentence that is a requirement.
A requirement is any statement containing: "shall", "must", "will", "should", or "required".

OUTPUT FORMAT:
Return a JSON Object with a single key "requirements" containing a list of objects.
{
  "requirements": [
    {
      "id": "REQ-123 (or null if none)",
      "text": "The system shall do X...",
      "type": "Function",
      "confidence": 1.0
    }
  ]
}

RULES:
1. Extract the FULL sentence. Do not truncate.
2. If a requirement has an ID (like REQ-BHT-1), capture it.
3. You MUST extract all requirements found. The input text typically contains 10-20 requirements.
4. Do not output markdown code blocks, just the raw JSON object.
"""
    
    # User message - Clean input with explicit one-shot example from THIS document style
    user_msg = f"""Section: \"{title}\"

TEXT TO ANALYZE:
{text}

Tables:
{chr(10).join(tables) if tables else '(none)'}

ONE-SHOT EXAMPLE (Mental Model):
Input: "REQ-BHT-1: The BHT shall accept update information."
Output: {{"id": "REQ-BHT-1", "text": "The BHT shall accept update information.", "type": "Function", "confidence": 1.0}}

ACTION:
Extract ALL requirements from the text above. Expect ~15 items.
"""
    
    return system_msg, user_msg


async def process_sections_batch(
    sections_data: List[Dict[str, Any]],
    con: duckdb.DuckDBPyConnection,
    profile: Dict[str, Any] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """Process sections using true HYBRID approach (Regex Anchors + LLM Discovery).
    
    Strategy:
    1. Deterministic Regex: Finds high-precision "anchors" (REQ-123, 'shall'). 
       - CRITICAL: Use fixed regex that captures full sentences, not truncated fragments.
    2. LLM Extraction: Scans full text to:
       - Verify and classify the regex anchors.
       - Find "edge case" requirements the regex missed (weird phrasing, no 'shall', etc).
       - Handle high variability in input formats.
    """
    
    api_key = os.getenv("CHUTES_API_KEY")
    api_base = os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1")
    profile = profile or {}
    
    requests = []
    section_map = {}
    deterministic_map = {}  # Store deterministic results by index to avoid scope issues
    
    for idx, sec in enumerate(sections_data):
        # Step 1: Deterministic extraction (High Precision)
        deterministic_reqs = extract_requirements_deterministic(sec["text"], profile)
        deterministic_map[idx] = deterministic_reqs
        
        # Step 2: Build Prompt (High Recall)
        system_msg, user_msg = build_prompt(
            sec["title"], 
            sec["text"], 
            sec["tables"],
            profile=profile,
            deterministic_reqs=deterministic_reqs
        )
        
        requests.append({
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "index": idx
        })
        section_map[idx] = sec["section_id"]
        
        # Debug logs...
    
    if not requests:
        return {}
    
    logger.info(f"Processing {len(requests)} sections with {MODEL} (Hybrid Extraction)...")
    
    results: Dict[str, List[Dict[str, Any]]] = {}
    
    async for r in parallel_acompletions_iter(
        requests,
        api_base=api_base,
        api_key=api_key,
        concurrency=CONCURRENCY,
        timeout=120,
        response_format={"type": "json_object"},
        repair_invalid_json=True,
    ):
        idx = r.get("index")
        section_id = section_map.get(idx)
        if not section_id: continue
        
        # Retrieve correct deterministic reqs for THIS section
        section_deterministic_reqs = deterministic_map.get(idx, [])
        
        # Parsing Logic
        extracted = []
        try:
            content = r.get("content")
            parsed = r.get("parsed")
            
            data = {}
            if isinstance(parsed, dict) and parsed:
                data = parsed
            elif isinstance(content, dict):
                data = content
            elif isinstance(content, str):
                 try:
                     import json_repair
                     data = json_repair.loads(content)
                 except: pass
            
            if isinstance(data, list):
                extracted = data
            elif isinstance(data, dict):
                extracted = data.get("requirements", [])
                
        except Exception as e:
            logger.error(f"Failed to parse LLM response for {section_id}: {e}")
            
        if not extracted and section_deterministic_reqs:
             logger.warning(f"Section {section_id}: LLM returned 0 items. Falling back to deterministic anchors.")
             extracted = [] 
        
        # Step 3: UNION MERGE - Ensure no Regex Anchors were lost
        final_reqs = []
        
        # Helper for fuzzy matching
        def normalize(t): return re.sub(r'\s+', ' ', t.lower().strip())
        
        llm_texts = {normalize(r.get("text", "")) for r in extracted}
        llm_ids = {r.get("citation_snippet", "").split(':')[0] for r in extracted if ":" in r.get("citation_snippet", "")}
        
        # Add all LLM results first
        final_reqs.extend(extracted)
        
        logger.info(f"Section {section_id}: Merge check - Deterministic={len(section_deterministic_reqs)}, LLM={len(extracted)}")
        
        # Check for missing anchors
        added_anchors = 0
        for anchor in section_deterministic_reqs:
            anchor_norm = normalize(anchor["text"])
            anchor_id = anchor.get("id")
            
            # Check if this anchor was caught by LLM
            match_found = False
            if anchor_id and anchor_id in llm_ids:
                match_found = True
            elif any(anchor_norm in t or t in anchor_norm for t in llm_texts):
                match_found = True
            
            if not match_found:
                logger.warning(f"Section {section_id}: Force-merging regex anchor: {anchor['id']} ({anchor['text'][:30]}...)")
                final_reqs.append({
                    "id": anchor["id"],  # Pass the ID!
                    "text": anchor["text"],
                    "type": "Function",
                    "confidence": 0.99, # High confidence for regex
                    "citation_snippet": anchor.get("citation_snippet", anchor["text"]),
                    "is_conditional": "when" in anchor["text"].lower() or "if" in anchor["text"].lower(),
                    "condition_text": None
                })
                added_anchors += 1
            else:
                 logger.info(f"Section {section_id}: Regex anchor {anchor['id']} was successfully matched by LLM.")
        
        if added_anchors > 0:
            logger.info(f"Section {section_id}: Force-merged {added_anchors} missed regex anchors")
        
        results[section_id] = final_reqs
        logger.info(f"Section {section_id}: Final count {len(final_reqs)} (Hybrid Union)")
        
    return results


def run_extract_requirements(pipeline_dir: Path, db_path: Path) -> int:
    """Main entry point for Stage 08."""
    require_scillm_preflight()
    
    logger.info("Starting Stage 08: Focused Extraction (Batch)")
    t0 = time.monotonic()
    
    run_id = get_run_id()  # Track this execution for safe cleanup
    logger.info(f"Run ID: {run_id}")
    
    con = get_connection(db_path)
    ensure_requirements_metadata_column(con)
    debug_visuals = os.getenv("CONTRACT_LOOP_DEBUG_VISUALS", "0").lower() in {"1", "true", "yes", "y"}
    section_bbox_map = _load_section_bbox_map(pipeline_dir)
    
    # Load PDF profile for examples - get fixture name from status.json
    profile = {}
    fixture_name = None
    
    # Try to get fixture name from status.json
    status_path = pipeline_dir / "status.json"
    if status_path.exists():
        try:
            status = json.loads(status_path.read_text())
            fixture_name = status.get("fixture")
            if fixture_name:
                logger.info(f"Fixture name from status.json: {fixture_name}")
        except Exception as e:
            logger.debug(f"Could not read status.json: {e}")
    
    # Load profile using fixture name if available
    if fixture_name:
        # Search fixture directories for patterns YAML
        yaml_search_paths = [
            Path(__file__).resolve().parents[4] / "tools" / "tasks_loop" / "fixtures" / fixture_name / "requirement_patterns.yaml",
            Path.cwd() / "tools" / "tasks_loop" / "fixtures" / fixture_name / "requirement_patterns.yaml",
            Path.cwd() / "fixtures" / fixture_name / "requirement_patterns.yaml",
        ]
        for yaml_path in yaml_search_paths:
            if yaml_path.exists():
                try:
                    import yaml
                    patterns = yaml.safe_load(yaml_path.read_text())
                    logger.info(f"✅ Loaded requirement patterns from {yaml_path}")
                    profile = {"requirement_patterns": patterns}
                    break
                except Exception as e:
                    logger.warning(f"Failed to load YAML patterns {yaml_path}: {e}")
    
    # Fallback: search for PDF-based profile
    if not profile:
        pdf_files = list(pipeline_dir.rglob("*.pdf"))
        if pdf_files:
            pdf_path = pdf_files[0]
            logger.info(f"Found PDF: {pdf_path.name}")
            profile = load_pdf_profile(pdf_path)
            if profile:
                logger.info(f"✅ Loaded profile: {profile.get('pdf_name', 'unknown')}")
            else:
                logger.info(f"No profile found for {pdf_path.stem}, using defaults")
        else:
            logger.warning("No PDF found in pipeline directory")
    
    # Promote tables to requirements if profile flag is set
    table_requirements = convert_tables_to_requirements(con, profile)
    if table_requirements:
        logger.info(f"Will insert {len(table_requirements)} table-based requirements")
    
    # Idempotency Check
    existing_req_counts = {}
    try:
        existing = con.execute("SELECT section_id, COUNT(*) FROM requirements GROUP BY section_id").fetchall()
        existing_req_counts = {row[0]: row[1] for row in existing}
        if existing_req_counts:
            total_existing = sum(existing_req_counts.values())
            logger.info(f"Found {total_existing} existing requirements across {len(existing_req_counts)} sections")
    except duckdb.CatalogException:
        logger.debug("requirements table may not exist yet")
    
    # Fetch Sections (Targeted for Verification)
    sections = con.sql("""
        SELECT id, title, page_start 
        FROM sections 
        ORDER BY page_start, id
    """).fetchall()
    logger.info(f"Found {len(sections)} sections in corpus (Filtered).")
    
    # Prepare section data for batch processing
    sections_data = []
    for s_id, title, page_start in sections:
        # Skip already processed
        if s_id in existing_req_counts:
            continue
            
        text, tables, figures = get_section_content(con, s_id)
        
        # Heuristic filter
        if not heuristic_is_relevant(text, tables):
            continue
        
        # Extract section number
        section_number = ""
        num_match = re.match(r'^(\d+(?:\.\d+)*)', str(title or "").strip())
        if num_match:
            section_number = num_match.group(1)
        
        sections_data.append({
            "section_id": s_id,
            "title": str(title),
            "text": text,
            "tables": tables,
            "page_start": page_start,
            "section_number": section_number,
        })
    
    if not sections_data:
        logger.info("No new sections to process.")
        return 0
    
    logger.info(f"Processing {len(sections_data)} relevant sections...")
    
    # Run batch extraction (async)
    extraction_results = asyncio.run(process_sections_batch(sections_data, con, profile))
    
    # Process results and insert into DB
    requirements_batch = []
    merged_content_batch = []
    global_req_idx = 0
    
    try:
        max_sort = con.sql("SELECT COALESCE(MAX(sort_order), 0) FROM merged_content").fetchone()[0]
    except Exception:
        max_sort = 0
    
    for sec in sections_data:
        s_id = sec["section_id"]
        title = sec["title"]
        text = sec["text"]
        tables = sec["tables"]
        page_start = sec["page_start"]
        section_number = sec["section_number"]

        block_rows = con.execute(
            """
            SELECT page, x0, y0, x1, y1, text
            FROM v_clean_blocks
            WHERE section_id = ?
            ORDER BY page, y0, x0
            """,
            [s_id],
        ).fetchall()
        table_rows = con.execute(
            """
            SELECT page, x0, y0, x1, y1, csv_data
            FROM tables
            WHERE section_id = ?
            """,
            [s_id],
        ).fetchall()
        
        extracted = extraction_results.get(s_id, [])
        if not extracted:
            continue
        
        # Get section sort base (fallback) and text blocks for alignment
        try:
            result = con.execute(
                "SELECT MIN(sort_order) FROM merged_content WHERE section_id = ?", [s_id]
            ).fetchone()
            section_sort_base = (result[0] if result and result[0] else None) or (page_start * SORT_ORDER_PAGE_MULTIPLIER)
        except Exception:
            section_sort_base = page_start * SORT_ORDER_PAGE_MULTIPLIER if page_start else max_sort
        
        # Fetch existing text blocks to align sort order
        text_blocks = con.execute("""
            SELECT id, content, sort_order 
            FROM merged_content 
            WHERE section_id = ? AND type = 'text'
            ORDER BY sort_order
        """, [s_id]).fetchall()
        
        section_req_idx = 0
        
        for item in extracted:
            req_text = item.get("text")
            if not req_text:
                continue
                
            req_type = item.get("type", "Unknown")
            conf = float(item.get("confidence", 0.5))
            citation = item.get("citation_snippet", "")
            is_tbl = bool(item.get("is_table_row", False))
            is_conditional = bool(item.get("is_conditional", False))
            condition_text = item.get("condition_text") or None
            
            # Apply keyword detection if not already flagged
            if not is_conditional and req_text:
                patterns = profile.get("requirement_patterns", {})
                conditional_keywords = patterns.get("conditional_keywords", ["when", "if"])
                text_lower = req_text.lower()
                for kw in conditional_keywords:
                    kw_lower = kw.lower()
                    if (
                        text_lower.startswith(kw_lower + " ") or
                        f" {kw_lower} " in text_lower or
                        f": {kw_lower} " in text_lower or
                        f"- {kw_lower} " in text_lower
                    ):
                        is_conditional = True
                        break
            
            # Verify citation
            match_score = verify_citation(citation, text, tables)
            if match_score < THRESHOLD_CITATION_MATCH:
                conf = conf * 0.8
            
            # Generate IDs (unless provided)
            global_req_idx += 1
            section_req_idx += 1
            
            existing_id = item.get("id")
            if existing_id and str(existing_id).startswith("REQ-"):
                req_id = existing_id
            elif section_number:
                req_id = f"REQ-{section_number}-{section_req_idx:03d}"
            else:
                req_id = f"REQ-{global_req_idx:04d}"
            
            id_hash = hashlib.sha1(f"{s_id}:{req_id}".encode()).hexdigest()[:12]
            r_id = f"req_{id_hash}"
            
            # Determine Sort Order based on Citation Match
            sort_order = section_sort_base  # Fallback
            if citation and len(citation) > 10:
                best_ratio = 0
                for blk_id, blk_content, blk_sort in text_blocks:
                    # Simple inclusion check first
                    if citation in blk_content:
                        sort_order = blk_sort + 1  # Place immediately after
                        break
                    # Fuzzy fallback
                    ratio = fuzz.partial_ratio(citation.lower(), blk_content.lower())
                    if ratio > best_ratio and ratio > 60:
                        best_ratio = ratio
                        sort_order = blk_sort + 1
            
            # Offset slightly to prevent collisions if multiple reqs map to same block
            sort_order += (section_req_idx * 0.1)

            page, bbox, bbox_source = _resolve_requirement_bbox(
                citation=citation,
                is_table_row=is_tbl,
                section_id=str(s_id),
                page_start=page_start,
                blocks=block_rows,
                tables=table_rows,
                section_map=section_bbox_map,
                debug=debug_visuals,
            )
            y0 = float(bbox[1]) if bbox else 0.0
            metadata_json = json.dumps(
                {"page": page, "bbox": bbox, "bbox_source": bbox_source},
                ensure_ascii=True,
            )
            
            requirements_batch.append((
                r_id, req_id, s_id, req_text, req_type, conf, citation,
                is_tbl, is_conditional, condition_text, sort_order, page, y0, metadata_json, run_id
            ))
            
            mc_id = f"mc_{r_id}"
            prefix = "REQ: " + req_id
            if is_conditional:
                prefix += " [CONDITIONAL]"
            content_str = f"{prefix} {req_text}"
            
            merged_content_batch.append((
                mc_id, s_id, page, "requirement", content_str, r_id, sort_order
            ))
    
    # Insert all
    # Also add table-promoted requirements if any
    for tr in table_requirements:
        requirements_batch.append((
            tr["id"], tr["req_id"], tr["section_id"], tr["text"], tr["type"],
            tr["confidence"], tr["citation_snippet"], tr["is_table_row"], False,
            None, 0, tr["page"], tr["bbox"][1] if tr["bbox"] else 0.0,
            json.dumps({"page": tr["page"], "bbox": tr["bbox"], "bbox_source": "table_promotion"}),
            run_id
        ))
        # Also add to merged_content for export
        mc_id = f"mc_{tr['id']}"
        content_str = f"TBL-REQ: {tr['req_id']} {tr['text']}"
        merged_content_batch.append((
            mc_id, tr["section_id"], tr["page"], "table_requirement", content_str, tr["id"], 0
        ))
    
    if requirements_batch:
        con.executemany("""
            INSERT OR REPLACE INTO requirements 
            (id, req_id, section_id, text, type, confidence, citation_snippet, 
             is_table_row, is_conditional, condition_text, sort_order, page, y0, metadata_json, run_id) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, requirements_batch)
        con.executemany("""
            INSERT OR REPLACE INTO merged_content 
            (id, section_id, page, type, content, asset_id, sort_order) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, merged_content_batch)
    
    final_count = con.sql("SELECT count(*) FROM requirements").fetchone()[0]
    cond_count = con.sql("SELECT count(*) FROM requirements WHERE is_conditional = true").fetchone()[0]
    
    elapsed = int(time.monotonic() - t0)
    logger.info(f"Stage 08 Complete. Extracted {len(requirements_batch)} requirements in {elapsed}s.")
    logger.info(f"Total Requirements: {final_count} ({cond_count} conditional)")
    
    deduplicate_source_text(con)
    
    return len(requirements_batch)


def deduplicate_source_text(con: duckdb.DuckDBPyConnection):
    """
    Mark original text blocks as 'consumed_text' if they are covered by extracted requirements.
    This prevents duplication in the final export.
    """
    logger.info("Deduplicating source text based on citations...")
    
    # Fetch requirements with citations
    reqs = con.execute("SELECT section_id, citation_snippet FROM requirements WHERE citation_snippet IS NOT NULL AND length(citation_snippet) > 10").fetchall()
    
    updates = 0
    for s_id, citation in reqs:
        citation_clean = citation.strip()
        if not citation_clean: 
            continue
            
        # Mark text blocks containing the citation as consumed
        # Using ILIKE for case-insensitive matching
        con.execute("""
            UPDATE merged_content 
            SET type = 'consumed_text' 
            WHERE section_id = ? 
              AND type = 'text' 
              AND content ILIKE ?
        """, [s_id, f"%{citation_clean}%"])
        
    logger.info("Source text deduplication complete.")


def sanity() -> int:
    """Run sanity check for this step."""
    return run_step_sanity(STEP_NAME)


# Standard entry point alias for consistency across pipeline steps
run = run_extract_requirements


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-dir", type=str, required=True)
    args = parser.parse_args()
    
    p_dir = Path(args.pipeline_dir)
    db_path = p_dir / "pipeline.duckdb"
    
    run_extract_requirements(p_dir, db_path)
