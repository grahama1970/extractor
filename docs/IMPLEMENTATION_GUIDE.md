# Implementation Guide: Building the Production PDF Extractor

## Quick Start

This guide shows how to implement the production architecture step by step.

## Project Structure

```
extractor/
├── src/
│   ├── core/
│   │   ├── streaming/          # jq-based stream processing
│   │   ├── workers/            # Deterministic Python workers
│   │   ├── agents/             # Semantic sub-agents
│   │   └── orchestration/      # Task list management
│   ├── cli.py                  # Main CLI interface
│   └── pipeline.py             # Core pipeline logic
├── configs/
│   ├── task_templates/         # Reusable task list templates
│   └── agent_prompts/          # Sub-agent configurations
└── tests/
    ├── unit/                   # Component tests
    └── integration/            # Pipeline tests
```

## Step 1: Build the Streaming Discovery Engine

```python
# src/core/streaming/discovery.py

class JqStreamingEngine:
    """Core engine for memory-efficient document processing."""
    
    def __init__(self):
        self.jq_patterns = {
            "headers": '.[] | select(.block_type == "SectionHeader")',
            "tables": '.[] | select(.block_type == "Table")',
            "images": '.[] | select(.block_type == "Image")'
        }
    
    def discover_elements(self, json_path: Path, element_type: str) -> List[Dict]:
        """
        Discover elements without loading file into memory.
        """
        pattern = self.jq_patterns[element_type]
        cmd = ["jq", "-c", pattern, str(json_path)]
        
        elements = []
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True) as proc:
            for line in proc.stdout:
                elements.append(json.loads(line))
        
        return elements
    
    def apply_atomic_fixes(self, json_path: Path, fixes: List[Dict]) -> Path:
        """
        Apply all fixes in a single atomic operation.
        """
        jq_filter = self._build_fix_filter(fixes)
        output_path = json_path.with_suffix('.fixed.json')
        
        cmd = ["jq", jq_filter, str(json_path)]
        with open(output_path, 'w') as f:
            subprocess.run(cmd, stdout=f, check=True)
        
        # Atomic replace
        output_path.replace(json_path)
        return json_path
```

## Step 2: Create Deterministic Workers

```python
# src/core/workers/text_cleaner.py

class TextCleanerWorker:
    """Deterministic text cleaning operations."""
    
    def __init__(self):
        self.ligature_map = {
            'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff',
            'ﬃ': 'ffi', 'ﬄ': 'ffl'
        }
        self._hyphen_pattern = re.compile(r'(\w+)-\n(\w+)')
    
    async def clean_section(self, section: Dict) -> Dict:
        """Clean all text in a section."""
        for block in section.get('content', []):
            if block.get('type') == 'Text':
                block['text'] = self._clean_text(block['text'])
        return section
    
    def _clean_text(self, text: str) -> str:
        """Apply deterministic text cleaning rules."""
        if not text:
            return text
        
        # Fix encoding
        text = ftfy.fix_text(text)
        
        # Replace ligatures
        for lig, replacement in self.ligature_map.items():
            text = text.replace(lig, replacement)
        
        # Fix hyphenation
        text = self._hyphen_pattern.sub(r'\1\2', text)
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        return text
```

## Step 3: Implement Semantic Sub-Agents

```python
# src/core/agents/image_describer.py

class ImageDescriberAgent:
    """
    Multi-modal agent for semantic image description.
    This is where true AI reasoning happens.
    """
    
    def __init__(self, model="claude-3-opus"):
        self.model = model
        self.client = AsyncAnthropic()
    
    async def describe_image(self, image_data: Dict, context: str) -> str:
        """
        Generate semantic description of image based on context.
        """
        # Build multi-modal prompt
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""Analyze this image in the context of the surrounding text.
                        
Context: {context[:500]}

Provide a concise, informative description that explains what the image shows 
and why it's relevant to the document."""
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data.get('base64', '')
                        }
                    }
                ]
            }
        ]
        
        # Get semantic description from multi-modal model
        response = await self.client.messages.create(
            model=self.model,
            messages=messages,
            max_tokens=200
        )
        
        return response.content[0].text
```

## Step 4: Build the Task Orchestrator

```python
# src/core/orchestration/task_executor.py

class TaskOrchestrator:
    """Execute task lists with full production features."""
    
    def __init__(self):
        self.engines = {
            "jq": JqStreamingEngine(),
            "python": WorkerRegistry(),
            "agent": AgentRegistry()
        }
        self.checkpoint_manager = CheckpointManager()
    
    async def execute_pipeline(self, task_list: Dict, resume_from: str = None):
        """Execute complete pipeline with resume capability."""
        
        # Find starting point
        start_phase = self._find_resume_point(task_list, resume_from)
        
        for phase in task_list['phases'][start_phase:]:
            logger.info(f"Executing phase: {phase['phase']}")
            
            try:
                # Execute all tasks in phase
                for task in phase['tasks']:
                    result = await self._execute_task(task)
                    self.checkpoint_manager.save(f"{phase['phase']}_{task['id']}", result)
                
            except Exception as e:
                logger.error(f"Phase {phase['phase']} failed: {e}")
                raise PipelineError(f"Failed at {phase['phase']}", resume_point=phase['phase'])
    
    async def _execute_task(self, task: Dict) -> Any:
        """Route task to appropriate engine."""
        engine = self.engines[task['tool']]
        
        if task['tool'] == 'jq':
            return engine.execute_jq_task(task)
        elif task['tool'] == 'python':
            worker = engine.get_worker(task['worker'])
            return await worker.execute(task)
        elif task['tool'] == 'agent':
            agent = engine.get_agent(task['agent'])
            return await agent.execute(task)
```

## Step 5: Create the CLI Interface

```python
# src/cli.py

app = typer.Typer(help="Production PDF Extraction Pipeline")

@app.command()
def extract(
    input_file: Path = typer.Argument(..., help="Input JSON from marker-pdf"),
    output_dir: Path = typer.Option("./output", "-o", "--output"),
    config: Path = typer.Option(None, "-c", "--config", help="Task list config"),
    concurrency: int = typer.Option(4, "--concurrency", help="Parallel sections"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan only"),
    resume: str = typer.Option(None, "--resume", help="Resume from phase"),
    formats: List[str] = typer.Option(["structured"], "-f", "--format")
):
    """
    Extract and enhance PDF content with production pipeline.
    
    Examples:
        # Basic extraction
        pdf-extract document.json
        
        # Custom configuration
        pdf-extract document.json -c custom_tasks.json
        
        # Dry run to see plan
        pdf-extract document.json --dry-run
        
        # Resume after failure
        pdf-extract document.json --resume=enhancement
    """
    if dry_run:
        plan = generate_execution_plan(input_file, config)
        console.print(plan)
        return
    
    # Run pipeline
    asyncio.run(run_pipeline(
        input_file=input_file,
        output_dir=output_dir,
        config=config,
        concurrency=concurrency,
        resume_from=resume,
        export_formats=formats
    ))

@app.command()
def validate(
    input_file: Path = typer.Argument(..., help="JSON file to validate"),
    schema: str = typer.Option("marker", help="Schema to validate against")
):
    """Validate input file format."""
    validator = SchemaValidator(schema)
    issues = validator.validate(input_file)
    
    if issues:
        console.print("[red]Validation failed:[/red]")
        for issue in issues:
            console.print(f"  - {issue}")
        raise typer.Exit(1)
    else:
        console.print("[green]✓ Valid[/green]")
```

## Step 6: Configure Task Templates

```yaml
# configs/task_templates/standard_extraction.yaml

pipeline: pdf_extraction_standard
version: 1.0

phases:
  - name: discovery
    parallel: false
    tasks:
      - id: find_all_elements
        tool: jq
        operation: discover_elements
        params:
          types: [headers, tables, images, text]
        output: discoveries.json

  - name: quick_fixes
    parallel: false  
    tasks:
      - id: fix_obvious_headers
        tool: jq
        operation: apply_atomic_fixes
        input: discoveries.json
        rules:
          - headers_ending_with_comma: convert_to_text
          - headers_starting_with_conjunction: convert_to_text
        output: stage1.json

  - name: enhancement
    parallel: true
    concurrency: 4
    tasks:
      - id: partition_document
        tool: python
        worker: document_partitioner
        input: stage1.json
        output: sections.json
        
      - id: enhance_sections
        tool: agent
        agent: section_enhancer
        input: sections.json
        operations:
          - clean_text
          - merge_tables
          - describe_images
          - merge_paragraphs
        output: enhanced.json

  - name: export
    parallel: true
    tasks:
      - id: export_structured
        tool: python
        worker: structured_exporter
        input: enhanced.json
        format: structured_json
        
      - id: export_rag
        tool: python
        worker: rag_exporter
        input: enhanced.json
        format: semantic_chunks
```

## Step 7: Write Tests

```python
# tests/integration/test_pipeline.py

class TestProductionPipeline:
    
    @pytest.fixture
    def sample_document(self):
        """Create test document with known issues."""
        return {
            "blocks": [
                {"type": "Header", "text": "Introduction"},
                {"type": "Text", "text": "This is the intro."},
                {"type": "Header", "text": "For more details,"},  # Should convert
                {"type": "Text", "text": "see the appendix."},
                {"type": "Table", "text": "Col1", "cells": [["A"]]},
                {"type": "Table", "text": "Col1 (continued)", "cells": [["B"]]},  # Should merge
                {"type": "Image", "base64": "..."},  # Needs description
            ]
        }
    
    async def test_full_pipeline(self, sample_document, tmp_path):
        """Test complete extraction pipeline."""
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(sample_document))
        
        # Run pipeline
        result = await run_pipeline(
            input_file=input_file,
            output_dir=tmp_path / "output",
            concurrency=2
        )
        
        # Verify results
        output = json.loads((tmp_path / "output" / "final.json").read_text())
        
        # Check header was converted
        assert not any(b['text'] == "For more details," and b['type'] == "Header" 
                      for b in output['blocks'])
        
        # Check tables were merged
        table_blocks = [b for b in output['blocks'] if b['type'] == 'Table']
        assert len(table_blocks) == 1
        assert table_blocks[0]['cells'] == [["A"], ["B"]]
        
        # Check image has description
        image_blocks = [b for b in output['blocks'] if b['type'] == 'Image']
        assert image_blocks[0].get('description') is not None
```

## Running in Production

### Local Development
```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Process a document
pdf-extract sample.json -o output/

# Dry run to see plan
pdf-extract sample.json --dry-run
```

### Docker Deployment
```bash
# Build image
docker build -t pdf-extractor:latest .

# Run with volume mount
docker run -v $(pwd)/data:/data pdf-extractor:latest \
  extract /data/document.json -o /data/output
```

### Kubernetes Job
```bash
# Create configmap with task list
kubectl create configmap extraction-tasks --from-file=configs/

# Run job
kubectl apply -f k8s/extraction-job.yaml

# Check logs
kubectl logs -f job/pdf-extraction
```

## Performance Tuning

### 1. **Concurrency Settings**
```python
# For CPU-bound operations (text cleaning, table merging)
WORKER_CONCURRENCY = os.cpu_count()

# For I/O-bound operations (LLM calls)
AGENT_CONCURRENCY = 4  # Limit to avoid rate limits

# For memory-constrained environments
MAX_SECTIONS_IN_MEMORY = 100  # Process in batches
```

### 2. **Caching Strategy**
```python
class ResultCache:
    """Cache expensive operations."""
    
    def __init__(self, ttl=3600):
        self.cache = TTLCache(maxsize=1000, ttl=ttl)
    
    @cached(cache=cache)
    async def describe_image(self, image_hash: str, context: str) -> str:
        """Cache image descriptions to avoid duplicate LLM calls."""
        return await self.agent.describe_image(image_hash, context)
```

### 3. **Resource Limits**
```python
# Prevent memory explosions
resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))  # 4GB

# Timeout long operations
async def with_timeout(coro, timeout=300):
    return await asyncio.wait_for(coro, timeout=timeout)
```

## Monitoring

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

docs_processed = Counter('pdf_extraction_documents_total', 'Total documents processed')
processing_time = Histogram('pdf_extraction_duration_seconds', 'Processing time', ['phase'])
active_sections = Gauge('pdf_extraction_active_sections', 'Sections being processed')

# Log aggregation
import structlog

logger = structlog.get_logger()
logger = logger.bind(service="pdf-extractor", version="1.0")
```

## Conclusion

This implementation guide provides a complete, production-ready PDF extraction system that:

1. **Scales** to any document size through streaming
2. **Recovers** from failures with checkpointing
3. **Performs** through intelligent work distribution
4. **Maintains** quality through specialized components
5. **Operates** reliably in production environments

The key is the separation of concerns:
- jq for what it does best (streaming JSON operations)
- Python for deterministic transformations
- LLMs for semantic understanding
- Task lists for orchestration clarity

This is engineering discipline applied to AI systems.