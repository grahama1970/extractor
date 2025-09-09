# PDF Sub-Agent Pipeline Architecture - Visual Guide

## Overview

This document provides clear visual representations of how the PDF sub-agent pipeline works, showing the transformation from the current code-based approach to the new sub-agent orchestrated system.

## 1. Current Architecture vs Sub-Agent Architecture

```mermaid
graph TB
    subgraph "Current Code-Based Pipeline"
        PDF1[PDF Input] --> AE1[Annotation Extractor]
        AE1 --> MP1[Marker PDF]
        MP1 --> CP1[Code Processors]
        CP1 --> |"Pattern Matching"| SH1[SectionHeader Processor]
        CP1 --> |"Rules"| TP1[Table Processor]
        CP1 --> |"Hardcoded"| ST1[Stage3 Transformer]
        ST1 --> VAL1[Validation: 77.9%]
        VAL1 --> |"FAIL"| OUT1[Output]
    end
    
    subgraph "New Sub-Agent Pipeline"
        PDF2[PDF Input] --> SA1[pdf_annotation_extractor]
        SA1 --> |"Clean PDF"| SA2[marker_pdf_extractor]
        SA2 --> |"Raw Blocks"| WP[workflow_planner]
        WP --> |"Dispatch"| PD[pdf_dispatcher]
        PD --> |"Concurrent"| SAG{Sub-Agent Group}
        SAG --> SA3[pdf_section_header]
        SAG --> SA4[pdf_table_analyzer]
        SAG --> SA5[pdf_content_categorizer]
        SA3 & SA4 & SA5 --> |"Semantic Understanding"| SA6[pdf_gold_standard]
        SA6 --> VAL2[Validation: >90%]
        VAL2 --> |"PASS"| OUT2[Output]
    end
    
    style VAL1 fill:#f96,stroke:#333,stroke-width:2px
    style VAL2 fill:#9f6,stroke:#333,stroke-width:2px
```

## 2. Detailed Sub-Agent Pipeline Flow

```mermaid
flowchart TD
    Start([PDF Document]) --> Stage1{Stage 1: Annotations}
    
    subgraph "Stage 1: Annotation Processing"
        Stage1 --> AE[pdf_annotation_extractor]
        AE --> |"Extract"| ANNOT[Annotations JSON]
        AE --> |"Clean"| CLEAN[Clean PDF]
        ANNOT --> AI[pdf_annotation_interpreter]
        AI --> |"Learn"| KB1[(ArangoDB:<br/>Annotation Patterns)]
    end
    
    CLEAN --> Stage2{Stage 2: Marker}
    
    subgraph "Stage 2: Raw Extraction"
        Stage2 --> ME[marker_pdf_extractor]
        ME --> |"56 blocks"| BLOCKS[Raw Block List]
        BLOCKS --> GS1[pdf_gold_standard]
        GS1 --> |"Validate"| V1{90% Match?}
        V1 -->|"No"| FIX1[Log Issues]
        V1 -->|"Yes"| Stage3
    end
    
    BLOCKS --> Stage3{Stage 3: Planning}
    
    subgraph "Stage 3: Workflow Planning"
        Stage3 --> WP[workflow_planner]
        WP --> |"Analyze"| SUSP[Suspicious Blocks]
        SUSP --> PLAN[Processing Plan]
        PLAN --> PD[pdf_dispatcher]
    end
    
    PD --> Stage4{Stage 4: Concurrent}
    
    subgraph "Stage 4: Sub-Agent Processing"
        Stage4 --> |"Parallel"| AGENTS[Concurrent Sub-Agents]
        AGENTS --> SH[pdf_section_header]
        AGENTS --> TA[pdf_table_analyzer]
        AGENTS --> TM[pdf_table_merge]
        AGENTS --> CC[pdf_content_categorizer]
        
        SH --> |"Query"| KB2[(ArangoDB:<br/>Header Patterns)]
        TA --> |"Query"| KB3[(ArangoDB:<br/>Table Patterns)]
        CC --> |"Query"| KB4[(ArangoDB:<br/>Content Patterns)]
    end
    
    SH & TA & TM & CC --> Stage5{Stage 5: Organization}
    
    subgraph "Stage 5: Section Organization"
        Stage5 --> SO[Section Organizer]
        SO --> |"Build"| TREE[Section Tree]
        TREE --> GS2[pdf_gold_standard]
        GS2 --> |"Validate"| V2{90% Match?}
        V2 -->|"No"| FIX2[Iterate]
        V2 -->|"Yes"| Stage6
    end
    
    TREE --> Stage6{Stage 6: Export}
    
    subgraph "Stage 6: Output Generation"
        Stage6 --> EX[pdf_exporter]
        EX --> JSON[JSON Output]
        EX --> ARANGO[ArangoDB Graph]
        EX --> MD[Markdown]
        EX --> REPORT[Pipeline Report]
    end
```

## 3. Sub-Agent Communication Pattern

```mermaid
sequenceDiagram
    participant U as User
    participant O as Orchestrator
    participant WP as workflow_planner
    participant PD as pdf_dispatcher
    participant KA as knowledge_architect
    participant SA1 as pdf_section_header
    participant SA2 as pdf_table_analyzer
    participant SA3 as pdf_content_categorizer
    participant LLM as LLM Service
    participant DB as ArangoDB
    
    U->>O: Process PDF
    O->>WP: Analyze blocks
    WP->>DB: Query similar documents
    DB-->>WP: Historical patterns
    WP->>WP: Create processing plan
    WP->>PD: Dispatch plan
    
    par Concurrent Processing
        PD->>SA1: Validate headers
        SA1->>DB: Search header patterns
        DB-->>SA1: Similar headers
        SA1->>LLM: Semantic validation
        LLM-->>SA1: Validation result
        SA1->>DB: Store new pattern
    and
        PD->>SA2: Analyze tables
        SA2->>DB: Search table patterns
        SA2->>LLM: Table understanding
        LLM-->>SA2: Analysis result
    and
        PD->>SA3: Categorize content
        SA3->>DB: Search content patterns
        SA3->>LLM: Semantic grouping
        LLM-->>SA3: Categories
    end
    
    SA1 & SA2 & SA3->>O: Results
    O->>KA: Store learnings
    O->>U: Processed document
```

## 4. Knowledge-First Pattern Flow

```mermaid
graph LR
    subgraph "Knowledge-First Processing"
        REQ[New Request] --> CHECK{Check KB}
        CHECK -->|"Found"| CACHE[Use Cached Result]
        CHECK -->|"Not Found"| PROCESS[Process with LLM]
        PROCESS --> STORE[Store in KB]
        STORE --> RESULT[Return Result]
        CACHE --> RESULT
    end
    
    subgraph "Knowledge Base Structure"
        KB[(ArangoDB)]
        KB --> PATTERNS[Pattern Collections]
        KB --> SOLUTIONS[Solution Cache]
        KB --> GRAPH[Document Graph]
        
        PATTERNS --> HP[Header Patterns]
        PATTERNS --> TP[Table Patterns]
        PATTERNS --> CP[Content Patterns]
        
        SOLUTIONS --> HS[Header Solutions]
        SOLUTIONS --> TS[Table Solutions]
        SOLUTIONS --> CS[Content Solutions]
    end
    
    CHECK -.-> KB
    STORE -.-> KB
```

## 5. Error Handling and Recovery Flow

```mermaid
stateDiagram-v2
    [*] --> ProcessBlock
    ProcessBlock --> CheckKnowledge
    
    CheckKnowledge --> CacheHit: Pattern Found
    CheckKnowledge --> CallLLM: No Pattern
    
    CacheHit --> ValidateResult
    CallLLM --> LLMSuccess: Success
    CallLLM --> LLMError: Failure
    
    LLMError --> Retry: Retry < 3
    LLMError --> Fallback: Retry >= 3
    
    Retry --> CallLLM
    Fallback --> UseCodeProcessor
    
    LLMSuccess --> StorePattern
    StorePattern --> ValidateResult
    UseCodeProcessor --> ValidateResult
    
    ValidateResult --> PassValidation: >= 90%
    ValidateResult --> FailValidation: < 90%
    
    PassValidation --> [*]
    FailValidation --> ManualReview
    ManualReview --> UpdateGoldStandard
    UpdateGoldStandard --> [*]
```

## 6. Sub-Agent Types and Responsibilities

```mermaid
graph TB
    subgraph "Annotation Sub-Agents"
        A1[pdf_annotation_extractor<br/>Extract visual annotations]
        A2[pdf_annotation_interpreter<br/>Understand annotation meaning]
    end
    
    subgraph "Analysis Sub-Agents"
        B1[pdf_section_header<br/>Validate headers semantically]
        B2[pdf_table_analyzer<br/>Deep table understanding]
        B3[pdf_table_merge<br/>Merge split tables]
        B4[pdf_content_categorizer<br/>Group content semantically]
    end
    
    subgraph "Orchestration Sub-Agents"
        C1[workflow_planner<br/>Plan processing steps]
        C2[pdf_dispatcher<br/>Manage concurrency]
        C3[pdf_gold_standard<br/>Validate outputs]
    end
    
    subgraph "Utility Sub-Agents"
        D1[pdf_exporter<br/>Generate outputs]
        D2[knowledge_architect<br/>Manage patterns]
    end
    
    A1 & A2 --> B1 & B2 & B3 & B4
    C1 --> C2
    C2 --> B1 & B2 & B3 & B4
    B1 & B2 & B3 & B4 --> C3
    C3 --> D1
    D2 -.-> A1 & A2 & B1 & B2 & B3 & B4
```

## 7. Performance Optimization Strategy

```mermaid
graph TD
    subgraph "Optimization Layers"
        INPUT[PDF Input] --> CACHE{Cache Check}
        CACHE -->|"Hit 80%"| CACHED[Cached Result]
        CACHE -->|"Miss 20%"| BATCH[Batch Similar Blocks]
        
        BATCH --> PRIORITY{Priority Queue}
        PRIORITY -->|"High"| FAST[Fast LLM<br/>GPT-3.5]
        PRIORITY -->|"Medium"| BALANCED[Balanced LLM<br/>Claude Haiku]
        PRIORITY -->|"Low"| QUALITY[Quality LLM<br/>Claude Sonnet]
        
        FAST & BALANCED & QUALITY --> CONCURRENT[Concurrent Processing<br/>Max 10 threads]
        CONCURRENT --> RESULTS[Aggregated Results]
        RESULTS --> STORE[Store in Cache]
        STORE --> OUTPUT[Final Output]
        CACHED --> OUTPUT
    end
    
    subgraph "Metrics"
        M1[Response Time<br/>Target: <5s/page]
        M2[Cache Hit Rate<br/>Target: 80%]
        M3[LLM Cost<br/>Track per page]
        M4[Accuracy<br/>Target: >90%]
    end
```

## Key Architecture Decisions

1. **Knowledge-First**: Every sub-agent checks ArangoDB before making LLM calls
2. **Concurrent Processing**: Multiple sub-agents run in parallel for efficiency
3. **Semantic Understanding**: LLMs provide the semantic analysis that code cannot
4. **Learning System**: Every result is stored for future improvement
5. **Graceful Degradation**: Falls back to code processors if LLMs fail
6. **Validation Gates**: Gold standard checks at each major stage

## Implementation Priority

1. **Phase 1**: Core infrastructure (pdf_base, pdf_dispatcher)
2. **Phase 2**: Annotation agents (already partially exists)
3. **Phase 3**: Analysis agents (critical for 90% goal)
4. **Phase 4**: Validation agent (ensures quality)
5. **Phase 5**: Integration layer
6. **Phase 6**: Testing and optimization

This architecture enables the semantic understanding required to achieve >90% validation while maintaining performance through caching and concurrent processing.