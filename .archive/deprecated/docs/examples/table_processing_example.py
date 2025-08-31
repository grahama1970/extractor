"""
Example: Complete Table Processing Workflow
Shows how to use the enhanced table processors with pandas integration
"""

import json
from pathlib import Path

# Example 1: Basic Table Quality Assessment
def example_quality_assessment():
    """Show basic table quality assessment workflow."""
    from extractor.core.processors.llm.table_quality_processor import TableQualityProcessor
    
    # Sample technical datasheet table
    html_table = """
    <table>
        <tr>
            <th rowspan="2">Parameter</th>
            <th colspan="3">Electrical Characteristics</th>
            <th rowspan="2">Unit</th>
        </tr>
        <tr>
            <th>Min</th>
            <th>Typ</th>
            <th>Max</th>
        </tr>
        <tr>
            <td>Supply Voltage</td>
            <td>2.7</td>
            <td>3.3</td>
            <td>3.6</td>
            <td>V</td>
        </tr>
        <tr>
            <td>Operating Temperature</td>
            <td>-40</td>
            <td>25</td>
            <td>85</td>
            <td>°C</td>
        </tr>
        <tr>
            <td>Supply Current (Active)</td>
            <td>-</td>
            <td>15</td>
            <td>25</td>
            <td>mA</td>
        </tr>
        <tr>
            <td>Supply Current (Sleep)</td>
            <td>-</td>
            <td>0.5</td>
            <td>2</td>
            <td>µA</td>
        </tr>
    </table>
    """
    
    processor = TableQualityProcessor()
    
    # Load into pandas
    df, load_result = processor.load_table_to_dataframe(html_table)
    
    if df is not None:
        print("=== Table Loaded Successfully ===")
        print(f"Shape: {df.shape}")
        print(f"Load issues: {load_result.get('issues', [])}")
        
        # Generate quality report
        quality_report = processor.generate_quality_report(df)
        
        print("\n=== Quality Metrics ===")
        print(f"Quality Score: {quality_report.get('quality_score', 0)}")
        print(f"Null percentage by column:")
        for col, pct in quality_report['basic_metrics']['null_percentage'].items():
            print(f"  Column {col}: {pct}%")
        
        print("\n=== Column Analysis ===")
        for col, analysis in quality_report['column_analysis'].items():
            print(f"Column {col}:")
            print(f"  Type: {analysis.get('likely_type', 'unknown')}")
            print(f"  Nulls: {analysis['null_count']}")
            print(f"  Sample: {analysis['sample_values']}")
        
        # Extract structured format
        structured = processor.extract_structured_table(
            df, 
            quality_report,
            title="Table 2.1: DC Electrical Characteristics",
            title_confidence=0.95
        )
        
        print("\n=== Structured Output ===")
        print(f"Title: {structured.title} (confidence: {structured.title_confidence})")
        print(f"Headers: {structured.headers}")
        print(f"Data rows: {len(structured.data)}")
        print(f"Pandas compatible: {structured.metrics.extraction_quality.pandas_compatible}")
        
        # Save output
        output = {
            "structured_table": structured.model_dump(),
            "quality_report": quality_report,
            "dataframe": df.to_dict(orient='records')
        }
        
        with open('/tmp/table_analysis_output.json', 'w') as f:
            json.dump(output, f, indent=2)
        
        print("\nOutput saved to: /tmp/table_analysis_output.json")
        
    else:
        print(f"Failed to load table: {load_result}")


# Example 2: Table Merge Decision with Metrics
def example_table_merge_with_metrics():
    """Show how pandas metrics improve merge decisions."""
    from extractor.core.processors.llm.table_pandas_analyzer import TablePandasAnalyzer
    from extractor.core.schema.blocks import TableCell
    
    # Create two tables that should be merged
    # Table 1 - Pin descriptions 1-25
    cells1 = [
        TableCell(row_id=0, col_id=0, text="Pin", rowspan=1, colspan=1),
        TableCell(row_id=0, col_id=1, text="Name", rowspan=1, colspan=1),
        TableCell(row_id=0, col_id=2, text="Type", rowspan=1, colspan=1),
        TableCell(row_id=0, col_id=3, text="Description", rowspan=1, colspan=1),
    ]
    
    # Add data rows
    for i in range(1, 26):
        cells1.extend([
            TableCell(row_id=i, col_id=0, text=str(i), rowspan=1, colspan=1),
            TableCell(row_id=i, col_id=1, text=f"P{i:02d}", rowspan=1, colspan=1),
            TableCell(row_id=i, col_id=2, text="I/O", rowspan=1, colspan=1),
            TableCell(row_id=i, col_id=3, text=f"GPIO Pin {i}", rowspan=1, colspan=1),
        ])
    
    # Table 2 - Pin descriptions 26-50 (no headers)
    cells2 = []
    for i in range(26, 51):
        cells2.extend([
            TableCell(row_id=i-26, col_id=0, text=str(i), rowspan=1, colspan=1),
            TableCell(row_id=i-26, col_id=1, text=f"P{i:02d}", rowspan=1, colspan=1),
            TableCell(row_id=i-26, col_id=2, text="I/O", rowspan=1, colspan=1),
            TableCell(row_id=i-26, col_id=3, text=f"GPIO Pin {i}", rowspan=1, colspan=1),
        ])
    
    analyzer = TablePandasAnalyzer()
    
    # Convert to DataFrames
    df1 = analyzer.cells_to_dataframe(cells1)
    df2 = analyzer.cells_to_dataframe(cells2)
    
    print("=== Table 1 Analysis ===")
    metrics1 = analyzer.calculate_table_metrics(df1)
    print(f"Headers detected: {metrics1['structure']['likely_header_rows']}")
    print(f"Sequential data: {metrics1['sequential_data']}")
    
    print("\n=== Table 2 Analysis ===")
    metrics2 = analyzer.calculate_table_metrics(df2)
    print(f"Headers detected: {metrics2['structure']['likely_header_rows']}")
    print(f"Sequential data: {metrics2['sequential_data']}")
    
    # Compare tables
    print("\n=== Merge Analysis ===")
    comparison = analyzer.compare_table_structures(df1, df2)
    print(f"Column count match: {comparison['column_count_match']}")
    print(f"Type compatibility: {comparison['type_compatibility']:.2%}")
    print(f"Sequential continuation: {comparison['sequential_continuation']}")
    print(f"Table 2 has headers: {comparison['table2_has_headers']}")
    print(f"Merge confidence: {comparison['merge_confidence']:.2%}")
    
    print("\n=== Decision ===")
    if comparison['merge_confidence'] > 0.7:
        print("✓ Tables should be MERGED (bottom direction)")
        print("  - Sequential pin numbers detected")
        print("  - Table 2 continues from Table 1")
        print("  - No headers in Table 2")
    else:
        print("✗ Tables should NOT be merged")


# Example 3: Complete Workflow with LLM
def example_complete_workflow():
    """Show complete workflow from HTML to structured output."""
    print("=== Complete Table Processing Workflow ===")
    
    # This would be used in actual processing:
    # 1. Extract HTML from PDF using marker
    # 2. Load into pandas with quality assessment
    # 3. Provide metrics to LLM for structural fixes only
    # 4. Output structured table with confidence scores
    
    workflow = """
    PDF Document
         ↓
    Marker Extraction (HTML tables)
         ↓
    TableQualityProcessor
         ├─→ Load to pandas DataFrame
         ├─→ Clean HTML (remove spans, handle br tags)
         ├─→ Generate quality report
         └─→ Detect headers and data types
              ↓
    LLM Processing (if quality < threshold)
         ├─→ Provide pandas metrics
         ├─→ Show structural issues
         ├─→ Request ONLY structural fixes
         └─→ FORBID data changes
              ↓
    Structured Output
         ├─→ Title (detected/inferred)
         ├─→ Headers (multi-row supported)
         ├─→ Data (exact preservation)
         └─→ Metrics (confidence, quality, compatibility)
              ↓
    Downstream Use
         ├─→ Direct pandas DataFrame
         ├─→ JSON for APIs
         └─→ ArangoDB storage
    """
    
    print(workflow)
    
    print("\nKey Benefits:")
    print("1. Data Integrity: LLM cannot modify table data")
    print("2. Quality Metrics: Objective assessment before LLM")
    print("3. Pandas Ready: Tables guaranteed to load in pandas")
    print("4. Confidence Scores: Know when extraction is uncertain")
    print("5. Title Detection: Automatic from context")


if __name__ == "__main__":
    print("Table Processing Examples\n")
    
    print("1. Quality Assessment Example")
    print("=" * 50)
    example_quality_assessment()
    
    print("\n\n2. Table Merge Analysis Example")
    print("=" * 50)
    example_table_merge_with_metrics()
    
    print("\n\n3. Complete Workflow")
    print("=" * 50)
    example_complete_workflow()