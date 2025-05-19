#!/bin/bash

# Test the CLI with summaries on a real PDF
cd /home/graham/workspace/experiments/marker
source .venv/bin/activate

echo "Testing CLI with summaries on a real PDF..."
echo "========================================="

# Convert the PDF with summaries
python cli.py convert single ./repos/camelot/docs/_static/pdf/us-030.pdf \
    --output-format json \
    --add-summaries \
    --output-dir ./test_output

# Check if the output file exists
if [ -f "./test_output/us-030/us-030.json" ]; then
    echo "Output file created successfully"
    
    # Extract and display summaries using Python
    python -c "
import json
import sys

with open('./test_output/us-030/us-030.json', 'r') as f:
    data = json.load(f)
    
if 'metadata' in data and 'document_summary' in data['metadata']:
    print('\nDocument Summary:')
    print('-' * 50)
    print(data['metadata']['document_summary'])
    
    if 'section_summaries' in data['metadata']:
        print('\n\nSection Summaries:')
        print('-' * 50)
        for section in data['metadata']['section_summaries']:
            print(f\"\nSection: {section['title']}\")
            print(f\"Summary: {section['summary']}\")
else:
    print('No summaries found in output')
"
else
    echo "Error: Output file not found"
fi