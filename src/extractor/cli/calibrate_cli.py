"""CLI wrappers for calibration modules.

Provides command-line interface for:
- Element detection
- Page sampling
- Verdict submission
- Session status
- Flight check (finish)

Usage:
    python -m extractor.cli.calibrate_cli detect doc.pdf --page 0
    python -m extractor.cli.calibrate_cli sample session_key --count 5
    python -m extractor.cli.calibrate_cli verdict session_key elem_001 correct
    python -m extractor.cli.calibrate_cli status session_key
    python -m extractor.cli.calibrate_cli finish session_key
"""

import json
import os
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="calibrate",
    help="Calibration CLI for human-agent collaborative preset tuning",
)


@app.command()
def detect(
    pdf_path: Path = typer.Argument(..., help="Path to PDF file"),
    page: Optional[int] = typer.Option(None, "--page", "-p", help="Page number (0-indexed)"),
    pages: Optional[str] = typer.Option(None, "--pages", help="Comma-separated page numbers"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON path"),
):
    """Detect elements on PDF page(s). Returns JSON with detected elements."""
    from extractor.pipeline.calibration import detect_elements

    # Parse page numbers
    if page is not None:
        page_numbers = [page]
    elif pages:
        page_numbers = [int(p.strip()) for p in pages.split(",")]
    else:
        page_numbers = None  # All pages

    # Detect elements
    elements_by_page = detect_elements(str(pdf_path), page_numbers=page_numbers)

    # Format output for element presentation
    result = {
        "pdf_path": str(pdf_path),
        "pages": {},
        "total_elements": 0,
    }

    # First pass: count total elements
    for page_num, elements in elements_by_page.items():
        result["total_elements"] += len(elements)

    # Second pass: build element data with all fields needed for presentation
    for page_num, elements in elements_by_page.items():
        result["pages"][page_num] = [
            {
                "element_idx": elem.element_idx,
                "element_type": elem.element_type,
                "bbox": [round(b, 1) for b in elem.bbox],
                "confidence": round(elem.confidence * 100, 1),  # As percentage
                "reasoning": elem.reasoning,
                "text_preview": elem.text[:100] if elem.text else None,
                "font_info": (
                    {
                        "name": elem.font_info.name if elem.font_info else None,
                        "size": round(elem.font_info.size, 1) if elem.font_info else None,
                        "is_bold": elem.font_info.is_bold if elem.font_info else None,
                        "is_italic": elem.font_info.is_italic if elem.font_info else None,
                        "color": elem.font_info.color if elem.font_info else None,
                    }
                    if elem.font_info
                    else None
                ),
                "metadata": elem.metadata if elem.metadata else None,
            }
            for elem in elements
        ]

    json_output = json.dumps(result, indent=2)

    if output:
        output.write_text(json_output)
        typer.echo(f"Saved to {output}")
    else:
        typer.echo(json_output)


@app.command()
def sample(
    session_id: str = typer.Argument(..., help="Session ID/key"),
    count: int = typer.Option(5, "--count", "-n", help="Number of pages to suggest"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON path"),
):
    """Suggest pages for review based on diversity sampling."""
    from extractor.pipeline.calibration import (
        CalibrationSchema,
        sample_pages,
        SamplerConfig,
    )

    schema = CalibrationSchema()
    session = schema.get_session(session_id)

    if not session:
        typer.echo(f"Error: Session '{session_id}' not found", err=True)
        raise typer.Exit(1)

    pdf_path = session["pdf_path"]

    config = SamplerConfig(
        diversity_weight=0.7,
        complexity_weight=0.3,
        max_pages=count,
    )

    suggested = sample_pages(pdf_path, config)

    result = {
        "session_id": session_id,
        "pdf_path": pdf_path,
        "suggested_pages": [s.page_number for s in suggested],
        "reasons": [s.reason for s in suggested],
    }

    json_output = json.dumps(result, indent=2)

    if output:
        output.write_text(json_output)
        typer.echo(f"Saved to {output}")
    else:
        typer.echo(json_output)


@app.command()
def verdict(
    session_id: str = typer.Argument(..., help="Session ID/key"),
    element_id: str = typer.Argument(..., help="Element ID"),
    verdict_value: str = typer.Argument(
        ..., help="Verdict: correct, wrong_type, not_element, split, flagged"
    ),
    note: Optional[str] = typer.Option(None, "--note", "-n", help="Additional note"),
    correct_type: Optional[str] = typer.Option(
        None, "--correct-type", "-t", help="Correct type (for wrong_type verdict)"
    ),
):
    """Submit a human verdict for an element."""
    from extractor.pipeline.calibration import (
        CalibrationSchema,
        FeedbackHandler,
        HumanVerdict,
    )

    schema = CalibrationSchema()
    handler = FeedbackHandler(schema)

    # Validate session
    session = schema.get_session(session_id)
    if not session:
        typer.echo(f"Error: Session '{session_id}' not found", err=True)
        raise typer.Exit(1)

    # Parse verdict
    verdict_map = {
        "correct": HumanVerdict.CORRECT,
        "wrong_type": HumanVerdict.WRONG_TYPE,
        "not_element": HumanVerdict.NOT_ELEMENT,
        "split": HumanVerdict.SPLIT,
        "flagged": HumanVerdict.FLAGGED,
    }

    if verdict_value.lower() not in verdict_map:
        typer.echo(f"Error: Invalid verdict '{verdict_value}'", err=True)
        typer.echo(f"Valid values: {', '.join(verdict_map.keys())}")
        raise typer.Exit(1)

    parsed_verdict = verdict_map[verdict_value.lower()]

    # Build correction if needed
    correction = None
    if parsed_verdict == HumanVerdict.WRONG_TYPE:
        if not correct_type:
            typer.echo("Error: --correct-type required for wrong_type verdict", err=True)
            raise typer.Exit(1)
        correction = {"correct_type": correct_type}

    # Record verdict
    handler.record_verdict(
        session_key=session_id,
        element_id=element_id,
        verdict=parsed_verdict,
        correction=correction,
        note=note,
    )

    typer.echo(json.dumps({"ok": True, "element_id": element_id, "verdict": verdict_value}))


@app.command()
def status(
    session_id: str = typer.Argument(..., help="Session ID/key"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON path"),
):
    """Get session status: accuracy, reviewed count, convergence."""
    from extractor.pipeline.calibration import CalibrationSchema, FeedbackHandler

    schema = CalibrationSchema()
    session = schema.get_session(session_id)

    if not session:
        typer.echo(f"Error: Session '{session_id}' not found", err=True)
        raise typer.Exit(1)

    handler = FeedbackHandler(schema)
    stats = handler.get_session_stats(session_id)

    # Check convergence
    converged = stats["accuracy"] >= 90.0 and stats["reviewed"] >= 20

    result = {
        "session_id": session_id,
        "pdf_path": session["pdf_path"],
        "preset_id": session.get("preset_id"),
        "status": session.get("status"),
        "reviewed": stats["reviewed"],
        "correct": stats["correct"],
        "accuracy": stats["accuracy"],
        "converged": converged,
        "current_round": stats["current_round"],
        "by_type": stats["by_type"],
        "last_page": stats["last_page"],
        "last_element_idx": stats["last_element_idx"],
    }

    json_output = json.dumps(result, indent=2)

    if output:
        output.write_text(json_output)
        typer.echo(f"Saved to {output}")
    else:
        typer.echo(json_output)


@app.command()
def finish(
    session_id: str = typer.Argument(..., help="Session ID/key"),
    force: bool = typer.Option(False, "--force", "-f", help="Force finish even if not converged"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output preset YAML path"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    skip_preview: bool = typer.Option(False, "--skip-preview", help="Skip extraction preview"),
    preview_pages: int = typer.Option(
        5, "--preview-pages", "-n", help="Number of pages to preview"
    ),
):
    """Finish calibration and run flight check.

    Shows extraction preview, then runs flight check validation,
    and generates preset YAML on pass.
    """
    from tools.tasks_loop.gates.gate_calibration import run_flight_check, format_flight_check
    from extractor.pipeline.calibration import (
        CalibrationSchema,
        generate_preset,
        format_preset_summary,
    )
    from extractor.pipeline.calibration.preview import (
        ExtractionPreview,
        format_preview_text,
        format_preview_json,
    )

    schema = CalibrationSchema()
    session = schema.get_session(session_id)

    if not session:
        typer.echo(f"Error: Session '{session_id}' not found", err=True)
        raise typer.Exit(1)

    pdf_path = session.get("pdf_path")

    # Step 1: Run extraction preview (unless skipped)
    preview_result = None
    if not skip_preview and pdf_path:
        if not json_output:
            typer.echo("=" * 60)
            typer.echo("STEP 1: Extraction Preview")
            typer.echo("=" * 60)
            typer.echo("")

        try:
            previewer = ExtractionPreview(schema)
            preview_result = previewer.preview_extraction(
                pdf_path=pdf_path,
                session_key=session_id,
                max_pages=preview_pages,
            )

            if not json_output:
                typer.echo(format_preview_text(preview_result))
                typer.echo("")
        except Exception as e:
            if not json_output:
                typer.echo(f"Warning: Could not generate preview: {e}", err=True)
                typer.echo("")

    # Step 2: Run flight check
    if not json_output:
        typer.echo("=" * 60)
        typer.echo("STEP 2: Flight Check Validation")
        typer.echo("=" * 60)
        typer.echo("")

    flight_result = run_flight_check(session_id)

    if json_output:
        result = {
            "session_id": session_id,
            "preview": format_preview_json(preview_result) if preview_result else None,
            "flight_check": {
                "passed": flight_result.passed or force,
                "checks": flight_result.checks,
                "missing": flight_result.missing,
            },
            "stats": flight_result.stats,
        }

        if flight_result.passed or force:
            preset_id = session.get("preset_id", session_id) if session else session_id
            preset_path = output or Path(f"presets/{preset_id}.yaml")
            result["preset_path"] = str(preset_path)
            result["status"] = "converged"

        typer.echo(json.dumps(result, indent=2))
    else:
        # Human-readable output
        typer.echo(format_flight_check(flight_result))
        typer.echo("")

    if flight_result.passed or force:
        # Generate preset
        preset_id = session.get("preset_id", session_id) if session else session_id
        preset_path = output or Path(f"presets/{preset_id}.yaml")

        try:
            config = generate_preset(session_id, preset_path)

            # Update session status
            schema.update_session(session_id, {"status": "converged"})

            if not json_output:
                typer.echo(format_preset_summary(config))
                typer.echo(f"\nPreset saved to: {preset_path}")

            if not flight_result.passed and force:
                typer.echo("\nWarning: Forced finish - some checks did not pass", err=True)

        except Exception as e:
            typer.echo(f"Error generating preset: {e}", err=True)
            raise typer.Exit(1)
    else:
        if not json_output:
            typer.echo("\nTo continue calibrating, review more elements.")
            typer.echo("Use --force to generate preset anyway (not recommended).")
        raise typer.Exit(1)


@app.command()
def preview(
    pdf_path: Path = typer.Argument(..., help="Path to PDF file"),
    session_id: Optional[str] = typer.Option(
        None, "--session", "-s", help="Session ID to use learned patterns from"
    ),
    pages: Optional[str] = typer.Option(
        None, "--pages", "-p", help="Comma-separated page numbers (1-indexed)"
    ),
    max_pages: int = typer.Option(5, "--max-pages", "-n", help="Max pages to preview"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Preview extraction results before generating preset.

    Shows comparison between baseline detection and calibrated detection
    to validate that learned patterns improve extraction quality.
    """
    from extractor.pipeline.calibration.preview import (
        ExtractionPreview,
        format_preview_text,
        format_preview_json,
    )

    # Parse pages if provided
    page_list = None
    if pages:
        page_list = [int(p.strip()) for p in pages.split(",")]

    # Run preview
    previewer = ExtractionPreview()
    result = previewer.preview_extraction(
        pdf_path=pdf_path,
        session_key=session_id,
        pages=page_list,
        max_pages=max_pages,
    )

    if json_output:
        typer.echo(json.dumps(format_preview_json(result), indent=2))
    else:
        typer.echo(format_preview_text(result))


@app.command()
def present(
    pdf_path: Path = typer.Argument(..., help="Path to PDF file"),
    page: int = typer.Option(0, "--page", "-p", help="Page number (0-indexed)"),
    element_idx: int = typer.Option(0, "--idx", "-i", help="Element index on page"),
    round_num: int = typer.Option(1, "--round", "-r", help="Calibration round number"),
):
    """Format a single element for presentation in calibration conversation.

    Outputs the element in the standard presentation format used during
    human-agent calibration conversations.
    """
    from extractor.pipeline.calibration import detect_elements

    # Detect elements on the page
    elements_by_page = detect_elements(str(pdf_path), page_numbers=[page])

    if page not in elements_by_page:
        typer.echo(f"Error: No elements found on page {page}", err=True)
        raise typer.Exit(1)

    elements = elements_by_page[page]
    total = len(elements)

    if element_idx >= total:
        typer.echo(f"Error: Element index {element_idx} out of range (0-{total-1})", err=True)
        raise typer.Exit(1)

    elem = elements[element_idx]

    # Format the presentation
    presentation = f"""Element {element_idx + 1}/{total} on Page {page + 1} (Round {round_num})

Type: {elem.element_type.title()} ({round(elem.confidence * 100)}% confidence)
Bbox: [{round(elem.bbox[0])}, {round(elem.bbox[1])}, {round(elem.bbox[2])}, {round(elem.bbox[3])}]
Reasoning: {elem.reasoning}"""

    # Add font info if available
    if elem.font_info and elem.element_type == "header":
        font_info = elem.font_info
        presentation += f"\nFont: {font_info.name} {font_info.size:.1f}pt"
        if font_info.is_bold:
            presentation += " Bold"
        if font_info.is_italic:
            presentation += " Italic"

    # Add text preview for headers
    if elem.text and elem.element_type == "header":
        preview = elem.text[:50] + ("..." if len(elem.text) > 50 else "")
        presentation += f'\nText: "{preview}"'

    # Add table metadata
    if elem.metadata and elem.element_type == "table":
        rows = elem.metadata.get("rows", "?")
        cols = elem.metadata.get("cols", "?")
        presentation += f"\nStructure: {rows} rows x {cols} columns"

    # Add screenshot command
    bbox_str = (
        f"{round(elem.bbox[0])},{round(elem.bbox[1])},{round(elem.bbox[2])},{round(elem.bbox[3])}"
    )
    presentation += (
        f'\n\n[Use: pdf-screenshot --file {pdf_path} --page {page + 1} --highlight "{bbox_str}"]'
    )

    presentation += "\n\nIs this correct? (or describe what's wrong)"

    typer.echo(presentation)


@app.command()
def relations(
    session_id: str = typer.Argument(..., help="Session ID/key"),
    pdf_path: Optional[Path] = typer.Option(
        None, "--pdf", "-p", help="PDF path (defaults to session PDF)"
    ),
    pages: Optional[str] = typer.Option(None, "--pages", help="Comma-separated page numbers"),
    max_proposals: int = typer.Option(10, "--max", "-n", help="Max proposals to show"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Propose and annotate relations between elements.

    Detects potential relations (parent-child, caption-of, references)
    and formats them as questions for human confirmation.
    """
    from extractor.pipeline.calibration import (
        CalibrationSchema,
        detect_elements,
    )
    from extractor.pipeline.calibration.relations import (
        RelationDetector,
    )

    schema = CalibrationSchema()
    session = schema.get_session(session_id)

    if not session:
        typer.echo(f"Error: Session '{session_id}' not found", err=True)
        raise typer.Exit(1)

    # Get PDF path
    doc_path = pdf_path or Path(session.get("pdf_path", ""))
    if not doc_path or not doc_path.exists():
        typer.echo(f"Error: PDF not found: {doc_path}", err=True)
        raise typer.Exit(1)

    # Parse pages
    page_numbers = None
    if pages:
        page_numbers = [int(p.strip()) for p in pages.split(",")]

    # Detect elements
    elements_by_page = detect_elements(str(doc_path), page_numbers=page_numbers)

    # Flatten elements to list of dicts
    all_elements = []
    for page_num, elements in elements_by_page.items():
        for elem in elements:
            all_elements.append(
                {
                    "element_type": elem.element_type,
                    "page_num": elem.page_num,
                    "element_idx": elem.element_idx,
                    "bbox": elem.bbox,
                    "text": elem.text,
                    "confidence": elem.confidence,
                }
            )

    # Propose relations
    detector = RelationDetector()
    proposals = detector.propose_relations(all_elements, max_proposals=max_proposals)

    if json_output:
        result = {
            "session_id": session_id,
            "pdf_path": str(doc_path),
            "proposals": [
                {
                    "proposal_id": p.proposal_id,
                    "relation_type": p.relation_type.value,
                    "source": p.source_element,
                    "target": p.target_element,
                    "confidence": p.confidence,
                    "reasoning": p.reasoning,
                    "question": p.format_question(),
                }
                for p in proposals
            ],
        }
        typer.echo(json.dumps(result, indent=2))
    else:
        if not proposals:
            typer.echo("No relation proposals found.")
            return

        typer.echo(f"Found {len(proposals)} potential relations:\n")
        for i, proposal in enumerate(proposals, 1):
            typer.echo(f"--- Relation {i}/{len(proposals)} ---")
            typer.echo(f"Type: {proposal.relation_type.value}")
            typer.echo(proposal.format_question())
            typer.echo("")


@app.command()
def annotate_relation(
    session_id: str = typer.Argument(..., help="Session ID/key"),
    relation_type: str = typer.Argument(
        ..., help="Relation type: parent_child, caption_of, references"
    ),
    source_id: str = typer.Argument(..., help="Source element ID"),
    target_id: str = typer.Argument(..., help="Target element ID"),
    note: Optional[str] = typer.Option(None, "--note", "-n", help="Optional note"),
):
    """Annotate a relation between two elements.

    Use this after human confirms a relation proposal.
    """
    from extractor.pipeline.calibration.relations import (
        RelationType,
        AnnotatedRelation,
        RelationHandler,
    )

    # Validate relation type
    try:
        rtype = RelationType(relation_type)
    except ValueError:
        valid = ", ".join(rt.value for rt in RelationType)
        typer.echo(
            f"Error: Invalid relation type '{relation_type}'. Valid types: {valid}", err=True
        )
        raise typer.Exit(1)

    # Create and save relation
    handler = RelationHandler()
    relation = AnnotatedRelation(
        relation_type=rtype,
        source_id=source_id,
        target_id=target_id,
        confirmed_by="human",
        note=note or "",
    )

    key = handler.save_relation(session_id, relation)
    typer.echo(json.dumps({"ok": True, "relation_key": key, "relation_type": relation_type}))


@app.command()
def relation_stats(
    session_id: str = typer.Argument(..., help="Session ID/key"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show relation statistics for a session."""
    from extractor.pipeline.calibration.relations import (
        RelationHandler,
        format_relation_summary,
    )

    handler = RelationHandler()
    relations = handler.get_session_relations(session_id)
    stats = handler.get_relation_stats(session_id)

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "session_id": session_id,
                    "total_relations": len(relations),
                    "by_type": stats,
                },
                indent=2,
            )
        )
    else:
        typer.echo(f"Session: {session_id}")
        typer.echo(f"Total relations: {len(relations)}")
        typer.echo("")
        typer.echo(format_relation_summary(relations))


# =====================================================
# TIMEOUT LEARNING COMMANDS
# =====================================================

timeout_app = typer.Typer(
    name="timeout",
    help="Timeout model training and validation",
)
app.add_typer(timeout_app, name="timeout")


@timeout_app.command("collect")
def timeout_collect(
    corpus_dir: Path = typer.Option(
        Path(os.environ.get("CORPUS_ROOT", "/mnt/storage12tb/extractor_corpus")),
        "--corpus-dir", "-c",
        help="Path to extractor corpus"
    ),
    output: Path = typer.Option(
        Path("timeout_training_data.parquet"),
        "--output", "-o",
        help="Output parquet file"
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress"),
):
    """Collect timeout training data from corpus results.

    Scans corpus results to extract features (page_count, table_count, etc.)
    and actual extraction durations for training the timeout model.
    """
    from extractor.pipeline.calibration.timeout_learner import (
        collect_training_data,
        analyze_training_data,
    )

    typer.echo(f"Collecting timeout training data from: {corpus_dir}")

    df = collect_training_data(corpus_dir, verbose=not quiet)

    if df is None or len(df) == 0:
        typer.echo("No samples collected!", err=True)
        raise typer.Exit(1)

    # Save to parquet
    df.to_parquet(output, index=False)
    typer.echo(f"\nSaved {len(df)} samples to: {output}")

    # Always analyze
    analyze_training_data(df)


@timeout_app.command("train")
def timeout_train(
    data_path: Path = typer.Option(
        Path("timeout_training_data.parquet"),
        "--data", "-d",
        help="Training data parquet file"
    ),
    output: Path = typer.Option(
        None,
        "--output", "-o",
        help="Output model JSON path (default: calibration/timeout_model.json)"
    ),
    holdout: float = typer.Option(0.2, "--holdout", help="Holdout fraction for validation"),
):
    """Train timeout prediction model from collected data.

    Uses linear regression on features like page_count, table_count,
    figure_count to predict extraction duration.
    """
    import pandas as pd
    from extractor.pipeline.calibration.timeout_learner import (
        train_timeout_model,
        save_timeout_model,
        validate_timeout_model,
    )

    if not data_path.exists():
        typer.echo(f"Error: Training data not found: {data_path}", err=True)
        typer.echo("Run 'calibrate timeout collect' first.")
        raise typer.Exit(1)

    df = pd.read_parquet(data_path)
    typer.echo(f"Loaded {len(df)} training samples")

    # Split for validation if requested
    if holdout > 0:
        from sklearn.model_selection import train_test_split
        train_df, val_df = train_test_split(df, test_size=holdout, random_state=42)
        typer.echo(f"Training: {len(train_df)}, Validation: {len(val_df)}")
    else:
        train_df = df
        val_df = None

    # Train model
    model = train_timeout_model(train_df)

    # Validate if holdout
    if val_df is not None:
        metrics = validate_timeout_model(model, val_df)
        typer.echo("\n--- Validation Metrics ---")
        typer.echo(f"  MAE: {metrics['mae']:.1f}s")
        typer.echo(f"  RMSE: {metrics['rmse']:.1f}s")
        typer.echo(f"  R²: {metrics['r2']:.3f}")
        typer.echo(f"  Within 30s: {metrics['within_30s']*100:.1f}%")
        typer.echo(f"  Within 60s: {metrics['within_60s']*100:.1f}%")

    # Save model
    output_path = output or Path("src/extractor/pipeline/calibration/timeout_model.json")
    save_timeout_model(model, output_path)
    typer.echo(f"\nModel saved to: {output_path}")

    # Print model coefficients
    typer.echo("\n--- Learned Coefficients ---")
    typer.echo(f"  Base timeout: {model.base_timeout_s:.1f}s")
    typer.echo(f"  Per page: {model.sec_per_page:.2f}s")
    typer.echo(f"  Per table: {model.sec_per_table:.2f}s")
    typer.echo(f"  Per figure: {model.sec_per_figure:.2f}s")
    typer.echo(f"  Per section: {model.sec_per_section:.2f}s")
    typer.echo(f"  Formula mult: {model.formula_multiplier:.2f}x")
    typer.echo(f"  Requirements mult: {model.requirements_multiplier:.2f}x")
    if model.domain_multipliers:
        typer.echo("  Domain multipliers:")
        for domain, mult in model.domain_multipliers.items():
            typer.echo(f"    {domain}: {mult:.2f}x")


@timeout_app.command("validate")
def timeout_validate(
    corpus_dir: Path = typer.Option(
        Path(os.environ.get("CORPUS_ROOT", "/mnt/storage12tb/extractor_corpus")),
        "--corpus-dir", "-c",
        help="Path to extractor corpus"
    ),
    model_path: Path = typer.Option(
        None,
        "--model", "-m",
        help="Model JSON path (default: calibration/timeout_model.json)"
    ),
    sample_size: int = typer.Option(100, "--sample", "-n", help="Sample size for validation"),
):
    """Validate timeout model against corpus data.

    Compares predicted vs actual extraction times.
    """
    import random
    import pandas as pd
    from extractor.pipeline.calibration.timeout_learner import (
        collect_training_data,
        load_timeout_model,
        validate_timeout_model,
    )

    # Load model
    model_file = model_path or Path("src/extractor/pipeline/calibration/timeout_model.json")
    if not model_file.exists():
        typer.echo(f"Error: Model not found: {model_file}", err=True)
        typer.echo("Run 'calibrate timeout train' first.")
        raise typer.Exit(1)

    model = load_timeout_model(model_file)
    typer.echo(f"Loaded model from: {model_file}")

    # Collect validation data
    df = collect_training_data(corpus_dir, verbose=False)
    if df is None or len(df) == 0:
        typer.echo("Error: No validation data found", err=True)
        raise typer.Exit(1)

    # Sample if needed
    if len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42)
        typer.echo(f"Sampled {sample_size} PDFs for validation")
    else:
        typer.echo(f"Validating on {len(df)} PDFs")

    # Validate
    metrics = validate_timeout_model(model, df)

    typer.echo("\n--- Validation Results ---")
    typer.echo(f"  Mean Absolute Error: {metrics['mae']:.1f}s")
    typer.echo(f"  Root Mean Squared Error: {metrics['rmse']:.1f}s")
    typer.echo(f"  R² Score: {metrics['r2']:.3f}")
    typer.echo(f"  Within 30s of actual: {metrics['within_30s']*100:.1f}%")
    typer.echo(f"  Within 60s of actual: {metrics['within_60s']*100:.1f}%")

    # Show worst predictions
    typer.echo("\n--- Largest Prediction Errors ---")
    worst = metrics.get('worst_predictions', [])
    for pred in worst[:5]:
        typer.echo(f"  {pred['source']}: predicted {pred['predicted']:.0f}s, actual {pred['actual']:.0f}s (error: {pred['error']:.0f}s)")


@timeout_app.command("predict")
def timeout_predict(
    pdf_path: Path = typer.Argument(..., help="Path to PDF file"),
    model_path: Path = typer.Option(
        None,
        "--model", "-m",
        help="Model JSON path"
    ),
):
    """Predict extraction timeout for a PDF.

    Runs S00 profile detection and uses learned model to predict timeout.
    """
    from extractor.pipeline.calibration.timeout_learner import (
        load_timeout_model,
        predict_timeout,
        TimeoutFeatures,
    )
    from extractor.pipeline.steps.s00_profile_detector import profile_pdf

    # Load model
    model_file = model_path or Path("src/extractor/pipeline/calibration/timeout_model.json")
    if not model_file.exists():
        typer.echo(f"Warning: Model not found at {model_file}, using defaults")
        model = None
    else:
        model = load_timeout_model(model_file)

    # Profile the PDF
    typer.echo(f"Profiling: {pdf_path}")
    profile = profile_pdf(str(pdf_path))

    # Build features
    elements = profile.get("elements", {})
    features = TimeoutFeatures(
        page_count=profile.get("page_count", 1),
        file_size_mb=profile.get("file_size_mb", 0.0),
        table_pages=elements.get("table_pages", 0),
        has_tables=elements.get("tables", False),
        has_figures=elements.get("figures", False),
        has_formulas=elements.get("formulas", False),
        has_requirements=elements.get("requirements", False),
        estimated_sections=profile.get("hierarchy", {}).get("estimated_sections", 0),
        domain=profile.get("domain", "general"),
    )

    # Predict
    if model:
        predicted_s = predict_timeout(features, model)
        source = "learned model"
    else:
        # Fallback to S00 estimate
        predicted_s = profile.get("estimated_timeout_seconds", 300)
        source = "S00 heuristic"

    typer.echo(f"\n--- Timeout Prediction ({source}) ---")
    typer.echo(f"  Pages: {features.page_count}")
    typer.echo(f"  Table pages: {features.table_pages}")
    typer.echo(f"  Has formulas: {features.has_formulas}")
    typer.echo(f"  Has requirements: {features.has_requirements}")
    typer.echo(f"  Domain: {features.domain}")
    typer.echo(f"\n  Predicted timeout: {predicted_s:.0f}s ({predicted_s/60:.1f} min)")


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
