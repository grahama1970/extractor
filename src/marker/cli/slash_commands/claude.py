"""Claude integration slash commands for marker.

Provides commands for Claude-based analysis and verification.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import typer
from loguru import logger
import json
import asyncio

from .base import CommandGroup, validate_file_path, format_output
from marker.core.processors.claude_table_merge_analyzer import BackgroundTableAnalyzer as ClaudeTableMergeAnalyzer
from marker.core.processors.claude_section_verifier import BackgroundSectionVerifier
from marker.core.processors.claude_content_validator import BackgroundContentValidator
from marker.core.processors.claude_structure_analyzer import BackgroundStructureAnalyzer
from marker.core.processors.claude_image_describer import BackgroundImageDescriber
from marker.core.schema.document import Document


class ClaudeCommands(CommandGroup):
    """Claude AI integration commands."""
    
    def __init__(self):
        super().__init__(
            name="marker-claude",
            description="Claude AI-powered document analysis and verification",
            category="ai"
        )
    
    def _setup_commands(self):
        """Setup Claude command handlers."""
        super()._setup_commands()
        
        @self.app.command()
        def analyze(
            json_path: str = typer.Argument(..., help="Path to marker JSON output"),
            analysis_type: str = typer.Option("all", help="Type of analysis (all, tables, sections, content, structure)"),
            output_path: Optional[str] = typer.Option(None, help="Output path for results"),
            timeout: int = typer.Option(300, help="Timeout in seconds"),
            verbose: bool = typer.Option(False, help="Verbose output")
        ):
            """Run Claude analysis on extracted document."""
            try:
                json_path = validate_file_path(json_path)
                
                logger.info(f"Running Claude {analysis_type} analysis on {json_path}")
                
                # Load document
                with open(json_path, 'r', encoding='utf-8') as f:
                    doc_data = json.load(f)
                
                # Create document instance
                doc = Document.from_json(doc_data)
                
                results = {}
                
                # Run requested analyses
                if analysis_type in ["all", "tables"]:
                    print("🔍 Analyzing table merges...")
                    analyzer = ClaudeTableMergeAnalyzer()
                    
                    # Find tables to analyze
                    tables = [b for b in doc.blocks if b.block_type == 'Table']
                    if tables:
                        # Create analysis tasks
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        try:
                            task_ids = []
                            for i, table in enumerate(tables[:5]):  # Limit to 5 tables
                                config = {
                                    'table_data': table.to_dict(),
                                    'context': f"Table {i+1} from {doc.filename}"
                                }
                                task_id = loop.run_until_complete(
                                    analyzer.analyze_table_merge(config)
                                )
                                task_ids.append(task_id)
                                if verbose:
                                    print(f"  Submitted task {task_id} for table {i+1}")
                            
                            # Poll for results
                            import time
                            start_time = time.time()
                            completed = []
                            
                            while len(completed) < len(task_ids) and time.time() - start_time < timeout:
                                for task_id in task_ids:
                                    if task_id not in completed:
                                        result = loop.run_until_complete(
                                            analyzer.get_result(task_id)
                                        )
                                        if result and result.get('status') == 'completed':
                                            completed.append(task_id)
                                            if verbose:
                                                print(f"  Task {task_id} completed")
                                
                                if len(completed) < len(task_ids):
                                    time.sleep(2)  # Poll every 2 seconds
                            
                            # Collect results
                            table_results = []
                            for task_id in task_ids:
                                result = loop.run_until_complete(
                                    analyzer.get_result(task_id)
                                )
                                if result:
                                    table_results.append(result)
                            
                            results['table_analysis'] = table_results
                            print(f"  ✅ Analyzed {len(completed)} tables")
                        finally:
                            loop.close()
                    else:
                        print("  No tables found in document")
                
                if analysis_type in ["all", "sections"]:
                    print("🔍 Verifying section hierarchy...")
                    verifier = BackgroundSectionVerifier()
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        task_id = loop.run_until_complete(
                            verifier.verify_sections(doc)
                        )
                        
                        # Poll for result
                        import time
                        start_time = time.time()
                        
                        while time.time() - start_time < timeout:
                            result = loop.run_until_complete(
                                verifier.get_result(task_id)
                            )
                            if result and result.get('status') == 'completed':
                                results['section_verification'] = result
                                print(f"  ✅ Section verification complete")
                                break
                            time.sleep(2)
                    finally:
                        loop.close()
                
                if analysis_type in ["all", "content"]:
                    print("🔍 Validating content quality...")
                    validator = BackgroundContentValidator()
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        task_id = loop.run_until_complete(
                            validator.validate_content(doc)
                        )
                        
                        # Poll for result
                        import time
                        start_time = time.time()
                        
                        while time.time() - start_time < timeout:
                            result = loop.run_until_complete(
                                validator.get_result(task_id)
                            )
                            if result and result.get('status') == 'completed':
                                results['content_validation'] = result
                                print(f"  ✅ Content validation complete")
                                break
                            time.sleep(2)
                    finally:
                        loop.close()
                
                if analysis_type in ["all", "structure"]:
                    print("🔍 Analyzing document structure...")
                    analyzer = BackgroundStructureAnalyzer()
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        task_id = loop.run_until_complete(
                            analyzer.analyze_structure(doc)
                        )
                        
                        # Poll for result
                        import time
                        start_time = time.time()
                        
                        while time.time() - start_time < timeout:
                            result = loop.run_until_complete(
                                analyzer.get_result(task_id)
                            )
                            if result and result.get('status') == 'completed':
                                results['structure_analysis'] = result
                                print(f"  ✅ Structure analysis complete")
                                break
                            time.sleep(2)
                    finally:
                        loop.close()
                
                # Save results
                if output_path:
                    output_file = Path(output_path)
                else:
                    output_file = Path(json_path).parent / f"{Path(json_path).stem}_claude_analysis.json"
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                
                print(f"\n✅ Analysis complete. Results saved to: {output_file}")
                
                # Show summary
                if results:
                    print("\n📊 Analysis Summary:")
                    
                    if 'table_analysis' in results:
                        completed_tables = [r for r in results['table_analysis'] if r.get('status') == 'completed']
                        print(f"  Tables analyzed: {len(completed_tables)}")
                    
                    if 'section_verification' in results:
                        issues = results['section_verification'].get('analysis', {}).get('issues', [])
                        print(f"  Section issues found: {len(issues)}")
                    
                    if 'content_validation' in results:
                        scores = results['content_validation'].get('analysis', {}).get('scores', {})
                        if scores:
                            avg_score = sum(scores.values()) / len(scores)
                            print(f"  Content quality score: {avg_score:.2f}/10")
                    
                    if 'structure_analysis' in results:
                        structure_type = results['structure_analysis'].get('analysis', {}).get('structure_type', 'Unknown')
                        print(f"  Document structure: {structure_type}")
                
            except Exception as e:
                logger.error(f"Analysis failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def verify(
            json_path: str = typer.Argument(..., help="Path to marker JSON output"),
            fix_issues: bool = typer.Option(False, help="Attempt to fix identified issues"),
            output_path: Optional[str] = typer.Option(None, help="Output path for fixed document")
        ):
            """Verify extraction quality with Claude."""
            try:
                json_path = validate_file_path(json_path)
                
                logger.info(f"Verifying extraction quality for {json_path}")
                
                # Load document
                with open(json_path, 'r', encoding='utf-8') as f:
                    doc_data = json.load(f)
                
                doc = Document.from_json(doc_data)
                
                # Run section verification
                verifier = BackgroundSectionVerifier()
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    task_id = loop.run_until_complete(
                        verifier.verify_sections(doc)
                    )
                    
                    # Poll for result
                    import time
                    start_time = time.time()
                    result = None
                    
                    while time.time() - start_time < 300:  # 5 minute timeout
                        result = loop.run_until_complete(
                            verifier.get_result(task_id)
                        )
                        if result and result.get('status') == 'completed':
                            break
                        time.sleep(2)
                    
                    if not result or result.get('status') != 'completed':
                        print("❌ Verification timed out")
                        raise typer.Exit(1)
                    
                    # Display results
                    analysis = result.get('analysis', {})
                    issues = analysis.get('issues', [])
                    
                    if not issues:
                        print("✅ No issues found! Document structure looks good.")
                    else:
                        print(f"⚠️  Found {len(issues)} issues:\n")
                        for i, issue in enumerate(issues, 1):
                            print(f"{i}. {issue['type']}: {issue['description']}")
                            print(f"   Location: Page {issue['page']}")
                            if 'suggestion' in issue:
                                print(f"   Suggestion: {issue['suggestion']}")
                            print()
                    
                    # Fix issues if requested
                    if fix_issues and issues:
                        print("🔧 Attempting to fix issues...")
                        
                        # Apply fixes (this would need implementation)
                        # For now, just save the verification results
                        doc_data['claude_verification'] = analysis
                        
                        if output_path:
                            output_file = Path(output_path)
                        else:
                            output_file = Path(json_path).parent / f"{Path(json_path).stem}_verified.json"
                        
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(doc_data, f, indent=2, ensure_ascii=False)
                        
                        print(f"✅ Saved verified document to: {output_file}")
                
                finally:
                    loop.close()
                
            except Exception as e:
                logger.error(f"Verification failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def describe_images(
            json_path: str = typer.Argument(..., help="Path to marker JSON output"),
            output_path: Optional[str] = typer.Option(None, help="Output path for results"),
            image_dir: Optional[str] = typer.Option(None, help="Directory containing extracted images"),
            max_images: int = typer.Option(10, help="Maximum images to process")
        ):
            """Generate descriptions for images using Claude's multimodal capabilities."""
            try:
                json_path = validate_file_path(json_path)
                
                logger.info(f"Describing images from {json_path}")
                
                # Load document
                with open(json_path, 'r', encoding='utf-8') as f:
                    doc_data = json.load(f)
                
                doc = Document.from_json(doc_data)
                
                # Find image blocks
                image_blocks = [b for b in doc.blocks if b.block_type in ['Figure', 'Picture']]
                
                if not image_blocks:
                    print("No images found in document")
                    return
                
                print(f"Found {len(image_blocks)} images. Processing up to {max_images}...")
                
                # Use image describer
                describer = BackgroundImageDescriber()
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    task_ids = []
                    
                    # Submit description tasks
                    for i, block in enumerate(image_blocks[:max_images]):
                        # Construct image path
                        if image_dir:
                            img_path = Path(image_dir) / f"image_{i+1}.png"
                        else:
                            # Try to extract from block metadata
                            img_path = block.metadata.get('image_path') if hasattr(block, 'metadata') else None
                        
                        if img_path and Path(img_path).exists():
                            task_id = loop.run_until_complete(
                                describer.describe_image(str(img_path), block)
                            )
                            task_ids.append((task_id, i))
                            print(f"  Submitted task for image {i+1}")
                    
                    if not task_ids:
                        print("No valid image paths found")
                        return
                    
                    # Poll for results
                    import time
                    start_time = time.time()
                    results = {}
                    
                    while len(results) < len(task_ids) and time.time() - start_time < 600:  # 10 min timeout
                        for task_id, idx in task_ids:
                            if task_id not in results:
                                result = loop.run_until_complete(
                                    describer.get_result(task_id)
                                )
                                if result and result.get('status') == 'completed':
                                    results[task_id] = {
                                        'index': idx,
                                        'description': result.get('analysis', {})
                                    }
                                    print(f"  ✅ Completed image {idx+1}")
                        
                        if len(results) < len(task_ids):
                            time.sleep(2)
                    
                    # Save results
                    if output_path:
                        output_file = Path(output_path)
                    else:
                        output_file = Path(json_path).parent / f"{Path(json_path).stem}_image_descriptions.json"
                    
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(results, f, indent=2, ensure_ascii=False)
                    
                    print(f"\n✅ Described {len(results)} images")
                    print(f"Results saved to: {output_file}")
                    
                    # Show sample descriptions
                    if results:
                        print("\n📸 Sample Descriptions:")
                        for task_id, data in list(results.items())[:3]:
                            desc = data['description']
                            print(f"\nImage {data['index']+1}:")
                            print(f"  Type: {desc.get('type', 'Unknown')}")
                            print(f"  Description: {desc.get('description', 'N/A')[:200]}...")
                
                finally:
                    loop.close()
                
            except Exception as e:
                logger.error(f"Image description failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def merge_tables(
            json_path: str = typer.Argument(..., help="Path to marker JSON output"),
            output_path: Optional[str] = typer.Option(None, help="Output path for merged tables"),
            threshold: float = typer.Option(0.8, help="Merge confidence threshold"),
            max_distance: int = typer.Option(5, help="Maximum block distance for merging")
        ):
            """Analyze and merge related tables using Claude."""
            try:
                json_path = validate_file_path(json_path)
                
                logger.info(f"Analyzing tables for merging in {json_path}")
                
                # Load document
                with open(json_path, 'r', encoding='utf-8') as f:
                    doc_data = json.load(f)
                
                doc = Document.from_json(doc_data)
                
                # Find tables
                tables = [(i, b) for i, b in enumerate(doc.blocks) if b.block_type == 'Table']
                
                if len(tables) < 2:
                    print("Need at least 2 tables to analyze merging")
                    return
                
                print(f"Found {len(tables)} tables. Analyzing potential merges...")
                
                # Use table merge analyzer
                analyzer = ClaudeTableMergeAnalyzer()
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    merge_candidates = []
                    
                    # Check adjacent tables
                    for i in range(len(tables) - 1):
                        idx1, table1 = tables[i]
                        idx2, table2 = tables[i + 1]
                        
                        # Check if tables are close enough
                        if idx2 - idx1 <= max_distance:
                            config = {
                                'table1': table1.to_dict(),
                                'table2': table2.to_dict(),
                                'context': f"Tables at positions {idx1} and {idx2}"
                            }
                            
                            task_id = loop.run_until_complete(
                                analyzer.analyze_table_merge(config)
                            )
                            
                            merge_candidates.append({
                                'task_id': task_id,
                                'table1_idx': idx1,
                                'table2_idx': idx2
                            })
                    
                    if not merge_candidates:
                        print("No adjacent tables found for merging")
                        return
                    
                    print(f"Analyzing {len(merge_candidates)} potential merges...")
                    
                    # Poll for results
                    import time
                    start_time = time.time()
                    merge_results = []
                    
                    while len(merge_results) < len(merge_candidates) and time.time() - start_time < 300:
                        for candidate in merge_candidates:
                            if candidate['task_id'] not in [r['task_id'] for r in merge_results]:
                                result = loop.run_until_complete(
                                    analyzer.get_result(candidate['task_id'])
                                )
                                if result and result.get('status') == 'completed':
                                    analysis = result.get('analysis', {})
                                    if analysis.get('should_merge') and analysis.get('confidence', 0) >= threshold:
                                        merge_results.append({
                                            **candidate,
                                            'confidence': analysis['confidence'],
                                            'reason': analysis.get('reason', '')
                                        })
                        
                        time.sleep(2)
                    
                    # Display results
                    if merge_results:
                        print(f"\n✅ Found {len(merge_results)} tables that should be merged:\n")
                        for mr in merge_results:
                            print(f"  Tables {mr['table1_idx']} + {mr['table2_idx']}")
                            print(f"    Confidence: {mr['confidence']:.2%}")
                            print(f"    Reason: {mr['reason']}")
                            print()
                        
                        # Apply merges if output path specified
                        if output_path:
                            # TODO: Implement actual table merging logic
                            # For now, just save the merge analysis
                            output_file = Path(output_path)
                            with open(output_file, 'w', encoding='utf-8') as f:
                                json.dump({
                                    'document': doc.filename,
                                    'merge_analysis': merge_results
                                }, f, indent=2)
                            
                            print(f"Merge analysis saved to: {output_file}")
                    else:
                        print("No tables meet the merge criteria")
                
                finally:
                    loop.close()
                
            except Exception as e:
                logger.error(f"Table merge analysis failed: {e}")
                raise typer.Exit(1)
    
    def get_examples(self) -> List[str]:
        """Get example usage."""
        return [
            "/marker-claude analyze document.json --analysis-type all",
            "/marker-claude verify document.json --fix-issues",
            "/marker-claude describe-images document.json --max-images 5",
            "/marker-claude merge-tables document.json --threshold 0.9",
        ]