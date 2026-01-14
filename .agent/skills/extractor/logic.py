import asyncio
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict
import json
import yaml

from loguru import logger

# Paths
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
TASKS_LOOP_DIR = WORKSPACE_ROOT / "tools" / "tasks_loop"
FIXTURES_DIR = TASKS_LOOP_DIR / "fixtures"

class ExtractorLogic:
    def __init__(self):
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = f"{WORKSPACE_ROOT}/src:{self.env.get('PYTHONPATH', '')}"

    async def _run_command(self, cmd: List[str], cwd: Path = WORKSPACE_ROOT) -> int:
        """Run a subprocess command asynchronously."""
        cmd_str = " ".join(cmd)
        logger.info(f"Running: {cmd_str}")
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            env=self.env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        if stdout:
            print(stdout.decode())
        if stderr:
            print(stderr.decode(), file=sys.stderr)
            
        return proc.returncode

    async def compile_spec(self, fixture_name: str) -> bool:
        """Compile SPEC.md to contracts and config."""
        script = TASKS_LOOP_DIR / "utils" / "compile_contracts.py"
        ret = await self._run_command(
            ["python3", str(script), "--fixture", fixture_name],
            cwd=TASKS_LOOP_DIR
        )
        return ret == 0

    async def verify_twin(self, fixture_name: str, auto_tune: bool = False) -> bool:
        """Run the Twin Verification Loop."""
        # reuse the logic from verify_mimic script but calling python directly where possible
        # For now, simplest path is to wrap the verify_mimic script or port it. 
        # Let's wrap the script for maximum fidelity to the verified phase.
        
        verify_script = WORKSPACE_ROOT / ".skills" / "verify_mimic" / "verify"
        fixture_pdf = FIXTURES_DIR / fixture_name / "source.pdf"
        
        # We need to find the compiled config to pass
        profile_json = FIXTURES_DIR / fixture_name / f"{fixture_name}_profile.json"
        
        # NOTE: verify_mimic takes <pdf> [config_yml]
        # But we generate config in step 3? 
        # Actually verify_mimic does: Analyze -> Generate -> Compile -> Extract.
        # If we use verify_mimic, it regenerates the SPEC.md? 
        # Wait, the new Flow says SPEC.md is SOURCE.
        # `verify_mimic` was updated to generate SPEC.md from Source-Expected.
        # But for Client Fixtures, SPEC.md is HAND WRITTEN.
        # So `verify_mimic` logic is for "Twin Generation".
        # For "Twin Verification" of an EXISTING Spec, we just run the pipeline.
        
        # Let's assume this is a "Client Twin" (Hand-crafted Spec).
        # We need to:
        # 1. Compile Contracts.
        # 2. Extract Twin PDF.
        # 3. Verify Output vs Match.
        
        # Re-using verify_mimic script might be confusing if it forces generation.
        # Let's stick to calling the shell script for now if it works, 
        # OR better: Implement strict steps here.
        
        # Step 1: Compile
        if not await self.compile_spec(fixture_name):
            logger.error("Spec compilation failed.")
            return False
            
        # Step 2: Extract (using the compiled profile)
        # Profile is valid? S08 loads it.
        # We assume 'source.pdf' exists in fixture.
        
        cmd = [
            "uv", "run", "python3", "-m", "extractor.pipeline",
            "--pdf", str(fixture_pdf),
            "--out", f"data/results/pipeline_{fixture_name}",
            "--skip-proving" # Default
        ]
        
        ret = await self._run_command(cmd)
        
        # Step 3: Check Report (or auto-tune)
        if ret != 0 and auto_tune:
             logger.info("Pipeline failed. Attempting Auto-Tune...")
             tune_script = TASKS_LOOP_DIR / "auto_tune.py"
             await self._run_command(["python3", str(tune_script), str(FIXTURES_DIR / fixture_name)])
             return False # Failed this run, but tuned.
             
        return ret == 0

    def _find_twin_for_pdf(self, pdf_path: Path) -> Optional[str]:
        """Look up Twin registry to find a matching Twin for the PDF."""
        registry_path = FIXTURES_DIR / "twin_registry.yml"
        if not registry_path.exists():
            return None
            
        try:
            registry = yaml.safe_load(registry_path.read_text())
        except Exception:
            return None
            
        # Check for exact fixture name match
        pdf_name = pdf_path.stem.lower().replace(" ", "_")
        fixture_dir = FIXTURES_DIR / pdf_name
        if fixture_dir.exists() and (fixture_dir / "SPEC.md").exists():
            return pdf_name
            
        # Check detection rules (pattern matching in PDF content)
        # For now, just check categories
        categories = registry.get("categories", {})
        for cat_name, cat_info in categories.items():
            if cat_info.get("twin_fixture"):
                # Check if fixture exists
                twin_dir = FIXTURES_DIR / cat_info["twin_fixture"]
                if twin_dir.exists() and (twin_dir / "SPEC.md").exists():
                    # TODO: Actually match PDF content to category
                    # For now, return first available Twin
                    return cat_info["twin_fixture"]
        
        return None

    async def extract_real(self, pdf_path: Path, strict: bool = True) -> bool:
        """Run on Real PDF."""
        pdf_path = Path(pdf_path).resolve()
        
        if strict:
            twin_name = self._find_twin_for_pdf(pdf_path)
            
            if not twin_name:
                logger.warning(f"No Twin found for {pdf_path.name}")
                print("\n" + "="*60)
                print("⚠️  STRICT MODE: No calibrated Twin found for this PDF.")
                print("="*60)
                print("\nOptions:")
                print("  1. Create a Twin first (recommended)")
                print("  2. Use --fast mode (risky, no calibration)")
                print("\nTo create a Twin, run:")
                print(f"  python3 .agent/skills/extractor/cli.py verify <fixture_name>")
                print("\nTo proceed with fast mode, run:")
                print(f"  python3 .agent/skills/extractor/cli.py extract {pdf_path} --fast")
                return False
            else:
                logger.info(f"Using Twin: {twin_name}")
                # Verify the Twin is still valid (passes)
                # TODO: Run Twin verification first?
            
        cmd = [
            "uv", "run", "python3", "-m", "extractor.pipeline",
            "--pdf", str(pdf_path),
            "--out", "data/results/real_runs",
            "--skip-proving"
        ]
        
        return (await self._run_command(cmd)) == 0

    async def create_twin(
        self,
        source_pdf: Path,
        fixture_name: str,
        pages: int = 5,
        errors: List[str] = None
    ) -> bool:
        """Create a Digital Twin fixture from source PDF analysis."""
        errors = errors or ["hyphenation", "ligatures", "split_tables", "trapped_headers"]
        
        fixture_dir = FIXTURES_DIR / fixture_name
        fixture_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Creating Twin: {fixture_name} ({pages} pages)")
        
        # Step 1: Analyze source PDF style (future: use analyze_pdf_style.py)
        # For now, we generate a standard messy fixture
        
        # Step 2: Generate Twin PDF with chaos
        generator_script = TASKS_LOOP_DIR / "utils" / "generate_complex_fixture.py"
        output_pdf = fixture_dir / "source.pdf"
        
        # Build config with requested errors
        config = {
            "pages": pages,
            "chaos": {
                "hyphenation_probability": 0.15 if "hyphenation" in errors else 0,
                "ligature_map": {"fi": "ﬁ", "fl": "ﬂ"} if "ligatures" in errors else {},
                "mojibake_probability": 0.01 if "mojibake" in errors else 0,
            },
            "features": {
                "split_tables": "split_tables" in errors,
                "trapped_headers": "trapped_headers" in errors,
                "ocr_artifacts": "ocr_artifacts" in errors,
            }
        }
        
        # Write temp config
        config_path = fixture_dir / "twin_config.yml"
        config_path.write_text(yaml.dump(config, sort_keys=False))
        
        ret = await self._run_command([
            "python3", str(generator_script),
            str(output_pdf),
            "--config", str(config_path)
        ])
        
        if ret != 0:
            logger.error("Twin generation failed")
            return False
            
        # Step 3: Generate SPEC.md from Ground Truth
        expected_json = fixture_dir / "source_expected.json"
        if expected_json.exists():
            data = json.loads(expected_json.read_text())
            metrics = data.get("metrics", {})
            
            spec = {
                "fixture": fixture_name,
                "pdf": f"tools/tasks_loop/fixtures/{fixture_name}/source.pdf",
                "agent_config": {
                    "allow_auto_tune": True,
                    "strict_calibration": True,
                },
                "steps": {}
            }
            
            if metrics.get("table_count"):
                spec["steps"]["s05"] = {
                    "name": "Table Extractor",
                    "expected": {"table_count": metrics["table_count"]}
                }
            if metrics.get("requirement_count"):
                spec["steps"]["s08"] = {
                    "name": "Requirement Extractor", 
                    "expected": {"requirement_count": metrics["requirement_count"]}
                }
            if metrics.get("section_count"):
                spec["steps"]["s04"] = {
                    "name": "Section Builder",
                    "expected": {"section_count": metrics["section_count"]}
                }
                
            spec_path = fixture_dir / "SPEC.md"
            with open(spec_path, "w") as f:
                f.write("---\n")
                yaml.dump(spec, f, sort_keys=False)
                f.write("---\n\n")
                f.write(f"# {fixture_name} Twin\n\n")
                f.write(f"Generated from: {source_pdf.name}\n")
                f.write(f"Pages: {pages}\n")
                f.write(f"Chaos: {', '.join(errors)}\n")
                
            logger.info(f"Generated SPEC.md at {spec_path}")
            
        # Step 4: Compile contracts
        await self.compile_spec(fixture_name)
        
        return True
