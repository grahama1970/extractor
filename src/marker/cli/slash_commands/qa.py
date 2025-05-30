"""QA generation and validation slash commands for marker.

Provides commands for generating and validating question-answer pairs.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import typer
from loguru import logger
import json

from .base import CommandGroup, validate_file_path, format_output
from marker.core.arangodb.qa_generator import generate_qa_pairs
from marker.core.arangodb.validators.qa_validator import validate_qa_pairs as validate_qa_pairs_func
from marker.core.schema.document import Document


class QACommands(CommandGroup):
    """Question-Answer generation and validation commands."""
    
    def __init__(self):
        super().__init__(
            name="marker-qa",
            description="Generate and validate question-answer pairs from documents",
            category="qa"
        )
    
    def _setup_commands(self):
        """Setup QA command handlers."""
        super()._setup_commands()
        
        @self.app.command()
        def generate(
            json_path: str = typer.Argument(..., help="Path to marker JSON output"),
            output_path: Optional[str] = typer.Option(None, help="Output path for QA pairs"),
            qa_type: str = typer.Option("all", help="Type of QA to generate (all, factual, conceptual, analytical)"),
            num_questions: int = typer.Option(10, help="Number of questions per section"),
            model: str = typer.Option("gpt-4", help="LLM model to use"),
            include_context: bool = typer.Option(True, help="Include context with QA pairs")
        ):
            """Generate QA pairs from extracted document."""
            try:
                json_path = validate_file_path(json_path)
                
                logger.info(f"Generating QA pairs from {json_path}")
                
                # Load document
                with open(json_path, 'r', encoding='utf-8') as f:
                    doc_data = json.load(f)
                
                # Generate QA pairs
                qa_pairs, stats = generate_qa_pairs(
                    marker_output=doc_data,
                    output_dir=str(Path(json_path).parent / "qa_output"),
                    max_questions=num_questions,
                    question_types=[qa_type] if qa_type != "all" else ["factual", "conceptual", "application"]
                )
                
                if not qa_pairs:
                    print("No QA pairs generated")
                    return
                
                print(f"✅ Generated {len(qa_pairs)} QA pairs")
                
                # Group by type
                by_type = {}
                for qa in qa_pairs:
                    qa_type = qa.get('type', 'general')
                    if qa_type not in by_type:
                        by_type[qa_type] = []
                    by_type[qa_type].append(qa)
                
                # Show distribution
                print("\n📊 QA Distribution:")
                for qa_type, items in by_type.items():
                    print(f"  {qa_type}: {len(items)} questions")
                
                # Save QA pairs
                if output_path:
                    output_file = Path(output_path)
                else:
                    output_file = Path(json_path).parent / f"{Path(json_path).stem}_qa.json"
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'document': Path(json_path).stem,
                        'total_questions': len(qa_pairs),
                        'qa_pairs': qa_pairs
                    }, f, indent=2, ensure_ascii=False)
                
                print(f"\n💾 Saved QA pairs to: {output_file}")
                
                # Show sample QA pairs
                print("\n📝 Sample QA Pairs:")
                for qa in qa_pairs[:3]:
                    print(f"\nQ: {qa['question']}")
                    print(f"A: {qa['answer'][:200]}..." if len(qa['answer']) > 200 else f"A: {qa['answer']}")
                    if include_context and 'context' in qa:
                        print(f"Context: {qa['context'][:100]}...")
                
            except Exception as e:
                logger.error(f"QA generation failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def validate(
            qa_path: str = typer.Argument(..., help="Path to QA JSON file"),
            document_path: Optional[str] = typer.Option(None, help="Path to source document for validation"),
            output_path: Optional[str] = typer.Option(None, help="Output path for validation results"),
            model: str = typer.Option("gpt-4", help="LLM model to use for validation"),
            sample_size: Optional[int] = typer.Option(None, help="Number of QA pairs to validate")
        ):
            """Validate QA pairs for accuracy and relevance."""
            try:
                qa_path = validate_file_path(qa_path)
                
                logger.info(f"Validating QA pairs from {qa_path}")
                
                # Load QA pairs
                with open(qa_path, 'r', encoding='utf-8') as f:
                    qa_data = json.load(f)
                
                qa_pairs = qa_data.get('qa_pairs', [])
                
                if not qa_pairs:
                    print("No QA pairs found to validate")
                    return
                
                # Sample if requested
                if sample_size and sample_size < len(qa_pairs):
                    import random
                    qa_pairs = random.sample(qa_pairs, sample_size)
                    print(f"Validating sample of {sample_size} QA pairs")
                else:
                    print(f"Validating all {len(qa_pairs)} QA pairs")
                
                # Load source document if provided
                source_doc = None
                if document_path:
                    document_path = validate_file_path(document_path)
                    with open(document_path, 'r', encoding='utf-8') as f:
                        source_doc = json.load(f)
                
                # Validate QA pairs
                # Need to save qa_pairs to a temp file for validation
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                    for qa in qa_pairs:
                        f.write(json.dumps(qa) + '\n')
                    temp_qa_path = f.name
                
                try:
                    validation_results = validate_qa_pairs_func(
                        qa_pairs_path=temp_qa_path,
                        marker_output_path=document_path if document_path else None
                    )
                finally:
                    import os
                    if os.path.exists(temp_qa_path):
                        os.unlink(temp_qa_path)
                
                # Calculate statistics
                total_validated = len(validation_results)
                valid_count = sum(1 for r in validation_results if r['is_valid'])
                accuracy_scores = [r['accuracy_score'] for r in validation_results if 'accuracy_score' in r]
                relevance_scores = [r['relevance_score'] for r in validation_results if 'relevance_score' in r]
                
                avg_accuracy = sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0
                avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
                
                # Display results
                print(f"\n✅ Validation Complete")
                print(f"\n📊 Validation Results:")
                print(f"  Total validated: {total_validated}")
                print(f"  Valid QA pairs: {valid_count} ({valid_count/total_validated*100:.1f}%)")
                print(f"  Average accuracy: {avg_accuracy:.2f}/10")
                print(f"  Average relevance: {avg_relevance:.2f}/10")
                
                # Show issues
                issues = [r for r in validation_results if not r['is_valid']]
                if issues:
                    print(f"\n⚠️  Found {len(issues)} issues:")
                    for i, issue in enumerate(issues[:5], 1):  # Show first 5
                        print(f"\n{i}. Question: {issue['question'][:100]}...")
                        print(f"   Issues: {', '.join(issue.get('issues', []))}")
                        if 'suggestion' in issue:
                            print(f"   Suggestion: {issue['suggestion']}")
                
                # Save validation results
                if output_path:
                    output_file = Path(output_path)
                else:
                    output_file = Path(qa_path).parent / f"{Path(qa_path).stem}_validation.json"
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'total_validated': total_validated,
                        'valid_count': valid_count,
                        'validation_rate': valid_count / total_validated if total_validated > 0 else 0,
                        'average_accuracy': avg_accuracy,
                        'average_relevance': avg_relevance,
                        'validation_results': validation_results
                    }, f, indent=2, ensure_ascii=False)
                
                print(f"\n💾 Saved validation results to: {output_file}")
                
            except Exception as e:
                logger.error(f"QA validation failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def test(
            document_path: str = typer.Argument(..., help="Path to document to test"),
            qa_path: str = typer.Argument(..., help="Path to QA pairs"),
            output_path: Optional[str] = typer.Option(None, help="Output path for test results"),
            model: str = typer.Option("gpt-4", help="LLM model to use"),
            verbose: bool = typer.Option(False, help="Show detailed results")
        ):
            """Test document extraction quality using QA pairs."""
            try:
                document_path = validate_file_path(document_path)
                qa_path = validate_file_path(qa_path)
                
                logger.info(f"Testing document with QA pairs")
                
                # Load document and QA pairs
                with open(document_path, 'r', encoding='utf-8') as f:
                    doc_data = json.load(f)
                
                with open(qa_path, 'r', encoding='utf-8') as f:
                    qa_data = json.load(f)
                
                qa_pairs = qa_data.get('qa_pairs', [])
                
                if not qa_pairs:
                    print("No QA pairs found")
                    return
                
                print(f"Testing with {len(qa_pairs)} QA pairs...")
                
                # Run QA testing
                from marker.core.services.litellm import LiteLLMService
                llm_service = LiteLLMService()
                
                test_results = []
                correct_count = 0
                
                for i, qa in enumerate(qa_pairs):
                    # Extract answer from document
                    prompt = f"""Given the following document content, answer this question:

Document: {json.dumps(doc_data, indent=2)[:3000]}...

Question: {qa['question']}

Provide a concise answer based only on the document content."""
                    
                    response = llm_service.call_llm(prompt, model=model)
                    extracted_answer = response.get('content', '')
                    
                    # Compare with expected answer
                    comparison_prompt = f"""Compare these two answers and determine if they convey the same information:

Expected Answer: {qa['answer']}

Extracted Answer: {extracted_answer}

Are these answers essentially the same? Respond with YES or NO and a brief explanation."""
                    
                    comparison = llm_service.call_llm(comparison_prompt, model=model)
                    comparison_text = comparison.get('content', '')
                    
                    is_correct = 'YES' in comparison_text.upper()
                    if is_correct:
                        correct_count += 1
                    
                    test_results.append({
                        'question': qa['question'],
                        'expected_answer': qa['answer'],
                        'extracted_answer': extracted_answer,
                        'is_correct': is_correct,
                        'comparison': comparison_text
                    })
                    
                    if verbose:
                        print(f"\n{i+1}. {'✅' if is_correct else '❌'} {qa['question']}")
                        if not is_correct:
                            print(f"   Expected: {qa['answer'][:100]}...")
                            print(f"   Got: {extracted_answer[:100]}...")
                
                # Calculate accuracy
                accuracy = correct_count / len(qa_pairs) if qa_pairs else 0
                
                print(f"\n📊 Test Results:")
                print(f"  Total questions: {len(qa_pairs)}")
                print(f"  Correct answers: {correct_count}")
                print(f"  Accuracy: {accuracy:.1%}")
                
                # Analyze by question type
                by_type_results = {}
                for result, qa in zip(test_results, qa_pairs):
                    qa_type = qa.get('type', 'general')
                    if qa_type not in by_type_results:
                        by_type_results[qa_type] = {'correct': 0, 'total': 0}
                    by_type_results[qa_type]['total'] += 1
                    if result['is_correct']:
                        by_type_results[qa_type]['correct'] += 1
                
                print(f"\n📈 Accuracy by Question Type:")
                for qa_type, stats in by_type_results.items():
                    type_accuracy = stats['correct'] / stats['total'] if stats['total'] > 0 else 0
                    print(f"  {qa_type}: {type_accuracy:.1%} ({stats['correct']}/{stats['total']})")
                
                # Save test results
                if output_path:
                    output_file = Path(output_path)
                else:
                    output_file = Path(document_path).parent / f"{Path(document_path).stem}_qa_test.json"
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'document': Path(document_path).stem,
                        'total_questions': len(qa_pairs),
                        'correct_answers': correct_count,
                        'accuracy': accuracy,
                        'by_type_results': by_type_results,
                        'test_results': test_results
                    }, f, indent=2, ensure_ascii=False)
                
                print(f"\n💾 Saved test results to: {output_file}")
                
            except Exception as e:
                logger.error(f"QA testing failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def report(
            results_dir: str = typer.Argument(..., help="Directory containing QA test results"),
            output_path: str = typer.Option("qa_report.html", help="Output path for report"),
            include_charts: bool = typer.Option(True, help="Include visualization charts")
        ):
            """Generate comprehensive QA quality report."""
            try:
                results_path = Path(results_dir)
                if not results_path.exists():
                    raise typer.BadParameter(f"Directory not found: {results_dir}")
                
                # Find all test result files
                test_files = list(results_path.glob("*_qa_test.json"))
                
                if not test_files:
                    print("No test result files found")
                    return
                
                print(f"Found {len(test_files)} test results. Generating report...")
                
                # Aggregate results
                all_results = []
                for test_file in test_files:
                    with open(test_file, 'r', encoding='utf-8') as f:
                        results = json.load(f)
                        results['filename'] = test_file.stem
                        all_results.append(results)
                
                # Calculate overall statistics
                total_questions = sum(r['total_questions'] for r in all_results)
                total_correct = sum(r['correct_answers'] for r in all_results)
                overall_accuracy = total_correct / total_questions if total_questions > 0 else 0
                
                # Generate HTML report
                html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>QA Quality Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        h1, h2 {{
            color: #333;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #007bff;
        }}
        .stat-label {{
            color: #666;
            margin-top: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #007bff;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .chart-container {{
            position: relative;
            height: 400px;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 QA Quality Report</h1>
        <p>Generated on {json.dumps(str(Path(output_path).stat().st_mtime))}</p>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{len(all_results)}</div>
                <div class="stat-label">Documents Tested</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_questions:,}</div>
                <div class="stat-label">Total Questions</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_correct:,}</div>
                <div class="stat-label">Correct Answers</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{overall_accuracy:.1%}</div>
                <div class="stat-label">Overall Accuracy</div>
            </div>
        </div>
        
        <h2>📈 Document Performance</h2>
        <table>
            <thead>
                <tr>
                    <th>Document</th>
                    <th>Questions</th>
                    <th>Correct</th>
                    <th>Accuracy</th>
                </tr>
            </thead>
            <tbody>
"""
                
                # Add document rows
                for result in sorted(all_results, key=lambda x: x['accuracy'], reverse=True):
                    accuracy_color = "green" if result['accuracy'] >= 0.8 else "orange" if result['accuracy'] >= 0.6 else "red"
                    html_content += f"""
                <tr>
                    <td>{result['filename']}</td>
                    <td>{result['total_questions']}</td>
                    <td>{result['correct_answers']}</td>
                    <td style="color: {accuracy_color}; font-weight: bold;">{result['accuracy']:.1%}</td>
                </tr>
"""
                
                html_content += """
            </tbody>
        </table>
"""
                
                if include_charts:
                    # Aggregate by type results
                    type_totals = {}
                    for result in all_results:
                        for qa_type, stats in result.get('by_type_results', {}).items():
                            if qa_type not in type_totals:
                                type_totals[qa_type] = {'correct': 0, 'total': 0}
                            type_totals[qa_type]['correct'] += stats['correct']
                            type_totals[qa_type]['total'] += stats['total']
                    
                    html_content += """
        <h2>📊 Accuracy by Question Type</h2>
        <div class="chart-container">
            <canvas id="typeChart"></canvas>
        </div>
        
        <script>
            const ctx = document.getElementById('typeChart').getContext('2d');
            const typeData = {
"""
                    
                    html_content += f"""
                labels: {json.dumps(list(type_totals.keys()))},
                datasets: [{{
                    label: 'Accuracy',
                    data: {json.dumps([stats['correct']/stats['total']*100 if stats['total'] > 0 else 0 for stats in type_totals.values()])},
                    backgroundColor: 'rgba(54, 162, 235, 0.6)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }}]
            }};
            
            new Chart(ctx, {{
                type: 'bar',
                data: typeData,
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            max: 100,
                            ticks: {{
                                callback: function(value) {{
                                    return value + '%';
                                }}
                            }}
                        }}
                    }},
                    plugins: {{
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    return context.dataset.label + ': ' + context.parsed.y.toFixed(1) + '%';
                                }}
                            }}
                        }}
                    }}
                }}
            }});
        </script>
"""
                
                html_content += """
    </div>
</body>
</html>
"""
                
                # Save report
                output_file = Path(output_path)
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                print(f"✅ Report generated: {output_file}")
                print(f"\nOpen in browser to view the interactive report")
                
            except Exception as e:
                logger.error(f"Report generation failed: {e}")
                raise typer.Exit(1)
    
    def get_examples(self) -> List[str]:
        """Get example usage."""
        return [
            "/marker-qa generate document.json --num-questions 20",
            "/marker-qa validate qa_pairs.json --sample-size 50",
            "/marker-qa test document.json qa_pairs.json --verbose",
            "/marker-qa report ./test_results/ --output-path qa_report.html",
        ]