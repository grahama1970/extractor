# Agent Self-Learning Analysis

## What Already Exists

### 1. Annotation Learning System (`core/learning/`)
- **AnnotationLearner**: Learns from human PDF annotations
- **Rule Creation**: Creates rules from patterns like "not_section_header"
- **Rule Application**: Can apply learned rules to future extractions

### 2. Gold Standard Infrastructure (`gold_standards/`)
- Human-validated extraction results
- Ground truth for testing accuracy
- But NOT used for continuous learning

### 3. Validation Tracking
- Processors add validation metadata to blocks
- Confidence scores on decisions
- But NO feedback loop to improve

## What's Missing: Active Learning Loop

The agent should be continuously learning, not just applying static rules:

```python
class SelfLearningExtractor:
    def __init__(self):
        self.extraction_history = []
        self.confidence_threshold = 0.8
        self.learning_buffer = []
        
    async def extract_with_learning(self, pdf_path):
        # 1. Extract with current knowledge
        result = await extract_to_unified_json(pdf_path)
        
        # 2. Identify low-confidence decisions
        uncertain_blocks = self._find_uncertain_blocks(result)
        
        # 3. Log for human review if needed
        if uncertain_blocks:
            self._queue_for_review(pdf_path, uncertain_blocks)
        
        # 4. Apply previously learned patterns
        result = self._apply_learned_patterns(result)
        
        # 5. Track for pattern mining
        self.extraction_history.append({
            'pdf': pdf_path,
            'decisions': self._extract_decisions(result),
            'timestamp': datetime.now()
        })
        
        # 6. Mine patterns periodically
        if len(self.extraction_history) % 100 == 0:
            new_patterns = self._mine_patterns()
            self._update_processors(new_patterns)
        
        return result
```

## Immediate Improvements

### 1. Confidence-Based Learning Queue
```python
# In SectionHeaderProcessor
if text.endswith(','):
    # Don't just log - queue for learning
    self.learning_queue.add({
        'text': text,
        'decision': 'rejected_header',
        'confidence': 0.95,
        'reason': 'ends_with_comma'
    })
```

### 2. Pattern Mining from History
```python
def mine_header_patterns(extraction_history):
    # Find patterns in rejected headers
    rejected_headers = [
        h for h in extraction_history 
        if h['decision'] == 'rejected_header'
    ]
    
    # Cluster by features
    patterns = cluster_by_features(rejected_headers, [
        'ends_with_punctuation',
        'word_count',
        'starts_with_lowercase',
        'contains_assignment'
    ])
    
    # Generate new rules
    return patterns_to_rules(patterns)
```

### 3. Active Learning Interface
```python
class ActiveLearningUI:
    """Simple CLI for human feedback on uncertain cases"""
    
    def review_uncertain_blocks(self):
        for block in self.uncertain_queue:
            print(f"\nText: {block['text']}")
            print(f"Current: {block['classification']}")
            print(f"Confidence: {block['confidence']}")
            
            correct = input("Correct? (y/n/skip): ")
            if correct == 'n':
                new_class = input("Should be: ")
                self.record_correction(block, new_class)
```

## Why This Matters

1. **No Manual Rule Writing**: Agent learns patterns automatically
2. **Continuous Improvement**: Gets better with each document
3. **Domain Adaptation**: Learns document-specific patterns
4. **Confidence Tracking**: Knows when to ask for help

## Implementation Priority

### Phase 1: Track Decisions (1 day)
- Log all classification decisions with confidence
- Store in SQLite/JSON for analysis

### Phase 2: Pattern Mining (2 days)
- Mine common patterns from decisions
- Generate candidate rules automatically

### Phase 3: Active Learning (1 day)
- Queue low-confidence cases
- Simple review interface
- Update rules from feedback

### Phase 4: Self-Updating (1 week)
- Automatically update processors
- A/B test new patterns
- Track improvement metrics

## The Missing Link

Your current system has the infrastructure but lacks the CONNECTION:
- Annotations → Rules ✓ (exists)
- Rules → Processors ✓ (exists)
- **Extractions → Learning → Rules** ✗ (MISSING)

The agent should be learning from EVERY extraction, not just annotated PDFs.