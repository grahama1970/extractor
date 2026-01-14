#!/usr/bin/env python3
"""
Extractor CLI - Collaborative PDF Extraction

Every PDF needs a Digital Twin. Neither human nor agent alone can figure it out.
"""
import typer
import asyncio
from pathlib import Path
from typing import List, Optional

try:
    from .logic import ExtractorLogic, FIXTURES_DIR, WORKSPACE_ROOT
except ImportError:
    from logic import ExtractorLogic, FIXTURES_DIR, WORKSPACE_ROOT

from loguru import logger

app = typer.Typer(
    help="Extractor: Collaborative PDF Extraction via Digital Twins",
    no_args_is_help=True
)
logic = ExtractorLogic()

# Common PDF extraction errors
CHAOS_OPTIONS = [
    "hyphenation",    # Words split across lines
    "ligatures",      # fi → ﬁ
    "split_tables",   # Tables spanning pages
    "trapped_headers", # Data rows mimicking headers
    "mojibake",       # Encoding corruption
    "ocr_artifacts",  # Character confusion
]

@app.command()
def extract(
    pdf: Path = typer.Argument(..., help="Path to the PDF file"),
    strict: bool = typer.Option(True, help="Enforce Twin-First calibration"),
    fast: bool = typer.Option(False, "--fast", help="Skip calibration (quick PyMuPDF only)"),
):
    """
    Extract content from a PDF.
    
    By default, requires a calibrated Twin (--strict).
    Use --fast for quick extraction without calibration (risky).
    """
    pdf = Path(pdf).resolve()
    
    if not pdf.exists():
        typer.echo(f"❌ File not found: {pdf}")
        raise typer.Exit(code=1)
    
    if fast:
        typer.echo("\n⚡ FAST MODE: Skipping Twin calibration (risky)")
        typer.echo("Using PyMuPDF direct extraction...\n")
        strict = False
        
    async def _run():
        success = await logic.extract_real(pdf, strict=strict)
        if not success and strict:
            # Offer interactive options
            typer.echo("\n" + "="*60)
            typer.echo("📋 EXTRACTION OPTIONS")
            typer.echo("="*60)
            typer.echo("\n⚠️  PDF extraction is difficult without calibration.")
            typer.echo("   High accuracy requires human-agent collaboration.\n")
            typer.echo("  1. Create a NEW Twin (recommended for new PDF types)")
            typer.echo("  2. Use an EXISTING Twin (if you have one for this PDF type)")
            typer.echo("  3. Quick extract with PyMuPDF (fast but LOW accuracy)")
            typer.echo("")
            
            choice = typer.prompt("Choose [1/2/3]", default="1")
            
            if choice == "1":
                pages = typer.prompt("How many pages for the Twin?", default="5", type=int)
                fixture_name = pdf.stem.lower().replace(" ", "_") + "_twin"
                
                typer.echo(f"\n🔧 Creating {pages}-page Twin: {fixture_name}")
                typer.echo("Run this command to create the Twin:\n")
                typer.echo(f"  python3 .agent/skills/extractor/cli.py twin {pdf} --pages {pages} --name {fixture_name}")
                typer.echo("")
                return
            elif choice == "2":
                existing_fixture = typer.prompt("Enter existing Twin fixture name (or path)")
                typer.echo(f"\n🔗 Using existing Twin: {existing_fixture}")
                typer.echo("First, verify the Twin passes:\n")
                typer.echo(f"  python3 .agent/skills/extractor/cli.py verify {existing_fixture}")
                typer.echo("\nThen extract with:")
                typer.echo(f"  python3 .agent/skills/extractor/cli.py extract {pdf} --fast")
                return
            else:
                typer.echo("\n⚠️  WARNING: Quick extraction has LOW accuracy.")
                typer.echo("   Results may be incomplete or incorrect.\n")
                await logic.extract_real(pdf, strict=False)
                
    asyncio.run(_run())

@app.command()
def verify(
    fixture: str = typer.Argument(..., help="Name of the fixture to verify"),
    auto_tune: bool = typer.Option(False, "--auto-tune", help="Automatically tune config on failure"),
):
    """
    Run the Twin Verification Loop.
    
    Compiles SPEC.md, runs pipeline on Twin, compares to Ground Truth.
    """
    typer.echo(f"\n🔍 Verifying Twin: {fixture}")
    
    async def _run():
        success = await logic.verify_twin(fixture, auto_tune=auto_tune)
        if success:
            typer.echo("\n✅ Twin verification PASSED")
            typer.echo("You can now run extraction on real PDFs with confidence.")
        else:
            typer.echo("\n❌ Twin verification FAILED")
            if auto_tune:
                typer.echo("Auto-tune suggestions have been generated.")
            else:
                typer.echo("Run with --auto-tune to get fix suggestions.")
            raise typer.Exit(code=1)
    
    asyncio.run(_run())

@app.command()
def twin(
    source_pdf: Path = typer.Argument(..., help="PDF to analyze and mimic"),
    pages: int = typer.Option(5, "--pages", "-p", help="Number of pages to generate"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Fixture name (default: auto from PDF)"),
    errors: Optional[str] = typer.Option(
        "hyphenation,ligatures,split_tables,trapped_headers",
        "--errors", "-e",
        help=f"Chaos to inject (comma-separated): {', '.join(CHAOS_OPTIONS)}"
    ),
    show_expected: bool = typer.Option(True, "--show-expected/--no-show-expected", help="Show expected markdown"),
):
    """
    Create a Digital Twin fixture from a source PDF.
    
    Analyzes the PDF style and creates a synthetic version with known content.
    """
    source_pdf = Path(source_pdf).resolve()
    
    if not source_pdf.exists():
        typer.echo(f"❌ Source PDF not found: {source_pdf}")
        raise typer.Exit(code=1)
    
    fixture_name = name or (source_pdf.stem.lower().replace(" ", "_") + "_twin")
    fixture_dir = FIXTURES_DIR / fixture_name
    error_list = [e.strip() for e in errors.split(",") if e.strip()]
    
    typer.echo("\n" + "="*60)
    typer.echo("🎭 DIGITAL TWIN CREATION")
    typer.echo("="*60)
    typer.echo(f"\nSource PDF:  {source_pdf.name}")
    typer.echo(f"Twin Name:   {fixture_name}")
    typer.echo(f"Pages:       {pages}")
    typer.echo(f"Chaos:       {', '.join(error_list)}")
    typer.echo("")
    
    async def _run():
        success = await logic.create_twin(
            source_pdf=source_pdf,
            fixture_name=fixture_name,
            pages=pages,
            errors=error_list
        )
        
        if success:
            typer.echo(f"\n✅ Twin created: {fixture_dir}")
            
            # Show expected markdown if requested
            if show_expected:
                expected_md = fixture_dir / "source_expected.md"
                if expected_md.exists():
                    typer.echo("\n" + "="*60)
                    typer.echo("📄 EXPECTED MARKDOWN OUTPUT")
                    typer.echo("="*60 + "\n")
                    content = expected_md.read_text()
                    # Show first 2000 chars
                    if len(content) > 2000:
                        typer.echo(content[:2000])
                        typer.echo(f"\n... (truncated, see full file at {expected_md})")
                    else:
                        typer.echo(content)
                        
            typer.echo("\n📋 NEXT STEPS:")
            typer.echo(f"  1. Review the Twin: {fixture_dir}/source.pdf")
            typer.echo(f"  2. Edit SPEC.md if needed: {fixture_dir}/SPEC.md")
            typer.echo(f"  3. Verify: python3 .agent/skills/extractor/cli.py verify {fixture_name}")
        else:
            typer.echo("\n❌ Twin creation failed")
            raise typer.Exit(code=1)
            
    asyncio.run(_run())

if __name__ == "__main__":
    app()
