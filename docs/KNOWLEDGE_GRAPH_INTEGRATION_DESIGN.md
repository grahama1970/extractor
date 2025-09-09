# Knowledge Graph Integration for PDF Extraction Sub-Agents

## Overview

This document outlines how the Figure Describer, Annotation Learner, and Gold Standard Manager sub-agents collaborate through the Knowledge Architect to build a comprehensive learning system for PDF extraction.

## Architecture

```
                    Knowledge Architect (ArangoDB)
                           |
          +----------------+----------------+
          |                |                |
    Figure Describer  Annotation Learner  Gold Standard Manager
          |                |                |
    Visual Analysis   Pattern Learning   Quality Validation
```

## Core Collections Design

### 1. PDF Analysis Collections

```json
// pdf_documents
{
  "_key": "doc_001_2025_07_25",
  "filename": "research_paper.pdf",
  "path": "/path/to/pdf",
  "pages": 10,
  "extraction_date": "2025-07-25",
  "overall_quality": 0.85,
  "stages_completed": ["annotation", "extraction", "validation"]
}

// pdf_blocks
{
  "_key": "block_doc001_p1_001",
  "document_id": "pdf_documents/doc_001_2025_07_25",
  "page": 1,
  "block_type": "Table",
  "bbox": [100, 200, 400, 500],
  "confidence": 0.75,
  "visual_features": {
    "has_grid_lines": true,
    "is_text_like": false,
    "aspect_ratio": 2.1
  },
  "extraction_method": "marker",
  "validation_status": "needs_review"
}

// extraction_attempts
{
  "_key": "attempt_001",
  "block_id": "pdf_blocks/block_doc001_p1_001",
  "method": "camelot",
  "success": true,
  "confidence": 0.92,
  "duration_ms": 1500,
  "timestamp": "2025-07-25T10:30:00Z"
}
```

### 2. Learning Collections

```json
// annotation_patterns
{
  "_key": "pattern_merge_table",
  "pattern_type": "merge_instruction",
  "color": "yellow",
  "text_pattern": "merge|continue|split",
  "confidence": 0.89,
  "occurrences": 45,
  "learned_from": ["doc_001", "doc_002"]
}

// gold_standards
{
  "_key": "gold_doc001_stage2",
  "document_id": "pdf_documents/doc_001_2025_07_25",
  "stage": "extraction",
  "version": "1.2.0",
  "source_weights": {
    "expert_review": 1.0,
    "visual_analysis": 0.9,
    "annotation": 0.85
  },
  "blocks": {...},
  "quality_score": 0.94
}

// visual_insights
{
  "_key": "insight_table_grid",
  "insight_type": "misclassification",
  "description": "Figures with grid lines are often tables",
  "visual_signature": {
    "horizontal_lines": ">=2",
    "vertical_lines": ">=2",
    "aspect_ratio": ">1.5"
  },
  "accuracy": 0.87,
  "sample_blocks": ["block_001", "block_002"]
}
```

### 3. Edge Collections

```json
// block_relationships
{
  "_from": "pdf_blocks/block_001",
  "_to": "pdf_blocks/block_002",
  "relationship_type": "continues_from",
  "confidence": 0.9,
  "reason": "table_split_across_pages"
}

// problem_solutions
{
  "_from": "pdf_blocks/block_misclassified_001",
  "_to": "extraction_attempts/camelot_success_001",
  "relationship_type": "fixed_by",
  "improvement": 0.35,
  "key_insight": "camelot_better_for_bordered_tables"
}

// pattern_applications
{
  "_from": "annotation_patterns/pattern_merge_table",
  "_to": "gold_standards/gold_doc001_stage2",
  "relationship_type": "applied_to",
  "success": true,
  "impact": "high"
}
```

## Sub-Agent Integration Patterns

### 1. Figure Describer Integration

```python
class FigureDescriberKnowledgeIntegration:
    async def analyze_and_store(self, block, visual_analysis):
        # Store visual analysis results
        await mcp__arango_tools__upsert(
            collection="pdf_blocks",
            search=f'{{"_key": "{block.id}"}}',
            update=json.dumps({
                "visual_features": visual_analysis,
                "last_analyzed": datetime.now().isoformat()
            })
        )
        
        # Check for misclassification patterns
        if block.type == "Figure" and visual_analysis["has_grid_lines"]:
            # Search for similar misclassifications
            similar = await mcp__arango_tools__semantic_search(
                collection="visual_insights",
                query="figure with grid lines misclassified as table",
                text_field="description",
                top_k=5
            )
            
            # Create insight if pattern is new
            if not similar or similar[0]["score"] < 0.8:
                await mcp__arango_tools__insert(
                    message="New misclassification pattern detected",
                    level="INSIGHT",
                    metadata=json.dumps({
                        "pattern": "figure_with_grid_is_table",
                        "confidence": 0.85
                    })
                )
            
            # Link to existing solutions
            solutions = await mcp__arango_tools__query(
                aql="""
                FOR solution IN extraction_attempts
                    FILTER solution.method == "camelot" 
                    AND solution.success == true
                    AND solution.confidence > 0.8
                    RETURN solution
                """
            )
            
            # Create edge to best solution
            if solutions:
                await mcp__arango_tools__edge(
                    from_id=f"pdf_blocks/{block.id}",
                    to_id=solutions[0]["_id"],
                    collection="problem_solutions",
                    relationship_type="recommended_fix"
                )
```

### 2. Annotation Learner Integration

```python
class AnnotationLearnerKnowledgeIntegration:
    async def learn_and_store_patterns(self, annotations, document_id):
        # Store annotation patterns
        for annotation in annotations:
            pattern_key = await mcp__arango_tools__upsert(
                collection="annotation_patterns",
                search=json.dumps({
                    "pattern_type": annotation["type"],
                    "color": annotation["color"]
                }),
                update=json.dumps({
                    "occurrences": {"$inc": 1},
                    "last_seen": datetime.now().isoformat(),
                    "text_examples": {"$push": annotation["text"]}
                })
            )
            
            # Link pattern to document
            await mcp__arango_tools__edge(
                from_id=pattern_key,
                to_id=f"pdf_documents/{document_id}",
                collection="pattern_applications",
                relationship_type="found_in"
            )
        
        # Find related patterns using BM25
        related = await mcp__arango_tools__query(
            aql="""
            FOR pattern IN annotation_patterns
                SEARCH ANALYZER(
                    pattern.text_pattern IN TOKENS(@search_text, 'text_en'),
                    'text_en'
                )
                SORT BM25(pattern) DESC
                LIMIT 10
                RETURN pattern
            """,
            bind_vars=json.dumps({
                "search_text": " ".join([a["text"] for a in annotations])
            })
        )
        
        # Build pattern relationships
        for related_pattern in related:
            await mcp__arango_tools__build_similarity_graph(
                collection="annotation_patterns",
                text_field="text_pattern",
                edge_collection="similar_patterns",
                threshold=0.7
            )
```

### 3. Gold Standard Manager Integration

```python
class GoldStandardKnowledgeIntegration:
    async def create_and_link_gold_standard(self, gold_standard):
        # Store gold standard
        gold_key = await mcp__arango_tools__insert(
            message=f"Gold standard created for {gold_standard['document_id']}",
            level="INFO",
            metadata=json.dumps(gold_standard)
        )
        
        # Multi-hop traversal to find successful patterns
        successful_patterns = await mcp__arango_tools__query(
            aql="""
            // Start from this document
            LET doc = DOCUMENT(@doc_id)
            
            // Find all blocks that were successfully extracted
            LET successful_blocks = (
                FOR block IN pdf_blocks
                    FILTER block.document_id == doc._id
                    FILTER block.confidence > 0.8
                    
                    // Find extraction methods that worked
                    LET methods = (
                        FOR v, e IN 1..1 OUTBOUND block problem_solutions
                            FILTER e.improvement > 0.2
                            RETURN {
                                method: v.method,
                                improvement: e.improvement
                            }
                    )
                    
                    RETURN {
                        block: block,
                        successful_methods: methods
                    }
            )
            
            // Find similar documents that had similar blocks
            LET similar_docs = (
                FOR pattern IN successful_blocks
                    // Find blocks with similar visual features
                    FOR similar IN pdf_blocks
                        FILTER similar._id != pattern.block._id
                        FILTER similar.visual_features.has_grid_lines == 
                               pattern.block.visual_features.has_grid_lines
                        FILTER ABS(similar.visual_features.aspect_ratio - 
                               pattern.block.visual_features.aspect_ratio) < 0.2
                        
                        // Get their gold standards
                        LET gold = (
                            FOR g IN gold_standards
                                FILTER g.document_id == similar.document_id
                                RETURN g
                        )
                        
                        RETURN DISTINCT {
                            document: similar.document_id,
                            gold_standards: gold,
                            similarity_score: 0.85
                        }
            )
            
            RETURN {
                current_doc: doc,
                successful_patterns: successful_blocks,
                similar_successful_docs: similar_docs
            }
            """,
            bind_vars=json.dumps({
                "doc_id": f"pdf_documents/{gold_standard['document_id']}"
            })
        )
        
        # Track gold standard evolution
        await mcp__arango_tools__track_pattern_evolution(
            pattern_type="gold_standard_quality",
            window="daily"
        )
```

## Multi-Hop Graph Traversal Patterns

### 1. Find Related Solutions

```python
async def find_related_solutions_multi_hop(block_id, max_hops=3):
    """
    Find solutions through multiple relationship types:
    1. Direct fixes for this block
    2. Fixes for similar blocks
    3. Fixes for blocks with similar problems
    """
    
    query = """
    LET start_block = DOCUMENT(@block_id)
    
    // Direct solutions (1 hop)
    LET direct_solutions = (
        FOR v, e IN 1..1 OUTBOUND start_block problem_solutions
            RETURN {solution: v, relationship: e, hops: 1}
    )
    
    // Similar block solutions (2 hops)
    LET similar_block_solutions = (
        FOR similar IN pdf_blocks
            FILTER similar._id != start_block._id
            // Similar visual features
            FILTER similar.visual_features.has_grid_lines == 
                   start_block.visual_features.has_grid_lines
            // Find their solutions
            FOR v, e IN 1..1 OUTBOUND similar problem_solutions
                RETURN {solution: v, relationship: e, hops: 2, via: similar._id}
    )
    
    // Pattern-based solutions (3 hops)
    LET pattern_solutions = (
        // Find patterns this block matches
        FOR pattern IN annotation_patterns
            // Find other blocks that match this pattern
            FOR v1, e1 IN 1..1 INBOUND pattern pattern_applications
                FILTER v1._id != start_block._id
                // Find their solutions
                FOR v2, e2 IN 1..1 OUTBOUND v1 problem_solutions
                    RETURN {
                        solution: v2, 
                        relationship: e2, 
                        hops: 3, 
                        via_pattern: pattern._id,
                        via_block: v1._id
                    }
    )
    
    // Combine and rank by confidence and hop distance
    LET all_solutions = UNION_DISTINCT(
        direct_solutions,
        similar_block_solutions,
        pattern_solutions
    )
    
    FOR sol IN all_solutions
        SORT sol.solution.confidence DESC, sol.hops ASC
        LIMIT 10
        RETURN sol
    """
    
    return await mcp__arango_tools__query(
        aql=query,
        bind_vars=json.dumps({"block_id": block_id})
    )
```

### 2. BM25 + Graph Traversal Hybrid

```python
async def hybrid_search_solutions(problem_description, start_node=None):
    """
    Combine BM25 text search with graph traversal for best results
    """
    
    # First, use BM25 to find relevant nodes
    text_results = await mcp__arango_tools__semantic_search(
        collection="extraction_attempts",
        query=problem_description,
        text_field="description",
        top_k=20
    )
    
    # Then traverse from these nodes
    query = """
    LET text_matches = @text_results
    
    // For each text match, explore its graph neighborhood
    FOR match IN text_matches
        LET node = DOCUMENT(match._id)
        
        // Find related successful patterns
        LET patterns = (
            FOR v, e, p IN 1..3 ANY node 
                problem_solutions, 
                pattern_applications,
                block_relationships
                OPTIONS {uniqueVertices: 'global'}
                FILTER v.success == true OR v.confidence > 0.8
                RETURN {
                    node: v,
                    path: p,
                    distance: LENGTH(p.edges),
                    combined_confidence: PRODUCT(
                        FOR edge IN p.edges RETURN edge.confidence DEFAULT 1.0
                    )
                }
        )
        
        // Combine text relevance with graph relevance
        FOR p IN patterns
            LET final_score = (
                0.4 * match.score +  // BM25 score
                0.3 * p.combined_confidence +  // Path confidence
                0.3 * (1.0 / (1.0 + p.distance))  // Distance penalty
            )
            SORT final_score DESC
            RETURN {
                solution: p.node,
                text_relevance: match.score,
                graph_confidence: p.combined_confidence,
                path_length: p.distance,
                final_score: final_score,
                path: p.path
            }
    """
    
    return await mcp__arango_tools__query(
        aql=query,
        bind_vars=json.dumps({"text_results": text_results})
    )
```

## State Management Between Sub-Agents

### 1. Shared Context Store

```python
class SubAgentStateManager:
    async def save_state(self, agent_name, document_id, state):
        """Save agent state for coordination"""
        await mcp__arango_tools__upsert(
            collection="agent_states",
            search=json.dumps({
                "agent": agent_name,
                "document_id": document_id
            }),
            update=json.dumps({
                "state": state,
                "timestamp": datetime.now().isoformat()
            })
        )
    
    async def get_state(self, agent_name, document_id):
        """Retrieve agent state"""
        result = await mcp__arango_tools__query(
            aql="""
            FOR state IN agent_states
                FILTER state.agent == @agent
                AND state.document_id == @doc_id
                SORT state.timestamp DESC
                LIMIT 1
                RETURN state
            """,
            bind_vars=json.dumps({
                "agent": agent_name,
                "doc_id": document_id
            })
        )
        return result[0] if result else None
    
    async def coordinate_agents(self, document_id):
        """Coordinate multiple agents working on same document"""
        # Get all agent states
        states = await mcp__arango_tools__query(
            aql="""
            FOR state IN agent_states
                FILTER state.document_id == @doc_id
                RETURN {
                    agent: state.agent,
                    state: state.state,
                    timestamp: state.timestamp
                }
            """,
            bind_vars=json.dumps({"doc_id": document_id})
        )
        
        # Determine next actions based on states
        coordination_plan = {
            "next_actions": [],
            "dependencies": {},
            "conflicts": []
        }
        
        # Example coordination logic
        annotation_state = next((s for s in states if s["agent"] == "annotation_learner"), None)
        figure_state = next((s for s in states if s["agent"] == "figure_describer"), None)
        
        if annotation_state and annotation_state["state"]["patterns_found"]:
            coordination_plan["next_actions"].append({
                "agent": "gold_standard_manager",
                "action": "incorporate_annotation_patterns",
                "priority": "high"
            })
        
        if figure_state and figure_state["state"]["misclassifications_found"]:
            coordination_plan["next_actions"].append({
                "agent": "gold_standard_manager",
                "action": "validate_figure_corrections",
                "priority": "high"
            })
        
        return coordination_plan
```

### 2. Event-Driven Updates

```python
async def publish_agent_event(agent_name, event_type, data):
    """Publish events that other agents can react to"""
    event_id = await mcp__arango_tools__insert(
        message=f"Agent event: {agent_name} - {event_type}",
        level="EVENT",
        metadata=json.dumps({
            "agent": agent_name,
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
    )
    
    # Create edges to affected entities
    if "block_id" in data:
        await mcp__arango_tools__edge(
            from_id=event_id,
            to_id=data["block_id"],
            collection="event_impacts",
            relationship_type="affects"
        )
    
    # Trigger dependent agent actions
    await trigger_dependent_agents(agent_name, event_type, data)

async def subscribe_to_events(agent_name, event_patterns):
    """Subscribe agent to specific event patterns"""
    await mcp__arango_tools__upsert(
        collection="agent_subscriptions",
        search=json.dumps({"agent": agent_name}),
        update=json.dumps({
            "event_patterns": event_patterns,
            "active": True
        })
    )
```

## Benefits of This Architecture

1. **Persistent Learning**: Every extraction improves future performance
2. **Cross-Document Intelligence**: Learn from patterns across all PDFs
3. **Multi-Path Solutions**: Find solutions through various relationship paths
4. **Hybrid Search**: Combine text similarity with graph relationships
5. **Agent Coordination**: Sub-agents build on each other's work
6. **Audit Trail**: Complete history of decisions and improvements

## Example Workflow

```python
# 1. Annotation Learner finds merge pattern
await annotation_learner.analyze_and_store_patterns(pdf_annotations)

# 2. Figure Describer detects misclassified table
visual_analysis = await figure_describer.analyze_block(suspicious_block)
await figure_describer.store_insights(visual_analysis)

# 3. Gold Standard Manager finds solution through multi-hop
solutions = await find_related_solutions_multi_hop(
    block_id=suspicious_block.id,
    max_hops=3
)

# 4. Apply best solution and track outcome
best_solution = solutions[0]
result = await apply_extraction_method(best_solution["method"])
await mcp__arango_tools__track_solution_outcome(
    solution_id=best_solution["_id"],
    outcome="success" if result.confidence > 0.8 else "partial",
    key_reason="Visual analysis correctly identified table",
    category="misclassification_fix"
)

# 5. Update gold standard with learning
await gold_standard_manager.incorporate_learning(
    document_id=document.id,
    new_insights=[visual_analysis, annotation_patterns],
    successful_methods=[best_solution]
)
```

This architecture creates a self-improving system where each sub-agent contributes to a growing knowledge graph that benefits all future PDF extractions.