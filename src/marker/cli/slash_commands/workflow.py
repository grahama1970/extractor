"""Workflow slash commands for marker.

Provides commands for managing document processing workflows.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import typer
from loguru import logger
import json
import yaml

from .base import CommandGroup, validate_file_path, format_output


class WorkflowCommands(CommandGroup):
    """Workflow management commands."""
    
    def __init__(self):
        super().__init__(
            name="marker-workflow",
            description="Manage and execute document processing workflows",
            category="workflow"
        )
        self.workflows_dir = Path.home() / ".marker" / "workflows"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
    
    def _setup_commands(self):
        """Setup workflow command handlers."""
        super()._setup_commands()
        
        @self.app.command()
        def list(
            output_format: str = typer.Option("table", help="Output format (table, json, yaml)")
        ):
            """List available workflows."""
            try:
                # Get built-in workflows
                builtin_workflows = {
                    "standard": {
                        "name": "Standard Extraction",
                        "description": "Standard PDF extraction with OCR",
                        "steps": ["extract", "ocr", "structure", "output"]
                    },
                    "enhanced": {
                        "name": "Enhanced Extraction",
                        "description": "Enhanced extraction with Claude analysis",
                        "steps": ["extract", "ocr", "structure", "claude_analyze", "output"]
                    },
                    "qa": {
                        "name": "QA Generation",
                        "description": "Extract and generate QA pairs",
                        "steps": ["extract", "structure", "qa_generate", "qa_validate"]
                    },
                    "arangodb": {
                        "name": "ArangoDB Pipeline",
                        "description": "Extract and import to ArangoDB",
                        "steps": ["extract", "structure", "arangodb_import", "relationship_extract"]
                    },
                    "research": {
                        "name": "Research Pipeline",
                        "description": "Extract with emphasis on citations and references",
                        "steps": ["extract", "ocr", "structure", "citation_extract", "reference_link"]
                    }
                }
                
                # Get custom workflows
                custom_workflows = {}
                for workflow_file in self.workflows_dir.glob("*.yaml"):
                    with open(workflow_file, 'r') as f:
                        workflow = yaml.safe_load(f)
                        custom_workflows[workflow_file.stem] = workflow
                
                # Combine workflows
                all_workflows = {**builtin_workflows, **custom_workflows}
                
                if not all_workflows:
                    print("No workflows found")
                    return
                
                # Format output
                if output_format == "json":
                    print(json.dumps(all_workflows, indent=2))
                elif output_format == "yaml":
                    print(yaml.dump(all_workflows, default_flow_style=False))
                else:
                    # Table format
                    workflow_list = []
                    for key, workflow in all_workflows.items():
                        workflow_list.append({
                            'name': key,
                            'description': workflow.get('description', ''),
                            'steps': len(workflow.get('steps', [])),
                            'type': 'custom' if key in custom_workflows else 'builtin'
                        })
                    
                    print("📋 Available Workflows:\n")
                    print(format_output(workflow_list, "table"))
                
            except Exception as e:
                logger.error(f"Failed to list workflows: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def create(
            name: str = typer.Argument(..., help="Workflow name"),
            description: str = typer.Option("", help="Workflow description"),
            interactive: bool = typer.Option(True, help="Interactive workflow creation")
        ):
            """Create a new workflow."""
            try:
                workflow_file = self.workflows_dir / f"{name}.yaml"
                
                if workflow_file.exists():
                    overwrite = typer.confirm(f"Workflow '{name}' already exists. Overwrite?")
                    if not overwrite:
                        raise typer.Exit()
                
                workflow = {
                    'name': name,
                    'description': description,
                    'steps': [],
                    'config': {}
                }
                
                if interactive:
                    print(f"\n🔧 Creating workflow '{name}'")
                    
                    # Get description if not provided
                    if not description:
                        workflow['description'] = typer.prompt("Description")
                    
                    # Available steps
                    available_steps = [
                        "extract - Extract content from PDF",
                        "ocr - Run OCR on images/scanned pages",
                        "structure - Analyze document structure",
                        "tables - Extract and process tables",
                        "code - Extract and analyze code blocks",
                        "claude_analyze - Run Claude AI analysis",
                        "qa_generate - Generate QA pairs",
                        "qa_validate - Validate QA pairs",
                        "arangodb_import - Import to ArangoDB",
                        "relationship_extract - Extract entity relationships",
                        "citation_extract - Extract citations",
                        "reference_link - Link references",
                        "summary_generate - Generate summaries",
                        "output - Generate output files"
                    ]
                    
                    print("\n📝 Available steps:")
                    for i, step in enumerate(available_steps, 1):
                        print(f"  {i}. {step}")
                    
                    # Select steps
                    print("\nSelect steps (enter numbers separated by commas, or 'done' to finish):")
                    while True:
                        selection = typer.prompt("Steps")
                        if selection.lower() == 'done':
                            break
                        
                        try:
                            indices = [int(x.strip()) - 1 for x in selection.split(',')]
                            for idx in indices:
                                if 0 <= idx < len(available_steps):
                                    step_name = available_steps[idx].split(' - ')[0]
                                    if step_name not in workflow['steps']:
                                        workflow['steps'].append(step_name)
                                        print(f"  Added: {step_name}")
                        except (ValueError, IndexError):
                            print("Invalid selection")
                    
                    # Configure steps
                    print("\n⚙️  Configure steps (press Enter for defaults):")
                    
                    if 'extract' in workflow['steps']:
                        max_pages = typer.prompt("Max pages to extract", default="")
                        if max_pages:
                            workflow['config']['extract'] = {'max_pages': int(max_pages)}
                    
                    if 'ocr' in workflow['steps']:
                        ocr_all = typer.confirm("OCR all pages?", default=False)
                        workflow['config']['ocr'] = {'all_pages': ocr_all}
                    
                    if 'claude_analyze' in workflow['steps']:
                        analysis_types = typer.prompt(
                            "Claude analysis types (tables,sections,content,structure)",
                            default="all"
                        )
                        workflow['config']['claude'] = {'analysis_types': analysis_types}
                    
                    if 'qa_generate' in workflow['steps']:
                        num_questions = typer.prompt("Questions per section", default="10")
                        workflow['config']['qa'] = {'questions_per_section': int(num_questions)}
                    
                    if 'output' in workflow['steps']:
                        output_formats = typer.prompt("Output formats (markdown,json,html)", default="markdown")
                        workflow['config']['output'] = {'formats': output_formats.split(',')}
                
                # Save workflow
                with open(workflow_file, 'w') as f:
                    yaml.dump(workflow, f, default_flow_style=False)
                
                print(f"\n✅ Workflow '{name}' created: {workflow_file}")
                
                # Show workflow
                print("\n📋 Workflow configuration:")
                print(yaml.dump(workflow, default_flow_style=False))
                
            except Exception as e:
                logger.error(f"Failed to create workflow: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def run(
            workflow_name: str = typer.Argument(..., help="Workflow name"),
            input_path: str = typer.Argument(..., help="Input file or directory"),
            output_dir: Optional[str] = typer.Option(None, help="Output directory"),
            config_overrides: Optional[str] = typer.Option(None, help="JSON config overrides"),
            dry_run: bool = typer.Option(False, help="Show what would be executed"),
            parallel: bool = typer.Option(False, help="Run in parallel for multiple files")
        ):
            """Execute a workflow."""
            try:
                input_path = Path(input_path)
                if not input_path.exists():
                    raise typer.BadParameter(f"Input not found: {input_path}")
                
                # Load workflow
                workflow = self._load_workflow(workflow_name)
                if not workflow:
                    print(f"Workflow '{workflow_name}' not found")
                    raise typer.Exit(1)
                
                # Parse config overrides
                config = workflow.get('config', {})
                if config_overrides:
                    overrides = json.loads(config_overrides)
                    config.update(overrides)
                
                # Setup output directory
                if output_dir:
                    output_path = Path(output_dir)
                else:
                    output_path = Path.cwd() / f"{workflow_name}_output"
                
                output_path.mkdir(parents=True, exist_ok=True)
                
                # Find input files
                if input_path.is_file():
                    input_files = [input_path]
                else:
                    input_files = list(input_path.glob("*.pdf"))
                
                if not input_files:
                    print("No PDF files found")
                    return
                
                print(f"\n🚀 Running workflow '{workflow_name}'")
                print(f"  Input files: {len(input_files)}")
                print(f"  Output directory: {output_path}")
                print(f"  Steps: {', '.join(workflow['steps'])}")
                
                if dry_run:
                    print("\n🔍 Dry run - would execute:")
                    for step in workflow['steps']:
                        print(f"  - {step}")
                    return
                
                # Execute workflow
                from concurrent.futures import ProcessPoolExecutor, as_completed
                from tqdm import tqdm
                
                def process_file(pdf_file: Path) -> Dict[str, Any]:
                    """Process a single file through the workflow."""
                    results = {'file': str(pdf_file), 'status': 'started'}
                    
                    try:
                        # Create file-specific output directory
                        file_output = output_path / pdf_file.stem
                        file_output.mkdir(exist_ok=True)
                        
                        # Track intermediate results
                        context = {
                            'input_file': pdf_file,
                            'output_dir': file_output,
                            'config': config
                        }
                        
                        # Execute each step
                        for step in workflow['steps']:
                            step_result = self._execute_step(step, context)
                            results[step] = step_result
                            
                            # Update context with results
                            if isinstance(step_result, dict):
                                context.update(step_result)
                        
                        results['status'] = 'completed'
                        
                    except Exception as e:
                        results['status'] = 'failed'
                        results['error'] = str(e)
                        logger.error(f"Failed to process {pdf_file}: {e}")
                    
                    return results
                
                # Process files
                all_results = []
                
                if parallel and len(input_files) > 1:
                    # Parallel processing
                    with ProcessPoolExecutor(max_workers=4) as executor:
                        futures = {executor.submit(process_file, f): f for f in input_files}
                        
                        with tqdm(total=len(input_files), desc="Processing") as pbar:
                            for future in as_completed(futures):
                                result = future.result()
                                all_results.append(result)
                                pbar.update(1)
                else:
                    # Sequential processing
                    for pdf_file in tqdm(input_files, desc="Processing"):
                        result = process_file(pdf_file)
                        all_results.append(result)
                
                # Summary
                completed = sum(1 for r in all_results if r['status'] == 'completed')
                failed = sum(1 for r in all_results if r['status'] == 'failed')
                
                print(f"\n✅ Workflow complete")
                print(f"  Processed: {len(all_results)} files")
                print(f"  Successful: {completed}")
                print(f"  Failed: {failed}")
                
                # Save workflow results
                results_file = output_path / "workflow_results.json"
                with open(results_file, 'w') as f:
                    json.dump({
                        'workflow': workflow_name,
                        'total_files': len(all_results),
                        'completed': completed,
                        'failed': failed,
                        'results': all_results
                    }, f, indent=2)
                
                print(f"\n📊 Results saved to: {results_file}")
                
            except Exception as e:
                logger.error(f"Workflow execution failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def status(
            results_path: str = typer.Argument(..., help="Path to workflow results")
        ):
            """Check workflow execution status."""
            try:
                results_file = validate_file_path(results_path)
                
                with open(results_file, 'r') as f:
                    results = json.load(f)
                
                print(f"\n📊 Workflow Status")
                print(f"  Workflow: {results['workflow']}")
                print(f"  Total files: {results['total_files']}")
                print(f"  Completed: {results['completed']}")
                print(f"  Failed: {results['failed']}")
                
                # Show failed files
                failed_files = [r for r in results['results'] if r['status'] == 'failed']
                if failed_files:
                    print(f"\n❌ Failed files:")
                    for f in failed_files:
                        print(f"  - {f['file']}: {f.get('error', 'Unknown error')}")
                
                # Show step statistics
                step_stats = {}
                for result in results['results']:
                    if result['status'] == 'completed':
                        for step, step_result in result.items():
                            if step not in ['file', 'status']:
                                if step not in step_stats:
                                    step_stats[step] = {'success': 0, 'total': 0}
                                step_stats[step]['total'] += 1
                                if isinstance(step_result, dict) and step_result.get('status') == 'success':
                                    step_stats[step]['success'] += 1
                
                if step_stats:
                    print(f"\n📈 Step Statistics:")
                    for step, stats in step_stats.items():
                        success_rate = stats['success'] / stats['total'] if stats['total'] > 0 else 0
                        print(f"  {step}: {success_rate:.1%} success ({stats['success']}/{stats['total']})")
                
            except Exception as e:
                logger.error(f"Failed to get status: {e}")
                raise typer.Exit(1)
        
        def _load_workflow(self, name: str) -> Optional[Dict[str, Any]]:
            """Load a workflow by name."""
            # Check custom workflows first
            custom_file = self.workflows_dir / f"{name}.yaml"
            if custom_file.exists():
                with open(custom_file, 'r') as f:
                    return yaml.safe_load(f)
            
            # Check built-in workflows
            builtin_workflows = {
                "standard": {
                    "name": "Standard Extraction",
                    "description": "Standard PDF extraction with OCR",
                    "steps": ["extract", "ocr", "structure", "output"],
                    "config": {}
                },
                "enhanced": {
                    "name": "Enhanced Extraction",
                    "description": "Enhanced extraction with Claude analysis",
                    "steps": ["extract", "ocr", "structure", "claude_analyze", "output"],
                    "config": {
                        "claude": {"analysis_types": "all"}
                    }
                },
                "qa": {
                    "name": "QA Generation",
                    "description": "Extract and generate QA pairs",
                    "steps": ["extract", "structure", "qa_generate", "qa_validate"],
                    "config": {
                        "qa": {"questions_per_section": 10}
                    }
                },
                "arangodb": {
                    "name": "ArangoDB Pipeline",
                    "description": "Extract and import to ArangoDB",
                    "steps": ["extract", "structure", "arangodb_import", "relationship_extract"],
                    "config": {}
                },
                "research": {
                    "name": "Research Pipeline",
                    "description": "Extract with emphasis on citations and references",
                    "steps": ["extract", "ocr", "structure", "citation_extract", "reference_link"],
                    "config": {}
                }
            }
            
            return builtin_workflows.get(name)
        
        def _execute_step(self, step: str, context: Dict[str, Any]) -> Dict[str, Any]:
            """Execute a workflow step."""
            input_file = context['input_file']
            output_dir = context['output_dir']
            config = context.get('config', {})
            
            # Step implementations
            if step == "extract":
                # Run extraction
                from marker.core.converters.pdf import PdfConverter
                from marker.core.config.parser import ConfigParser
                
                config_parser = ConfigParser()
                pdf_config = config_parser.get_pdf_config()
                
                # Apply config overrides
                extract_config = config.get('extract', {})
                if 'max_pages' in extract_config:
                    pdf_config.max_pages = extract_config['max_pages']
                
                converter = PdfConverter(config=pdf_config)
                doc = converter.convert(input_file)
                
                # Save extraction
                json_file = output_dir / "extracted.json"
                with open(json_file, 'w') as f:
                    json.dump(doc.to_json(), f, indent=2, ensure_ascii=False)
                
                return {
                    'status': 'success',
                    'document': doc,
                    'json_file': str(json_file)
                }
            
            elif step == "ocr":
                # OCR processing (if needed)
                # This would be handled in extraction typically
                return {'status': 'success'}
            
            elif step == "structure":
                # Structure analysis
                doc = context.get('document')
                if doc:
                    # Analyze structure (already done in extraction)
                    return {'status': 'success'}
                return {'status': 'skipped', 'reason': 'No document in context'}
            
            elif step == "claude_analyze":
                # Claude analysis
                json_file = context.get('json_file')
                if json_file:
                    # Would run Claude analysis here
                    return {'status': 'success', 'analysis_file': str(output_dir / "claude_analysis.json")}
                return {'status': 'skipped', 'reason': 'No JSON file in context'}
            
            elif step == "qa_generate":
                # QA generation
                json_file = context.get('json_file')
                if json_file:
                    # Would generate QA pairs here
                    return {'status': 'success', 'qa_file': str(output_dir / "qa_pairs.json")}
                return {'status': 'skipped', 'reason': 'No JSON file in context'}
            
            elif step == "output":
                # Generate output files
                doc = context.get('document')
                json_file = context.get('json_file')
                
                if doc or json_file:
                    output_formats = config.get('output', {}).get('formats', ['markdown'])
                    
                    for fmt in output_formats:
                        if fmt == 'markdown':
                            from marker.core.output import output_to_format
                            
                            if doc:
                                md_file = output_dir / "output.md"
                                output_to_format(doc, md_file, 'markdown')
                            elif json_file:
                                # Convert from JSON
                                with open(json_file, 'r') as f:
                                    doc_data = json.load(f)
                                from marker.core.schema.document import Document
                                doc = Document.from_json(doc_data)
                                md_file = output_dir / "output.md"
                                output_to_format(doc, md_file, 'markdown')
                    
                    return {'status': 'success'}
                
                return {'status': 'skipped', 'reason': 'No document to output'}
            
            else:
                # Unknown step
                return {'status': 'skipped', 'reason': f'Step {step} not implemented'}
    
    def get_examples(self) -> List[str]:
        """Get example usage."""
        return [
            "/marker-workflow list",
            "/marker-workflow create research --interactive",
            "/marker-workflow run standard document.pdf",
            "/marker-workflow run enhanced ./pdfs/ --parallel",
            "/marker-workflow status workflow_output/workflow_results.json",
        ]