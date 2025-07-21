# Marker LLM Validation CLI Usage Guide

This guide provides comprehensive examples of using the Marker LLM validation CLI for all available capabilities including validation, multimodal processing, async batching, and advanced features.
Every command can be executed directly from the terminal to test the full range of functionality supported by the system.

## Table of Contents

- [Basic Validation](#basic-validation)
- [Validation with Different Models](#validation-with-different-models)
- [Corpus Validation](#corpus-validation)
- [Code Validation](#code-validation)
- [Table Validation](#table-validation)
- [Content Quality Validation](#content-quality-validation)
- [Citation Validation](#citation-validation)
- [Math Expression Validation](#math-expression-validation)
- [Image Description Validation](#image-description-validation)
- [Field Validation](#field-validation)
- [Custom Validators](#custom-validators)
- [Batch Validation](#batch-validation)
- [Async Batch Validation](#async-batch-validation)
- [Multimodal Processing](#multimodal-processing)
- [Advanced Multimodal Validation](#advanced-multimodal-validation)
- [Streaming Responses](#streaming-responses)
- [Parallel Processing](#parallel-processing)
- [Chain of Validation](#chain-of-validation)
- [Complex Validation Strategies](#complex-validation-strategies)
- [Debugging Tools](#debugging-tools)
- [Performance Profiling](#performance-profiling)
- [Comparing Validators](#comparing-validators)
- [Input/Output Options](#input-output-options)
- [Environment Configuration](#environment-configuration)
- [Integration Examples](#integration-examples)

## Basic Validation

### Simple Prompt Validation

```bash
# Validate a simple prompt with default settings
python -m marker.llm_call.cli.app validate "Generate a simple greeting"
```

### Validation with Retry Attempts

```bash
# Validate with 3 retry attempts
python -m marker.llm_call.cli.app validate "Generate a Python function to calculate Fibonacci numbers" --max-retries 3
```

### Specify Output File

```bash
# Save validation results to file
python -m marker.llm_call.cli.app validate "Create a JavaScript function" --output results.json
```

## Validation with Different Models

### Using Different LLM Models

```bash
# Validate using Gemini model
python -m marker.llm_call.cli.app validate "Generate Python code" --model "vertex_ai/gemini-1.5-pro"

# Validate using Claude model
python -m marker.llm_call.cli.app validate "Generate Python code" --model "claude-3-opus-20240229"

# Validate using GPT-4 model
python -m marker.llm_call.cli.app validate "Generate Python code" --model "gpt-4-turbo"
```

## Corpus Validation

### Validating Against Comma-Separated Values

```bash
# Validate if the response is in the allowed values list
python corpus_validator_cli.py "What is the largest city in Texas?" --corpus "London,Houston,New York City"
```

### Validating Against Values in a File

```bash
# Create a file with allowed values
echo -e "London\nHouston\nNew York City" > allowed_cities.txt

# Validate using corpus from file
python corpus_validator_cli.py "What is the Capital of England?" --corpus-file allowed_cities.txt
```

### Case-Sensitive Corpus Validation

```bash
# Case-sensitive validation
python corpus_validator_cli.py "What is the Capital of England?" --corpus "london,houston,new york city" --case-sensitive
```

### Providing a Custom Response

```bash
# Test with a custom response instead of simulated LLM response
python corpus_validator_cli.py "What is the Capital of France?" --corpus "London,Houston,New York City" --response "Paris"
```

### JSON Output Format

```bash
# Get results in JSON format
python corpus_validator_cli.py "What is the largest city in Texas?" --corpus "London,Houston,New York City" --json
```

## Code Validation

### Python Syntax Validation

```bash
# Validate Python syntax
python -m marker.llm_call.cli.app validate "Write a Python function to check if a number is prime" --validators python_syntax
```

### Code Language Detection Validation

```bash
# Validate code language detection
python -m marker.llm_call.cli.app validate "Write a sorting algorithm" --validators code_language
```

### Code Completeness Validation

```bash
# Validate code completeness
python -m marker.llm_call.cli.app validate "Write a React component" --validators code_completeness
```

### Combined Code Validators

```bash
# Use multiple code validators together
python -m marker.llm_call.cli.app validate "Write a Python class for a binary tree" \
  --validators python_syntax \
  --validators code_completeness
```

## Table Validation

### Table Structure Validation

```bash
# Validate table structure
python -m marker.llm_call.cli.app validate "Create an HTML table showing population data" --validators table_structure
```

### Table Consistency Validation

```bash
# Validate table consistency across rows
python -m marker.llm_call.cli.app validate "Create a table of monthly sales figures" --validators table_consistency
```

### Validating Tables with Sample Data

```bash
# Create a prompt file with a table to validate
cat > table_prompt.txt << EOL
Generate an HTML table with the following data:
Country | Population | Capital
USA | 331 million | Washington D.C.
India | 1.4 billion | New Delhi
China | 1.4 billion | Beijing
EOL

# Validate table with data from file
python -m marker.llm_call.cli.app validate --file table_prompt.txt --validators table_structure
```

## Content Quality Validation

### Basic Content Quality

```bash
# Validate content quality with default parameters
python -m marker.llm_call.cli.app validate "Write a paragraph about climate change" --validators content_quality
```

### Content Quality with Minimum Words

```bash
# Validate content quality with minimum word count
python -m marker.llm_call.cli.app validate "Summarize the benefits of renewable energy" \
  --validators "content_quality(min_words=50)"
```

### Tone Consistency Validation

```bash
# Validate tone consistency
python -m marker.llm_call.cli.app validate "Write a professional email to a client" --validators tone_consistency
```

### JSON Structure Validation

```bash
# Validate JSON structure
python -m marker.llm_call.cli.app validate "Generate a JSON config for a web application" --validators json_structure
```

## Citation Validation

### Citation Format Validation

```bash
# Validate citation format
python -m marker.llm_call.cli.app validate "Write a paragraph with academic citations" --validators citation_format
```

### Citation Matching Validation

```bash
# Create reference text
cat > references.txt << EOL
Smith, J. (2020). Machine Learning Fundamentals. Journal of AI Research, 15(2), 45-67.
Johnson, A. & Williams, B. (2019). Natural Language Processing. Computational Linguistics Review, 8(3), 112-128.
EOL

# Validate citations against reference text
python -m marker.llm_call.cli.app validate "Summarize recent advances in NLP with citations" \
  --validators "citation_match(reference_file='references.txt')"
```

### Citation Relevance Validation

```bash
# Validate citation relevance
python -m marker.llm_call.cli.app validate "Write about climate change with relevant citations" \
  --validators citation_relevance
```

## Math Expression Validation

### LaTeX Syntax Validation

```bash
# Validate LaTeX syntax
python -m marker.llm_call.cli.app validate "Write the quadratic formula using LaTeX" --validators latex_syntax
```

### Math Consistency Validation

```bash
# Validate mathematical consistency
python -m marker.llm_call.cli.app validate "Derive the solution to a quadratic equation" --validators math_consistency
```

## Image Description Validation

### Image Description Quality

```bash
# Validate image description quality
python -m marker.llm_call.cli.app validate "Describe the image in detail" \
  --validators image_description \
  --image "/home/graham/workspace/experiments/marker/data/images/table.png"
```

### Alt Text Accessibility Validation

```bash
# Validate image alt text for accessibility
python -m marker.llm_call.cli.app validate "Generate an accessible alt text for this image" \
  --validators alt_text \
  --image "/home/graham/workspace/experiments/marker/data/images/table.png"
```

## Field Validation

### Field Presence Validation

```bash
# Validate required fields are present
python -m marker.llm_call.cli.app validate "Generate contact information for a business" \
  --validators "field_presence(required_fields=['name', 'address', 'phone'])" \
  --response-format json
```

### Length Validation

```bash
# Validate field length
python -m marker.llm_call.cli.app validate "Write a short bio" \
  --validators "length_check(field_name='bio', min_length=50, max_length=200)" \
  --response-format json
```

### Format Validation

```bash
# Validate field format with regex
python -m marker.llm_call.cli.app validate "Generate a valid email address" \
  --validators "format_check(field_name='email', pattern='^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$')" \
  --response-format json
```

### Type Validation

```bash
# Validate field type
python -m marker.llm_call.cli.app validate "Generate a user's age" \
  --validators "type_check(field_name='age', expected_type='int')" \
  --response-format json
```

### Range Validation

```bash
# Validate numeric range
python -m marker.llm_call.cli.app validate "Generate a percentage value" \
  --validators "range_check(field_name='percentage', min_value=0, max_value=100)" \
  --response-format json
```

## Custom Validators

### Adding a Custom Validator

```bash
# Define a custom validator in a file
cat > custom_even_number_validator.py << EOL
from marker.llm_call.decorators import validator
from marker.llm_call.base import ValidationResult

@validator("even_number")
class EvenNumberValidator:
    def validate(self, response, context):
        try:
            num = int(response)
            if num % 2 == 0:
                return ValidationResult(valid=True)
            else:
                return ValidationResult(
                    valid=False,
                    error="Number is not even",
                    suggestions=["Provide an even number"]
                )
        except ValueError:
            return ValidationResult(
                valid=False,
                error="Response is not a number",
                suggestions=["Provide a numeric value"]
            )
EOL

# Add the custom validator
python -m marker.llm_call.cli.app add-validator custom_even_number_validator.py

# Use the custom validator
python -m marker.llm_call.cli.app validate "Generate an even number" --validators even_number
```

## Batch Validation

### Running Multiple Validators

```bash
# Validate with multiple validators in batch
python -m marker.llm_call.cli.app validate "Generate a Python function to calculate Fibonacci numbers" \
  --validators python_syntax \
  --validators code_completeness \
  --validators content_quality
```

### Batch Validation with Different Prompts

```bash
# Create a batch file with multiple prompts
cat > batch_prompts.json << EOL
[
  {"prompt": "Write a Python function", "validators": ["python_syntax", "code_completeness"]},
  {"prompt": "Create an HTML table of countries", "validators": ["table_structure", "content_quality"]},
  {"prompt": "Write an equation for the Pythagorean theorem", "validators": ["latex_syntax", "math_consistency"]}
]
EOL

# Run batch validation
python -m marker.llm_call.cli.app batch --file batch_prompts.json --output batch_results.json
```

## Async Batch Validation

### Running Validators Asynchronously

```bash
# Create an async batch file
cat > async_batch.json << EOL
[
  {"prompt": "Generate Python code for sorting", "validators": ["python_syntax"]},
  {"prompt": "Create a table of US states", "validators": ["table_structure"]},
  {"prompt": "Write a paragraph about AI", "validators": ["content_quality"]}
]
EOL

# Run async batch validation
python -m marker.llm_call.cli.app batch-async --file async_batch.json --concurrency 3 --output async_results.json
```

## Multimodal Processing

### Basic Image Processing

```bash
# Process a single image
python -m marker.llm_call.cli.app process-image \
  --image "/home/graham/workspace/experiments/marker/data/images/table.png" \
  --prompt "Describe what you see in this image" \
  --output image_description.txt
```

### Multiple Image Analysis

```bash
# Process multiple images in a batch
python -m marker.llm_call.cli.app process-images \
  --images "/home/graham/workspace/experiments/marker/data/images/table.png" "/home/graham/workspace/experiments/marker/data/images/overall.png" \
  --prompt "Compare and contrast these images" \
  --output image_comparison.json
```

### Image with Context

```bash
# Process image with additional context
python -m marker.llm_call.cli.app process-image \
  --image "/home/graham/workspace/experiments/marker/data/images/per_doc.png" \
  --context "This graph shows document processing performance across different models." \
  --prompt "Explain what this graph shows about performance" \
  --output image_analysis.txt
```

### Document with Images

```bash
# Extract and process images from a document
python -m marker.llm_call.cli.app process-document \
  --document "/home/graham/workspace/experiments/marker/data/input/2505.03335v2.pdf" \
  --extract-images \
  --process-images \
  --prompt "Describe each figure in this document" \
  --output document_figures.json
```

### Video Frame Analysis

```bash
# Extract and analyze frames from a video
python -m marker.llm_call.cli.app process-video \
  --video "/path/to/demo.mp4" \
  --frame-interval 5 \
  --prompt "Describe the action in this video frame" \
  --output video_analysis.json
```

## Advanced Multimodal Validation

### Image-Based Question Validation

```bash
# Validate responses to image-based questions
python -m marker.llm_call.cli.app validate-multimodal \
  --image "/home/graham/workspace/experiments/marker/data/images/table.png" \
  --prompt "How many columns does this table have?" \
  --validators "table_structure" \
  --validators "content_quality" \
  --expected-response "The table has 4 columns."
```

### OCR Quality Validation

```bash
# Validate OCR quality from image
python -m marker.llm_call.cli.app validate-ocr \
  --image "/home/graham/workspace/experiments/marker/data/images/table.png" \
  --validators "content_quality" \
  --validators "table_consistency" \
  --confidence-threshold 0.8 \
  --output ocr_validation.json
```

### Chart Data Extraction Validation

```bash
# Validate chart data extraction
python -m marker.llm_call.cli.app validate-chart \
  --image "/home/graham/workspace/experiments/marker/data/images/overall.png" \
  --prompt "Extract the data points from this chart" \
  --validators "json_structure" \
  --validators "content_quality" \
  --output chart_data.json
```

### Cross-Modal Consistency

```bash
# Check consistency between image and text
python -m marker.llm_call.cli.app validate-consistency \
  --image "/home/graham/workspace/experiments/marker/data/images/table.png" \
  --text "The table shows population data for 5 countries including USA, China, and India." \
  --validators "content_quality" \
  --output consistency_check.json
```

### Document Text-Image Alignment

```bash
# Validate text references to images in a document
python -m marker.llm_call.cli.app validate-alignment \
  --document "/home/graham/workspace/experiments/marker/data/input/2505.03335v2.pdf" \
  --validators "content_quality" \
  --output alignment_validation.json
```

## Streaming Responses

### Basic Streaming

```bash
# Stream validation results as they are generated
python -m marker.llm_call.cli.app validate "Generate a story about space exploration" \
  --validators content_quality \
  --stream
```

### Streaming with Token-by-Token Output

```bash
# Stream token-by-token output from LLM
python -m marker.llm_call.cli.app generate "Write a short story about AI" \
  --model "vertex_ai/gemini-1.5-pro" \
  --stream-tokens \
  --output story.txt
```

### Streaming Validation Updates

```bash
# Stream validation status updates
python -m marker.llm_call.cli.app validate "Generate a complex algorithm" \
  --validators code_completeness \
  --validators python_syntax \
  --stream-validation \
  --output algorithm_validation.json
```

### Streaming to WebSocket

```bash
# Stream validation results to a WebSocket
python -m marker.llm_call.cli.app validate "Generate data analysis code" \
  --validators python_syntax \
  --stream-to "ws://localhost:8080/validation" \
  --stream-format json
```

### Progressive Image Analysis

```bash
# Stream multi-step image analysis results
python -m marker.llm_call.cli.app analyze-image \
  --image "/home/graham/workspace/experiments/marker/data/images/overall.png" \
  --stream-analysis \
  --output image_analysis_stream.json
```

## Parallel Processing

### Multi-Worker Validation

```bash
# Run validation with multiple worker processes
python -m marker.llm_call.cli.app validate-parallel \
  --file batch_prompts.json \
  --workers 4 \
  --output parallel_results.json
```

### Distributed Processing

```bash
# Run validation across multiple machines (primary node)
python -m marker.llm_call.cli.app validate-distributed \
  --file large_batch.json \
  --nodes "192.168.1.101:5000,192.168.1.102:5000" \
  --primary \
  --output distributed_results.json
```

### Model Parallelism

```bash
# Run validation with model parallelism
python -m marker.llm_call.cli.app validate-models-parallel \
  --prompt "Generate complex Python code" \
  --models "gpt-4-turbo,claude-3-opus-20240229,vertex_ai/gemini-1.5-pro" \
  --validators python_syntax \
  --output model_comparison.json
```

### Validator Parallelism

```bash
# Run multiple validators in parallel
python -m marker.llm_call.cli.app validate-parallel-validators \
  --prompt "Write a technical paper on quantum computing" \
  --validators content_quality,citation_format,tone_consistency \
  --parallel-execution \
  --output validator_parallel_results.json
```

### GPU-Accelerated Validation

```bash
# Run GPU-accelerated validation for multiple prompts
python -m marker.llm_call.cli.app validate-gpu \
  --file prompts.json \
  --gpu-id 0 \
  --batch-size 16 \
  --validators python_syntax \
  --output gpu_validation.json
```

## Chain of Validation

### Sequential Validation Chain

```bash
# Create a chain of validators that run in sequence
python -m marker.llm_call.cli.app validate-chain \
  --prompt "Generate a research paper" \
  --chain "content_quality->citation_format->tone_consistency" \
  --output chain_validation.json
```

### Conditional Validation

```bash
# Run validators conditionally based on previous results
python -m marker.llm_call.cli.app validate-conditional \
  --prompt "Write Python code for data analysis" \
  --condition "python_syntax:valid ? code_completeness : content_quality" \
  --output conditional_validation.json
```

### Validation Pipeline

```bash
# Create a complex validation pipeline
python -m marker.llm_call.cli.app validate-pipeline \
  --pipeline-file pipeline.yaml \
  --input "Write a technical document about machine learning" \
  --output pipeline_results.json
```

### Multi-Stage Processing

```bash
# Run a multi-stage validation process
python -m marker.llm_call.cli.app validate-stages \
  --prompt "Generate a research paper on AI ethics" \
  --stage-1 "content_quality,tone_consistency" \
  --stage-2 "citation_format,citation_relevance" \
  --stage-3 "json_structure" \
  --output staged_validation.json
```

### Feedback Loop Validation

```bash
# Create a validation feedback loop
python -m marker.llm_call.cli.app validate-feedback-loop \
  --prompt "Write a Python function for sorting" \
  --validators python_syntax \
  --max-iterations 5 \
  --improvement-threshold 0.8 \
  --output feedback_results.json
```

## Complex Validation Strategies

### Validation with Custom Rules

```bash
# Apply custom validation rules
python -m marker.llm_call.cli.app validate-custom-rules \
  --prompt "Generate a secure password validation function" \
  --rules-file security_rules.yaml \
  --validators python_syntax \
  --output custom_validation.json
```

### Multi-Modal Mixed Validation

```bash
# Validate a mix of text and image inputs
python -m marker.llm_call.cli.app validate-mixed \
  --text "Describe the trend shown in the graph" \
  --image "/home/graham/workspace/experiments/marker/data/images/overall.png" \
  --validators content_quality \
  --validators image_description \
  --output mixed_validation.json
```

### Cross-Validator Consistency Check

```bash
# Check consistency across multiple validators
python -m marker.llm_call.cli.app validate-cross-check \
  --prompt "Write a paragraph about climate change" \
  --validators content_quality,tone_consistency,citation_relevance \
  --cross-check \
  --output cross_validation.json
```

### Ensemble Validation

```bash
# Run ensemble validation with multiple validators and voting
python -m marker.llm_call.cli.app validate-ensemble \
  --prompt "Generate a scientific explanation of quantum mechanics" \
  --validators content_quality,citation_format,tone_consistency \
  --voting-method weighted \
  --output ensemble_validation.json
```

### Meta-Validation

```bash
# Validate the validation results themselves
python -m marker.llm_call.cli.app meta-validate \
  --validation-file previous_validation.json \
  --meta-validators consistency,coverage,reliability \
  --output meta_validation.json
```

## Debugging Tools

### Debug Mode

```bash
# Run validation with debug output
python -m marker.llm_call.cli.app validate "Generate a Python class" \
  --validators python_syntax \
  --debug
```

### Trace Model Calls

```bash
# Trace LLM calls during validation
python -m marker.llm_call.cli.app validate "Write a simple function" \
  --validators code_completeness \
  --trace
```

### Step-by-Step Validation

```bash
# Run step-by-step validation with interactive debugging
python -m marker.llm_call.cli.app validate-step \
  --prompt "Generate a complex algorithm" \
  --validators code_completeness,python_syntax \
  --interactive
```

### Validator Inspection

```bash
# Inspect validator behavior in detail
python -m marker.llm_call.cli.app inspect-validator \
  --validator content_quality \
  --test-prompt "Write a short article about AI ethics" \
  --output validator_inspection.json
```

### Validation Replay

```bash
# Replay a previous validation with detailed logging
python -m marker.llm_call.cli.app validate-replay \
  --replay-file previous_validation.json \
  --verbose \
  --output replay_validation.json
```

## Performance Profiling

### Basic Profiling

```bash
# Run validation with profiling
python -m marker.llm_call.cli.app validate "Generate complex Python code" \
  --validators python_syntax,code_completeness \
  --profile \
  --output profile_results.json
```

### Detailed Timing Analysis

```bash
# Generate detailed timing analysis for each step
python -m marker.llm_call.cli.app validate-timed \
  --prompt "Write a research paper with citations" \
  --validators content_quality,citation_format \
  --timing-detail high \
  --output timing_analysis.json
```

### Resource Usage Monitoring

```bash
# Monitor resource usage during validation
python -m marker.llm_call.cli.app validate-monitor \
  --file batch_prompts.json \
  --validators python_syntax \
  --monitor-resources \
  --output resource_usage.json
```

### Benchmark Validators

```bash
# Run benchmark tests on multiple validators
python -m marker.llm_call.cli.app benchmark-validators \
  --validators python_syntax,code_completeness,content_quality \
  --iterations 10 \
  --output validator_benchmark.json
```

### LLM Performance Comparison

```bash
# Compare performance across different LLM models
python -m marker.llm_call.cli.app benchmark-models \
  --prompt "Generate a complex algorithm" \
  --models "gpt-4-turbo,claude-3-opus-20240229,vertex_ai/gemini-1.5-pro" \
  --validators python_syntax \
  --output model_benchmark.json
```

## Comparing Validators

### Compare Different Validation Strategies

```bash
# Create comparison test prompts
cat > compare_prompts.txt << EOL
Generate a Python function to calculate the Fibonacci sequence
Write a simple Python class for a bank account
Create a function to check if a string is a palindrome
EOL

# Run comparison with different validators
python -m marker.llm_call.cli.app compare \
  --file compare_prompts.txt \
  --validators python_syntax,code_completeness,content_quality \
  --output comparison_results.json
```

### A/B Testing Validators

```bash
# Run A/B test between different validators
python -m marker.llm_call.cli.app ab-test \
  --prompt "Generate a research paper on AI" \
  --a "content_quality(min_words=100)" \
  --b "tone_consistency" \
  --iterations 10 \
  --output ab_test_results.json
```

### Validator Evaluation Matrix

```bash
# Generate evaluation matrix for validators
python -m marker.llm_call.cli.app validator-matrix \
  --prompts-file test_prompts.json \
  --validators content_quality,citation_format,python_syntax \
  --metrics accuracy,precision,recall,f1 \
  --output validator_matrix.json
```

### Model-Validator Performance Heatmap

```bash
# Generate heatmap of model-validator performance
python -m marker.llm_call.cli.app performance-heatmap \
  --prompts-file test_prompts.json \
  --models "gpt-4-turbo,claude-3-opus-20240229,vertex_ai/gemini-1.5-pro" \
  --validators content_quality,citation_format,python_syntax \
  --output heatmap_data.json
```

## Input/Output Options

### Reading Prompt from File

```bash
# Create a prompt file
echo "Generate a detailed weather forecast for New York City" > prompt.txt

# Read prompt from file
python -m marker.llm_call.cli.app validate --file prompt.txt --validators content_quality
```

### Using JSON Response Format

```bash
# Validate with JSON response format
python -m marker.llm_call.cli.app validate "Generate user profile data" \
  --validators json_structure \
  --response-format json
```

### Multiple Output Formats

```bash
# Generate validation results in multiple formats
python -m marker.llm_call.cli.app validate "Generate technical documentation" \
  --validators content_quality \
  --output-formats json,yaml,html,markdown \
  --output validation_results
```

### Specifying a Schema

```bash
# Create a JSON schema file
cat > user_schema.json << EOL
{
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "age": {"type": "integer", "minimum": 0},
    "email": {"type": "string", "format": "email"}
  },
  "required": ["name", "age", "email"]
}
EOL

# Validate against schema
python -m marker.llm_call.cli.app validate "Generate a user profile" \
  --validators "json_structure(schema_file='user_schema.json')" \
  --response-format json
```

### Redirecting Output

```bash
# Save output to file
python -m marker.llm_call.cli.app validate "Generate Python code" \
  --validators python_syntax \
  > validation_output.txt 2> validation_errors.txt
```

## Environment Configuration

### Setting Up Environment Variables

```bash
# Create environment file
cat > .env << EOL
PYTHONPATH=/home/graham/workspace/experiments/marker
LITELLM_DEFAULT_MODEL=vertex_ai/gemini-1.5-pro
LITELLM_JUDGE_MODEL=claude-3-opus-20240229
LITELLM_API_BASE=https://api.organization.com/v1
LITELLM_API_KEY=sk_...
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=password
EOL

# Load environment and run
python -m marker.llm_call.cli.app env-setup --env-file .env
python -m marker.llm_call.cli.app validate "Generate code" --validators python_syntax
```

### Model Configuration

```bash
# Create model configuration file
cat > models_config.yaml << EOL
default: vertex_ai/gemini-1.5-pro
models:
  gpt-4-turbo:
    provider: openai
    temperature: 0.2
  claude-3-opus-20240229:
    provider: anthropic
    temperature: 0.1
  vertex_ai/gemini-1.5-pro:
    provider: google
    temperature: 0.3
EOL

# Use model configuration
python -m marker.llm_call.cli.app validate "Generate Python code" \
  --model-config models_config.yaml \
  --validators python_syntax
```

### API Key Management

```bash
# Set up API keys
python -m marker.llm_call.cli.app api-keys \
  --add openai sk_... \
  --add anthropic sk_... \
  --add google key_...

# Use stored API keys
python -m marker.llm_call.cli.app validate "Generate code" \
  --validators python_syntax \
  --use-stored-keys
```

### Proxy Configuration

```bash
# Configure and use proxy settings
python -m marker.llm_call.cli.app configure-proxy \
  --http-proxy http://proxy.example.com:8080 \
  --https-proxy https://proxy.example.com:8443

# Run validation through proxy
python -m marker.llm_call.cli.app validate "Generate code" \
  --validators python_syntax \
  --use-proxy
```

### Logging Configuration

```bash
# Set up logging
python -m marker.llm_call.cli.app configure-logging \
  --log-level debug \
  --log-file validation.log \
  --log-format json

# Run with configured logging
python -m marker.llm_call.cli.app validate "Generate Python code" \
  --validators python_syntax
```

## Integration Examples

### CI/CD Pipeline Integration

```bash
# Run validation as part of CI/CD
python -m marker.llm_call.cli.app ci-validate \
  --repo-path /path/to/repo \
  --commit-id abcdef123 \
  --validators python_syntax,content_quality \
  --output-format json \
  --exit-on-failure
```

### API Server Mode

```bash
# Start validation API server
python -m marker.llm_call.cli.app serve \
  --host localhost \
  --port 8000 \
  --workers 4 \
  --enable-cors

# Call the API server (example with curl)
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Generate Python code","validators":["python_syntax"]}'
```

### Webhook Integration

```bash
# Set up webhook integration
python -m marker.llm_call.cli.app configure-webhook \
  --url https://webhooks.example.com/validation \
  --auth-token token123 \
  --events validation.success,validation.failure

# Run validation with webhook notifications
python -m marker.llm_call.cli.app validate "Generate code" \
  --validators python_syntax \
  --notify-webhook
```

### Database Integration

```bash
# Configure database for validation results
python -m marker.llm_call.cli.app configure-db \
  --db-type postgres \
  --connection "postgresql://user:pass@localhost:5432/validation"

# Run validation with database storage
python -m marker.llm_call.cli.app validate "Generate Python code" \
  --validators python_syntax \
  --store-in-db
```

### Slack/Discord Notifications

```bash
# Configure messaging integration
python -m marker.llm_call.cli.app configure-messaging \
  --platform slack \
  --webhook-url https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX

# Run validation with messaging notifications
python -m marker.llm_call.cli.app validate "Generate code" \
  --validators python_syntax \
  --notify-on-failure
```

## Additional Examples

### List Available Validators

```bash
# List all available validators
python -m marker.llm_call.cli.app list-validators
```

### Get Validator Details

```bash
# Get details about a specific validator
python -m marker.llm_call.cli.app describe-validator python_syntax
```

### Validator Categories

```bash
# List validators by category
python -m marker.llm_call.cli.app list-validator-categories
```

### Export Validator Documentation

```bash
# Export full validator documentation
python -m marker.llm_call.cli.app export-validator-docs \
  --format markdown \
  --output validator_docs.md
```

### Custom Configuration File

```bash
# Create a config file
cat > validation_config.yaml << EOL
model: "vertex_ai/gemini-1.5-pro"
validators:
  - name: "content_quality"
    params:
      min_words: 100
      check_grammar: true
  - name: "tone_consistency"
max_retries: 2
debug: true
EOL

# Use the config file
python -m marker.llm_call.cli.app validate "Write a technical article" --config validation_config.yaml
```

### Custom Validation Strategy

```bash
# Create a validation strategy file
cat > custom_strategy.py << EOL
from marker.llm_call.core.validation import ValidationStrategy

class TechnicalContentStrategy(ValidationStrategy):
    def __init__(self):
        self.validators = [
            "content_quality(min_words=200)",
            "tone_consistency",
            "citation_format"
        ]
    
    def get_validators(self):
        return self.validators
EOL

# Use the custom strategy
python -m marker.llm_call.cli.app validate "Write a research paper" \
  --strategy custom_strategy.TechnicalContentStrategy
```

### Cached Validation

```bash
# Enable caching for validation
python -m marker.llm_call.cli.app validate "Generate Python code" \
  --validators python_syntax \
  --cache \
  --cache-ttl 3600
```

### Batch Processing from Queue

```bash
# Process validation requests from message queue
python -m marker.llm_call.cli.app queue-processor \
  --queue-type rabbitmq \
  --queue-url amqp://guest:guest@localhost:5672/ \
  --queue-name validation_requests \
  --workers 4 \
  --continuous
```