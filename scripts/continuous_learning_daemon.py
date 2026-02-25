#!/usr/bin/env python3
"""
Continuous Learning Daemon for PDF Extraction

Monitors the corpus directory for new PDFs and automatically:
1. Runs debug-table tuning to learn optimal extraction parameters
2. Generates fixture patterns for failures (ITAR-safe)
3. Logs indecipherable tables for analysis
4. Updates the knowledge base with learned patterns

This should run continuously "as long as PDFs plague humanity".

Usage:
    python continuous_learning_daemon.py start
    python continuous_learning_daemon.py status
    python continuous_learning_daemon.py stop
"""
import os
import sys
import json
import time
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Set, Dict, Any, Optional
import signal

from loguru import logger

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

def _resolve_learn_timeout_skill() -> Optional[Path]:
    """Find the learn-timeout skill directory."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "pi-mono" / ".pi" / "skills" / "learn-timeout",
        Path.home() / ".pi" / "skills" / "learn-timeout",
        Path.home() / ".claude" / "skills" / "learn-timeout",
    ]
    for p in candidates:
        if (p / "run.sh").exists():
            return p
    return None


_LEARN_TIMEOUT_SKILL = _resolve_learn_timeout_skill()
if _LEARN_TIMEOUT_SKILL:
    logger.info(f"learn-timeout skill found at {_LEARN_TIMEOUT_SKILL}")
else:
    logger.info("learn-timeout skill not found, using heuristic timeout estimation")


def _estimate_timeout(pdf_path: Path, page_count: int = 10, has_tables: bool = True, source: str = "unknown") -> int:
    """Estimate timeout using learn-timeout skill (GradientBoosting) or heuristic fallback.

    Priority:
    1. learn-timeout skill (uncapped GradientBoosting model)
    2. Heuristic fallback with source-specific multipliers
    """
    # --- Try learn-timeout skill first ---
    if _LEARN_TIMEOUT_SKILL is not None:
        try:
            file_size_mb = pdf_path.stat().st_size / (1024 * 1024) if pdf_path.exists() else 1.0
            domain = "scientific" if source in ("arxiv", "nasa", "nist") else "general"
            features = {
                "task_type": "pdf_extraction",
                "page_count": page_count,
                "file_size_mb": round(file_size_mb, 2),
                "has_tables": has_tables,
                "table_pages": max(1, page_count // 5) if has_tables else 0,
                "domain": domain,
                "source": source,
            }
            result = subprocess.run(
                [str(_LEARN_TIMEOUT_SKILL / "run.sh"), "predict", json.dumps(features)],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                prediction = json.loads(result.stdout.strip())
                recommended = prediction.get("recommended_timeout_seconds")
                if recommended and recommended > 0:
                    timeout = max(120, int(recommended))
                    logger.debug(
                        f"learn-timeout for {pdf_path.name}: {timeout}s "
                        f"(estimated={prediction.get('estimated_seconds')}s, "
                        f"risk={prediction.get('risk_label', 'unknown')}, source={source})"
                    )
                    return timeout
        except Exception as e:
            logger.debug(f"learn-timeout failed, falling back to heuristic: {e}")

    # --- Heuristic fallback ---
    SOURCE_MULTIPLIERS = {
        "arxiv": 2.5,
        "archive_org": 2.0,
        "ietf": 1.5,
        "defense": 1.3,
        "nasa": 1.3,
        "nist": 1.2,
    }
    source_multiplier = SOURCE_MULTIPLIERS.get(source, 1.0)
    size_mb = pdf_path.stat().st_size / (1024 * 1024) if pdf_path.exists() else 1.0

    # Base: 120s + 2s/page + 30s per estimated table page
    table_pages = max(1, page_count // 5) if has_tables else 0
    base = 120 + page_count * 2 + table_pages * 30
    timeout = int(base * 1.5 * source_multiplier)
    min_timeout = 300 if source in SOURCE_MULTIPLIERS else 180
    timeout = max(min_timeout, timeout)
    logger.debug(f"Heuristic timeout for {pdf_path.name}: {timeout}s (pages={page_count}, source={source}, mult={source_multiplier})")
    return timeout


# Configuration
CORPUS_ROOT = Path(os.getenv("CORPUS_ROOT", "/mnt/storage12tb/extractor_corpus"))
DEBUG_TABLE_SKILL = Path.home() / ".claude" / "skills" / "debug-table"
FIXTURE_TRICKY_SKILL = Path.home() / ".claude" / "skills" / "fixture-tricky"
FIXTURE_OUTPUT_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "generated"
STATE_FILE = Path.home() / ".pi" / "continuous-learning" / "state.json"
LOG_FILE = Path.home() / ".pi" / "continuous-learning" / "daemon.log"
MEMORY_API = "http://127.0.0.1:8601"

# Directories to monitor for new PDFs
# All directories with PDFs in corpus (discovered via `find` on 2026-02-07)
WATCH_DIRS = [
    "defense",
    "arxiv",
    "nasa",
    "ietf",
    "nist",
    "archive_org",
    "faa",
    "gpo",
    "incoming",
    # Additional directories discovered
    "inbox",           # 2157 PDFs - mixed sources
    "stress_test_pdfs", # 996 PDFs - stress test corpus
    "source",          # 13 PDFs - source documents
    "engineering",     # 10 PDFs - engineering specs
    "adversarial",     # 9 PDFs - adversarial test cases
    "edge_cases",      # 5 PDFs - edge case tests
    "dtic",            # DTIC defense technical info
    "government",      # Government documents
]

# How often to check for new PDFs (seconds)
POLL_INTERVAL = 60

# Batch size for processing
BATCH_SIZE = 50


class ContinuousLearningDaemon:
    """Daemon for continuous PDF learning."""

    def __init__(self):
        self.state_file = STATE_FILE
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.running = True
        self.processed_pdfs: Set[str] = set()
        self.generated_fixtures: Set[str] = set()  # Track generated fixture patterns to avoid duplicates
        self.stats = {
            "total_processed": 0,
            "total_failures": 0,
            "patterns_generated": 0,
            "indecipherable_tables": 0,
            "started_at": None,
            "last_activity": None,
        }
        self._load_state()

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info("Shutdown signal received, saving state...")
        self.running = False
        self._save_state()

    def _load_state(self):
        """Load persistent state from disk."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                self.processed_pdfs = set(data.get("processed_pdfs", []))
                self.generated_fixtures = set(data.get("generated_fixtures", []))
                self.stats = data.get("stats", self.stats)
                logger.info(f"Loaded state: {len(self.processed_pdfs)} PDFs already processed, {len(self.generated_fixtures)} fixtures generated")
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")

    def _save_state(self):
        """Save persistent state to disk."""
        try:
            data = {
                "processed_pdfs": list(self.processed_pdfs),
                "generated_fixtures": list(self.generated_fixtures),
                "stats": self.stats,
                "saved_at": datetime.utcnow().isoformat(),
            }
            self.state_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _get_pdf_hash(self, pdf_path: Path) -> str:
        """Get a hash of PDF path + mtime for change detection."""
        stat = pdf_path.stat()
        content = f"{pdf_path}:{stat.st_mtime}:{stat.st_size}"
        return hashlib.md5(content.encode()).hexdigest()

    def _find_new_pdfs(self) -> list[Path]:
        """Find PDFs that haven't been processed yet."""
        new_pdfs = []
        stale_hashes = []  # Track hashes that need removal (results missing)

        for watch_dir in WATCH_DIRS:
            dir_path = CORPUS_ROOT / watch_dir
            if not dir_path.exists():
                continue

            for pdf_path in dir_path.rglob("*.pdf"):
                # Skip output files - they're not source PDFs
                path_str = str(pdf_path)
                if "/results/" in path_str:
                    continue  # Skip anything in results directories
                if "_clean" in pdf_path.name:
                    continue  # Skip processed/cleaned PDFs
                if "/01_annotation_processor/" in path_str:
                    continue  # Skip stage output directories

                pdf_hash = self._get_pdf_hash(pdf_path)
                if pdf_hash not in self.processed_pdfs:
                    new_pdfs.append(pdf_path)
                else:
                    # Verify results actually exist - re-process if missing
                    result_dir = pdf_path.parent / "results" / pdf_path.stem
                    if not result_dir.exists():
                        logger.debug(f"Results missing for {pdf_path.name}, re-queuing")
                        stale_hashes.append(pdf_hash)
                        new_pdfs.append(pdf_path)

        # Remove stale hashes from processed set
        if stale_hashes:
            logger.info(f"Removing {len(stale_hashes)} stale hashes (results missing)")
            for h in stale_hashes:
                self.processed_pdfs.discard(h)

        return new_pdfs[:BATCH_SIZE]  # Limit batch size

    def _run_extractor(self, pdf_path: Path) -> Dict[str, Any]:
        """Run full extractor pipeline on a PDF."""
        result = {
            "pdf": str(pdf_path),
            "success": False,
            "sections": 0,
            "tables": 0,
            "figures": 0,
            "fragmentation": None,
            "pattern_generated": False,
            "error": None,
        }

        try:
            # Create output directory
            output_dir = pdf_path.parent / "results" / pdf_path.stem
            output_dir.mkdir(parents=True, exist_ok=True)

            # Run extractor CLI - fast batch mode for corpus processing
            # --fast-batch skips: summarizer, prover, table/fig descriptions
            cmd = [
                sys.executable, "-m", "extractor.pipeline.cli",
                str(pdf_path),
                "--out", str(output_dir),
                "--fast-batch",            # Skip heavy LLM stages (summarizer, descriptions)
                "--skip-llm03",            # Skip VLM verification (heuristic-only)
                "--continue-on-error",     # Don't stop on individual stage failures
            ]

            # Calculate dynamic timeout based on learned model + source multiplier
            source = pdf_path.parent.name
            dynamic_timeout = _estimate_timeout(pdf_path, page_count=10, has_tables=True, source=source)

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=dynamic_timeout,
                cwd=str(Path(__file__).parent.parent),
            )

            if proc.returncode == 0:
                result["success"] = True

                # Read metrics from output files (more reliable than parsing stdout)
                try:
                    # Count sections from S04 output (json_output/04_sections.json)
                    s04_sections = output_dir / "04_section_builder" / "json_output" / "04_sections.json"
                    if s04_sections.exists():
                        data = json.loads(s04_sections.read_text())
                        result["sections"] = data.get("section_count", 0) if isinstance(data, dict) else len(data)

                    # Count tables from S05 output (json_output/05_tables.json)
                    s05_tables = output_dir / "05_table_extractor" / "json_output" / "05_tables.json"
                    if s05_tables.exists():
                        try:
                            data = json.loads(s05_tables.read_text())
                            # Use table_count field if available, otherwise count tables array
                            if isinstance(data, dict) and "table_count" in data:
                                result["tables"] = data["table_count"]
                            else:
                                tables = data if isinstance(data, list) else data.get("tables", [])
                                result["tables"] = len(tables) if isinstance(tables, list) else 0
                            # Get params_used from quality_summary for /memory storage
                            if isinstance(data, dict) and "quality_summary" in data:
                                qs = data["quality_summary"]
                                result["params_used"] = qs.get("params_used", {})
                                result["param_source"] = qs.get("param_source")
                        except:
                            pass

                    # Count figures from S06 output
                    s06_dir = output_dir / "06_figure_extractor"
                    if s06_dir.exists():
                        fig_files = list(s06_dir.glob("*.json"))
                        for ff in fig_files:
                            try:
                                data = json.loads(ff.read_text())
                                figs = data if isinstance(data, list) else data.get("figures", [])
                                result["figures"] += len(figs) if isinstance(figs, list) else 0
                            except:
                                pass
                except Exception as e:
                    logger.debug(f"Error reading metrics from output: {e}")

                # Check for table fragmentation if tables found
                if result["tables"] > 0:
                    frag_result = self._check_table_fragmentation(output_dir)
                    result["fragmentation"] = frag_result

                # Store successful parameters in /memory for learning
                self._store_in_memory(result)
            else:
                result["error"] = proc.stderr[:500] if proc.stderr else "Unknown error"

        except subprocess.TimeoutExpired:
            result["error"] = f"Timeout after {dynamic_timeout} seconds (dynamic)"
        except Exception as e:
            result["error"] = str(e)

        return result

    def _check_table_fragmentation(self, output_dir: Path) -> Optional[int]:
        """Check table extraction quality from results."""
        try:
            # Look for table JSON files (correct path)
            s05_tables = output_dir / "05_table_extractor" / "json_output" / "05_tables.json"
            if not s05_tables.exists():
                return None

            # Use actual fragmentation_score from tables + count small tables as structural issues
            total_tables = 0
            total_frag_score = 0
            structural_fragments = 0  # Tables with <2 rows or cols
            data = json.loads(s05_tables.read_text())
            tables = data if isinstance(data, list) else data.get("tables", [])
            for t in tables:
                if not isinstance(t, dict):
                    continue
                total_tables += 1
                # Get actual OCR fragmentation score (count of fragmented cells)
                frag_score = t.get("fragmentation_score", 0)
                total_frag_score += frag_score

                # Get row/col count from pandas_metrics.shape or pandas_df length
                metrics = t.get("pandas_metrics", {})
                shape = metrics.get("shape", [0, 0])
                rows = shape[0] if len(shape) > 0 else len(t.get("pandas_df", []))
                cols = shape[1] if len(shape) > 1 else 0
                if rows < 2 or cols < 2:
                    structural_fragments += 1

            if total_tables > 0:
                # OCR frag: avg fragmented cells per table (0-100 scale)
                # Low fragmentation_score (0-5) is good, higher is bad
                avg_frag = total_frag_score / total_tables
                ocr_frag = min(100, int(avg_frag * 10))
                # Structural frag: % of tables that are small fragments
                struct_frag = int((structural_fragments / total_tables) * 100)
                # Return the worse of the two metrics
                return max(ocr_frag, struct_frag)
            return 0
        except Exception:
            return None

    def _store_in_memory(self, result: Dict[str, Any]) -> bool:
        """Store successful extraction parameters in /memory for learning.

        Only stores if:
        - Extraction was successful
        - Fragmentation is low (<10%)
        - We have valid params to store
        """
        if not HTTPX_AVAILABLE:
            return False

        if not result.get("success"):
            return False

        frag = result.get("fragmentation")
        if frag is None or frag > 10:
            return False

        params = result.get("params_used", {})
        if not params:
            return False

        source = result.get("source", "unknown")
        pdf_name = Path(result.get("pdf", "")).name

        # Build problem/solution for memory
        payload = {
            "problem": f"Optimal table extraction for {source} PDFs like {pdf_name}",
            "solution": (
                f"Use {params.get('flavor', 'lattice')} strategy with "
                f"line_scale={params.get('line_scale', 40)}, "
                f"edge_tol={params.get('edge_tol', 50)}. "
                f"Achieved {frag}% fragmentation."
            ),
            "tags": ["Precision", "table-extraction", f"source:{source}"],
        }

        try:
            resp = httpx.post(
                "http://127.0.0.1:8601/learn",
                json=payload,
                timeout=5.0,
            )
            if resp.status_code == 200:
                logger.debug(f"Stored extraction params in /memory for {source}")
                return True
        except Exception as e:
            logger.debug(f"Failed to store in /memory: {e}")

        return False

    def _run_debug_table(self, pdf_path: Path) -> Dict[str, Any]:
        """Run debug-table tuning on a PDF (for table-heavy docs)."""
        result = {
            "pdf": str(pdf_path),
            "success": False,
            "fragmentation": None,
            "pattern_generated": False,
            "error": None,
        }

        try:
            # Run debug-table tune
            cmd = [
                str(DEBUG_TABLE_SKILL / "run.sh"),
                "tune",
                str(pdf_path),
                "--max-iterations", "2",
            ]

            # Calculate dynamic timeout with source multiplier
            source = pdf_path.parent.name
            tune_timeout = _estimate_timeout(pdf_path, page_count=5, has_tables=True, source=source)

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=tune_timeout,
                cwd=str(DEBUG_TABLE_SKILL),
            )

            if proc.returncode == 0:
                result["success"] = True
                # Parse output for fragmentation
                for line in proc.stdout.split("\n"):
                    if "fragmentation" in line.lower():
                        try:
                            import re
                            match = re.search(r"fragmentation[:\s]+(\d+)", line.lower())
                            if match:
                                result["fragmentation"] = int(match.group(1))
                        except:
                            pass
            else:
                result["error"] = proc.stderr[:500] if proc.stderr else "Unknown error"

        except subprocess.TimeoutExpired:
            result["error"] = f"Timeout after {tune_timeout} seconds (dynamic)"
        except Exception as e:
            result["error"] = str(e)

        return result

    def _generate_failure_pattern(self, pdf_path: Path, failure_info: Dict) -> bool:
        """Learn from extraction failure - failures are instructive.

        THE FULL LEARNING LOOP:
        1. Run debug-table to understand the failure
        2. Store pattern in /memory for future reference
        3. Auto-invoke /fixture-tricky to generate a reproducer PDF
        4. Register fixture as regression test
        """
        try:
            error_msg = failure_info.get("error", "unknown")
            logger.info(f"Learning from failure: {pdf_path.name} - {error_msg[:100]}")

            # Run debug-table to understand WHY it failed
            tune_result = self._run_debug_table(pdf_path)

            # Store failure pattern in /memory with Fragility/Corruption tags
            self._store_failure_in_memory(pdf_path, failure_info, tune_result)

            # Determine pattern type from error message
            pattern_type = "unknown"
            if "timeout" in error_msg.lower():
                pattern_type = "timeout"
            elif "encoding" in error_msg.lower() or "decode" in error_msg.lower():
                pattern_type = "encoding"
            elif "camelot" in error_msg.lower() or "table" in error_msg.lower():
                pattern_type = "table-detection"
            elif "section" in error_msg.lower() or "header" in error_msg.lower():
                pattern_type = "layout"

            # Auto-invoke /fixture-tricky to generate reproducer
            if self._should_generate_fixture(pattern_type, error_msg):
                pattern_name = f"{pdf_path.parent.name}_{pattern_type}"
                description = f"Auto-generated from failure in {pdf_path.name}: {error_msg[:100]}"
                fixture_path = self._invoke_fixture_tricky(pattern_type, pattern_name, description)

                if fixture_path:
                    # Store fixture generation in /memory for tracking
                    self._store_fixture_in_memory(fixture_path, pattern_type, pdf_path)
                    return True

            return True

        except Exception as e:
            logger.error(f"Failed to learn from failure: {e}")
            return False

    def _store_fixture_in_memory(self, fixture_path: Path, pattern_type: str, source_pdf: Path):
        """Record that a fixture was generated for this pattern."""
        try:
            payload = json.dumps({
                "problem": f"Fixture generated for {pattern_type} pattern from {source_pdf.parent.name}",
                "solution": f"Created {fixture_path.name} as reproducer. This is a regression test for {pattern_type} failures.",
                "tags": ["Precision", "fixture-generated", pattern_type, f"source:{source_pdf.parent.name}"],
            })

            cmd = [
                "curl", "-s", "-X", "POST", f"{MEMORY_API}/learn",
                "-H", "Content-Type: application/json",
                "-d", payload,
                "--max-time", "10",
            ]

            subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            logger.debug(f"Recorded fixture generation in /memory: {fixture_path.name}")

        except Exception as e:
            logger.debug(f"Could not store fixture in memory: {e}")

    def _store_failure_in_memory(self, pdf_path: Path, failure_info: Dict, tune_result: Dict) -> bool:
        """Store failure pattern in /memory for future learning."""
        try:
            error_msg = failure_info.get("error", "unknown")

            # Determine bridge tags based on failure type
            bridge_tags = ["Fragility"]  # All failures indicate fragility
            if "timeout" in error_msg.lower():
                bridge_tags.append("Corruption")  # Timeouts often mean corrupted/complex PDFs
            if "encoding" in error_msg.lower() or "decode" in error_msg.lower():
                bridge_tags.append("Corruption")

            # Build problem/solution for /memory
            problem = f"PDF extraction failed for {pdf_path.name}: {error_msg[:200]}"
            solution_parts = [
                f"Extraction failed with error: {error_msg[:100]}.",
                "This PDF exhibits fragility patterns.",
            ]
            if tune_result.get("success"):
                solution_parts.append(f"Debug-table found: {tune_result.get('fragmentation', 'unknown')} fragmentation.")
            solution = " ".join(solution_parts)

            # Store via curl to /memory
            payload = json.dumps({
                "problem": problem,
                "solution": solution,
                "tags": bridge_tags + ["extraction-failure", f"source:{pdf_path.parent.name}"],
            })

            cmd = [
                "curl", "-s", "-X", "POST", f"{MEMORY_API}/learn",
                "-H", "Content-Type: application/json",
                "-d", payload,
                "--max-time", "10",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                logger.debug(f"Stored failure pattern in /memory: {pdf_path.name}")
                return True
            return False

        except Exception as e:
            logger.debug(f"Could not store failure in memory: {e}")
            return False

    def _invoke_fixture_tricky(self, pattern_type: str, pattern_name: str, description: str) -> Optional[Path]:
        """Auto-invoke fixture-tricky to generate reproducer for learned pattern.

        This is THE CORE LEARNING LOOP:
        1. PDF fails or shows fragility → _generate_failure_pattern()
        2. Store in /memory → _store_failure_in_memory()
        3. Generate fixture → _invoke_fixture_tricky() [THIS METHOD]
        4. Register fixture → manifest.yaml
        5. Fixture becomes regression test
        """
        try:
            # Map pattern types to fixture-tricky commands
            category_map = {
                "timeout": "cursed-text",
                "encoding": "cursed-text",
                "fragmentation": "malformed-tables",
                "table-detection": "false-tables",
                "borderless": "malformed-tables",
                "single-column": "false-tables",
                "layout": "layout-traps",
                "section": "layout-traps",
            }

            category = category_map.get(pattern_type, "gauntlet")

            # Generate unique filename from pattern
            safe_name = pattern_name.replace(" ", "_").replace("/", "_")[:50]
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_name = f"learned_{safe_name}_{timestamp}.pdf"
            output_path = FIXTURE_OUTPUT_DIR / output_name

            FIXTURE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            # Invoke fixture-tricky
            cmd = [
                "uv", "run", "generate.py", category,
                "--output", str(output_path),
            ]

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(FIXTURE_TRICKY_SKILL),
            )

            if proc.returncode == 0 and output_path.exists():
                logger.info(f"Generated fixture via fixture-tricky: {output_name}")

                # Register in manifest
                self._register_fixture(output_path, pattern_name, pattern_type, description)

                self.stats["fixtures_generated"] = self.stats.get("fixtures_generated", 0) + 1
                return output_path
            else:
                logger.warning(f"fixture-tricky failed: {proc.stderr[:200]}")
                return None

        except Exception as e:
            logger.error(f"Failed to invoke fixture-tricky: {e}")
            return None

    def _register_fixture(self, fixture_path: Path, name: str, pattern_type: str, description: str):
        """Register generated fixture in manifest.yaml for regression testing."""
        try:
            import yaml

            manifest_path = FIXTURE_OUTPUT_DIR / "manifest.yaml"

            # Load existing manifest or create new
            if manifest_path.exists():
                manifest = yaml.safe_load(manifest_path.read_text()) or {"fixtures": []}
            else:
                manifest = {"fixtures": []}

            # Add new fixture entry
            fixture_entry = {
                "name": name.replace(" ", "-").lower()[:50],
                "filename": fixture_path.name,
                "source_skill": "continuous-learning-daemon",
                "registered_at": datetime.utcnow().isoformat(),
                "tags": ["auto-generated", "learned-from-corpus", pattern_type],
                "description": description[:200],
            }

            # Check if already registered
            existing = [f for f in manifest["fixtures"] if f.get("filename") == fixture_path.name]
            if not existing:
                manifest["fixtures"].append(fixture_entry)
                manifest_path.write_text(yaml.dump(manifest, default_flow_style=False, sort_keys=False))
                logger.info(f"Registered fixture in manifest: {fixture_entry['name']}")

        except Exception as e:
            logger.warning(f"Failed to register fixture in manifest: {e}")

    def _should_generate_fixture(self, pattern_type: str, error_msg: str) -> bool:
        """Determine if this failure pattern warrants a new fixture.

        Uses in-memory tracking to prevent duplicate generation.
        Only generates ONE fixture per pattern_type per session.
        """
        # Create a key for this pattern type (not per-PDF, per-TYPE)
        pattern_key = f"{pattern_type}"

        # Already generated this pattern type? Skip.
        if pattern_key in self.generated_fixtures:
            logger.debug(f"Already generated fixture for {pattern_type} this session, skipping")
            return False

        # Limit total fixtures per session to prevent bloat
        # Set to 0 to disable auto-generation until learning loop is stable
        MAX_FIXTURES_PER_SESSION = 0
        if len(self.generated_fixtures) >= MAX_FIXTURES_PER_SESSION:
            logger.debug(f"Max fixtures per session ({MAX_FIXTURES_PER_SESSION}) reached, skipping")
            return False

        # Mark as will-generate
        self.generated_fixtures.add(pattern_key)
        return True

    def _store_extraction_in_memory(self, pdf_path: Path, result: Dict, tune_result: Dict, bridge_tags: list) -> bool:
        """Store successful extraction pattern in /memory for learning.

        When extraction succeeds with low fragmentation, stores the actual
        Camelot parameters (line_scale, edge_tol, flavor) so they can be
        recalled for similar PDFs via dynamic /memory queries.
        """
        try:
            frag = result.get("fragmentation", 0)
            table_count = result.get("tables", 0)
            source = pdf_path.parent.name

            # Get params from quality_summary if available
            params_used = result.get("params_used", {})
            param_str = ""
            if params_used:
                parts = []
                if params_used.get("flavor"):
                    parts.append(f"flavor={params_used['flavor']}")
                if params_used.get("line_scale"):
                    parts.append(f"line_scale={params_used['line_scale']}")
                if params_used.get("edge_tol"):
                    parts.append(f"edge_tol={params_used['edge_tol']}")
                if parts:
                    param_str = " Parameters: " + ", ".join(parts) + "."

            # Build problem/solution with actual params
            if "Precision" in bridge_tags:
                problem = f"Optimal table extraction for {source} PDFs with {table_count} tables."
                solution = f"Use {params_used.get('flavor', 'lattice')} with line_scale={params_used.get('line_scale', 40)} edge_tol={params_used.get('edge_tol', 500)} for clean extraction (fragmentation=0).{param_str}"
            else:
                problem = f"Table extraction for {source} PDFs with {table_count} tables, fragmentation={frag}%."
                solution = f"Extraction produced {frag}% fragmentation with {table_count} tables.{param_str} Consider different extraction parameters."

            if tune_result.get("success"):
                solution += f" Debug-table tuning completed."

            # Store via curl to /memory
            payload = json.dumps({
                "problem": problem,
                "solution": solution,
                "tags": bridge_tags + ["table-extraction", f"source:{source}", f"tables:{table_count}"],
            })

            cmd = [
                "curl", "-s", "-X", "POST", "http://127.0.0.1:8601/learn",
                "-H", "Content-Type: application/json",
                "-d", payload,
                "--max-time", "10",
            ]

            subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            logger.debug(f"Stored extraction pattern in /memory: {pdf_path.name} [{', '.join(bridge_tags)}]")
            return True

        except Exception as e:
            logger.debug(f"Could not store extraction in memory: {e}")
            return False

    def _process_pdf(self, pdf_path: Path) -> bool:
        """Process a single PDF through the extraction + learning pipeline."""
        pdf_hash = self._get_pdf_hash(pdf_path)
        logger.info(f"Extracting: {pdf_path.name}")

        # Run full extractor pipeline
        result = self._run_extractor(pdf_path)

        # Update stats
        self.stats["total_processed"] += 1
        self.stats["last_activity"] = datetime.utcnow().isoformat()

        if result["success"]:
            # Track extraction metrics
            self.stats["total_sections"] = self.stats.get("total_sections", 0) + result.get("sections", 0)
            self.stats["total_tables"] = self.stats.get("total_tables", 0) + result.get("tables", 0)
            self.stats["total_figures"] = self.stats.get("total_figures", 0) + result.get("figures", 0)

            # Run debug-table tuning for PDFs with tables to learn optimal params
            frag = result.get("fragmentation") or 0
            table_count = result.get("tables", 0)
            if table_count > 0:
                # Has tables - run debug-table to learn optimal params
                logger.info(f"PDF has {table_count} tables (frag={frag}%), running debug-table tuning...")
                tune_result = self._run_debug_table(pdf_path)
                if tune_result.get("success"):
                    result["pattern_generated"] = True
                    self.stats["patterns_generated"] += 1

                # Store in /memory - high fragmentation = Fragility, clean = Precision
                bridge_tags = []
                if frag == 0 and table_count >= 3:
                    bridge_tags = ["Precision", "Resilience"]
                elif frag > 50:
                    bridge_tags = ["Fragility"]
                    # High fragmentation warrants a fixture for regression testing
                    if self._should_generate_fixture("fragmentation", f"frag={frag}%"):
                        pattern_name = f"{pdf_path.parent.name}_high_fragmentation"
                        description = f"High fragmentation ({frag}%) in {pdf_path.name} with {table_count} tables"
                        self._invoke_fixture_tricky("fragmentation", pattern_name, description)
                elif frag > 0:
                    bridge_tags = ["Fragility"]  # Any fragmentation indicates issues

                if bridge_tags:
                    self._store_extraction_in_memory(pdf_path, result, tune_result, bridge_tags)
        else:
            self.stats["total_failures"] += 1
            # Generate pattern for failures
            self._generate_failure_pattern(pdf_path, result)

        # Mark as processed
        self.processed_pdfs.add(pdf_hash)

        # Log result
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "pdf": pdf_path.name,
            "source": pdf_path.parent.name,
            "sections": result.get("sections", 0),
            "tables": result.get("tables", 0),
            "figures": result.get("figures", 0),
            **{k: v for k, v in result.items() if k not in ["sections", "tables", "figures"]},
        }
        logger.info(f"Result: {json.dumps(log_entry)}")

        return result["success"]

    def run(self):
        """Main daemon loop."""
        logger.info("=" * 60)
        logger.info("Continuous Learning Daemon Starting")
        logger.info(f"Watching: {CORPUS_ROOT}")
        logger.info(f"Directories: {WATCH_DIRS}")
        logger.info("=" * 60)

        self.stats["started_at"] = datetime.utcnow().isoformat()

        from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

        # Parallel processing - 8 workers (ThreadPool works for subprocess calls)
        MAX_WORKERS = 8
        # Maximum time to wait for a single PDF (safety net above subprocess timeout)
        FUTURE_TIMEOUT = 300  # 5 minutes per PDF max
        # Batch timeout - if entire batch takes too long, something is stuck
        BATCH_TIMEOUT = 1800  # 30 minutes for entire batch

        # Heartbeat tracking
        last_heartbeat = time.time()
        HEARTBEAT_INTERVAL = 60  # Log heartbeat every 60s

        while self.running:
            try:
                # Log heartbeat to detect stalls
                if time.time() - last_heartbeat > HEARTBEAT_INTERVAL:
                    logger.info(f"[HEARTBEAT] Daemon alive, processed={self.stats['total_processed']}")
                    last_heartbeat = time.time()

                # Find new PDFs
                new_pdfs = self._find_new_pdfs()

                if new_pdfs:
                    logger.info(f"Found {len(new_pdfs)} new PDFs to process (parallel: {MAX_WORKERS} workers)")
                    batch_start = time.time()

                    # Process PDFs in parallel with timeout safety
                    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="extractor") as executor:
                        futures = {executor.submit(self._process_pdf, pdf): pdf for pdf in new_pdfs}
                        completed = 0

                        try:
                            # Use timeout on as_completed to detect stalls
                            for future in as_completed(futures, timeout=BATCH_TIMEOUT):
                                if not self.running:
                                    break
                                pdf = futures[future]
                                try:
                                    future.result(timeout=FUTURE_TIMEOUT)
                                    completed += 1
                                    # Update heartbeat on each completion
                                    last_heartbeat = time.time()
                                except FuturesTimeoutError:
                                    logger.error(f"TIMEOUT: {pdf.name} exceeded {FUTURE_TIMEOUT}s - marking as failed")
                                    self.processed_pdfs.add(self._get_pdf_hash(pdf))
                                    self.stats["total_failures"] += 1
                                except Exception as e:
                                    logger.error(f"Failed to process {pdf.name}: {e}")
                        except FuturesTimeoutError:
                            # Batch timeout - cancel remaining futures
                            logger.error(f"BATCH TIMEOUT: {len(futures) - completed} PDFs still pending after {BATCH_TIMEOUT}s")
                            for future in futures:
                                if not future.done():
                                    future.cancel()
                                    pdf = futures[future]
                                    self.processed_pdfs.add(self._get_pdf_hash(pdf))
                                    self.stats["total_failures"] += 1
                                    logger.warning(f"Cancelled stalled extraction: {pdf.name}")

                    elapsed = time.time() - batch_start
                    logger.info(f"Batch complete: {completed}/{len(new_pdfs)} in {elapsed:.1f}s")

                    # Save state after each batch
                    self._save_state()

                    # Log stats with extraction metrics
                    logger.info(
                        f"Stats: processed={self.stats['total_processed']}, "
                        f"failures={self.stats['total_failures']}, "
                        f"patterns={self.stats['patterns_generated']}, "
                        f"sections={self.stats.get('total_sections', 0)}, "
                        f"tables={self.stats.get('total_tables', 0)}, "
                        f"figures={self.stats.get('total_figures', 0)}"
                    )
                else:
                    logger.debug(f"No new PDFs, sleeping {POLL_INTERVAL}s")

                # Wait before next poll
                time.sleep(POLL_INTERVAL)

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(10)  # Brief pause on error

        logger.info("Daemon shutting down")
        self._save_state()

    def status(self) -> Dict[str, Any]:
        """Get current daemon status."""
        return {
            "processed_count": len(self.processed_pdfs),
            "stats": self.stats,
            "state_file": str(self.state_file),
        }


def main():
    import typer

    app = typer.Typer(help="Continuous Learning Daemon for PDF Extraction")

    @app.command()
    def start():
        """Start the continuous learning daemon."""
        # Configure logging
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        logger.add(LOG_FILE, rotation="10 MB", retention="7 days")

        daemon = ContinuousLearningDaemon()
        daemon.run()

    @app.command()
    def status():
        """Show daemon status."""
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text())
            print(json.dumps(data, indent=2))
        else:
            print("No state file found - daemon may not have run yet")

    @app.command()
    def stop():
        """Stop the daemon (send SIGTERM to running process)."""
        import subprocess
        result = subprocess.run(
            ["pkill", "-f", "continuous_learning_daemon"],
            capture_output=True,
        )
        if result.returncode == 0:
            print("Daemon stopped")
        else:
            print("No daemon process found")

    app()


if __name__ == "__main__":
    main()
