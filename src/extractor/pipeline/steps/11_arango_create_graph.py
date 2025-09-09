#!/usr/bin/env python3
"""
Pipeline Stage 11: ArangoDB Graph Creation with FAISS

Purpose: Create weighted graph relationships between PDF objects stored in ArangoDB
using FAISS for efficient similarity search and section hierarchy for structural weighting.

This stage runs AFTER documents are loaded into ArangoDB and creates edges based on:
1. Semantic similarity (using FAISS for efficient k-NN search)
2. Section hierarchy relationships
3. Combined weighted scores
"""

import os
import sys
import json
import asyncio
import math
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional, cast
from datetime import datetime, timezone
import numpy as np
from numpy.typing import NDArray
from textwrap import dedent

# Third-party
from loguru import logger
try:
    try:
        import typer
        _HAS_TYPER = True
    except Exception:
        _HAS_TYPER = False
        class _TyperShim:
            def __init__(self,*a,**k): pass
            def command(self,*a,**k): return lambda f: f
            def __call__(self,*a,**k): print("Typer not installed; CLI disabled")
        def _opt(*a,**k): return None
        def _arg(*a,**k): return None
        typer = _TyperShim()  # type: ignore
        typer.Typer = _TyperShim  # type: ignore
        typer.Option = _opt  # type: ignore
        typer.Argument = _arg  # type: ignore
        typer.secho = print  # type: ignore

    _HAS_TYPER = True
except Exception:
    _HAS_TYPER = False
    class _TyperShim:
        def __init__(self,*a,**k): pass
        def command(self,*a,**k): return lambda f: f
        def __call__(self,*a,**k): print("Typer not installed; CLI disabled")
    def _opt(*a,**k): return None
    def _arg(*a,**k): return None
    typer = _TyperShim()  # type: ignore
    typer.Typer = _TyperShim  # type: ignore
    typer.Option = _opt  # type: ignore
    typer.Argument = _arg  # type: ignore
    typer.secho = print  # type: ignore

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
try:
    from arango.client import ArangoClient
    from arango.exceptions import ArangoError
    from arango.database import StandardDatabase
except Exception:
    ArangoClient = None  # type: ignore
    class ArangoError(Exception): ...  # type: ignore
    class StandardDatabase: ...  # type: ignore

try:
    import faiss  # type: ignore
    _HAS_FAISS = True
except Exception:
    _HAS_FAISS = False
    faiss = None  # type: ignore

from tqdm.asyncio import tqdm
from extractor.pipeline.utils.litellm_call import litellm_call
from extractor.pipeline.utils.diagnostics import get_run_id

# FAIL FAST - simple env loading
from dotenv import load_dotenv, find_dotenv
if not load_dotenv(find_dotenv(), override=True):
    raise ValueError("No .env file found - check .env exists")

logger.remove()
logger.add(sys.stderr, level="INFO")

app = typer.Typer(help="Create graph relationships between PDF objects in ArangoDB")
console = Console()

# (duplicate config block removed)
# Stage 11 configuration via environment (toggleable)
GRAPH_K = int(os.getenv("GRAPH_K_NEIGHBORS", 10))
GRAPH_SIM_THRESHOLD = float(os.getenv("GRAPH_SIMILARITY_THRESHOLD", 0.55))
GRAPH_SEMANTIC_WEIGHT = float(os.getenv("GRAPH_SEMANTIC_WEIGHT", 0.7))
GRAPH_HIERARCHY_WEIGHT = float(os.getenv("GRAPH_HIERARCHY_WEIGHT", 0.3))
GRAPH_EDGE_COLLECTION = os.getenv("GRAPH_EDGE_COLLECTION", "pdf_relationships")
GRAPH_GRAPH_NAME = os.getenv("GRAPH_NAME", "pdf_knowledge_graph")
GRAPH_VERTEX_COLLECTION = os.getenv("GRAPH_VERTEX_COLLECTION", "pdf_objects")
GRAPH_ENABLE_RATIONALES = os.getenv("GRAPH_ENABLE_RATIONALES", "true").lower() in ("1", "true", "yes", "y")
GRAPH_RATIONALE_MODEL = os.getenv("GRAPH_RATIONALE_MODEL", "openai/gpt-5-mini")
GRAPH_RATIONALE_CONCURRENCY = int(os.getenv("GRAPH_RATIONALE_CONCURRENCY", 8))
GRAPH_RATIONALE_MAX_TOKENS = int(os.getenv("GRAPH_RATIONALE_MAX_TOKENS", 256))
GRAPH_RELATIONSHIPS_ENABLED = os.getenv("GRAPH_RELATIONSHIPS_ENABLED", "true").lower() in ("1", "true", "yes", "y")


def ensure_graph_and_edge_collection(
    db: StandardDatabase,
    graph_name: str = "pdf_knowledge_graph",
    edge_collection: str = "pdf_relationships",
    vertex_collection: str = "pdf_objects"
) -> str:
    """Ensure graph and edge collection exist in ArangoDB.
    
    Returns:
        Name of the edge collection
    """
    try:
        # Create edge collection if it doesn't exist
        if not db.has_collection(edge_collection):
            db.create_collection(edge_collection, edge=True)
            logger.info(f"Created edge collection: {edge_collection}")
        
        # Create graph if it doesn't exist
        if not db.has_graph(graph_name):
            db.create_graph(
                name=graph_name,
                edge_definitions=[{
                    'edge_collection': edge_collection,
                    'from_vertex_collections': [vertex_collection],
                    'to_vertex_collections': [vertex_collection]
                }]
            )
            logger.info(f"Created graph: {graph_name}")
        
        # Add indexes for efficient queries
        edge_col = db.collection(edge_collection)
        edge_col.add_persistent_index(fields=["relationship_type"], unique=False)
        edge_col.add_persistent_index(fields=["weight"], unique=False)
        edge_col.add_persistent_index(fields=["source_pdf"], unique=False)
        
        return edge_collection
        
    except ArangoError as e:
        logger.error(f"Failed to set up graph structures: {e}")
        sys.exit(1)


def build_faiss_index(embeddings: NDArray[np.float32]) -> faiss.IndexFlatIP:
    """Build FAISS index with normalized embeddings for cosine similarity.
    
    Args:
        embeddings: Array of embeddings
        
    Returns:
        FAISS index ready for search
    """
    # Normalize for cosine similarity
    faiss.normalize_L2(embeddings)
    
    # Use inner product (equivalent to cosine similarity after normalization)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(cast(Any, embeddings))  # type: ignore[arg-type]
    
    logger.info(f"Built FAISS index with {index.ntotal} vectors")
    
    return index


def calculate_hierarchy_distance(doc1: Dict[str, Any], doc2: Dict[str, Any]) -> float:
    """Calculate normalized hierarchical distance between two documents.
    
    Returns:
        Normalized distance between 0 and 1
    """
    # If not from same PDF, max distance
    if doc1.get('source_pdf') != doc2.get('source_pdf'):
        return 1.0
    
    # Calculate section level difference
    level1 = doc1.get('section_level', 0)
    level2 = doc2.get('section_level', 0)
    level_diff = abs(level1 - level2)
    
    # Check if in same section hierarchy
    breadcrumbs1 = doc1.get('section_breadcrumbs', [])
    breadcrumbs2 = doc2.get('section_breadcrumbs', [])
    
    # Find common ancestor depth
    common_depth = 0
    for i, (b1, b2) in enumerate(zip(breadcrumbs1, breadcrumbs2)):
        if b1 == b2:
            common_depth = i + 1
        else:
            break
    
    # Calculate tree distance
    tree_distance = (len(breadcrumbs1) - common_depth) + (len(breadcrumbs2) - common_depth)
    
    # Normalize (assuming max depth of 10)
    max_possible_distance = 10
    normalized_distance = min(tree_distance / max_possible_distance, 1.0)
    
    return normalized_distance


def calculate_combined_weight(
    semantic_similarity: float,
    hierarchy_distance: float,
    semantic_weight: float = 0.7,
    hierarchy_weight: float = 0.3
) -> float:
    """Calculate combined weight using semantic similarity and hierarchy.
    
    Args:
        semantic_similarity: FAISS similarity score (0-1)
        hierarchy_distance: Normalized hierarchy distance (0-1)
        semantic_weight: Weight for semantic similarity
        hierarchy_weight: Weight for hierarchy
        
    Returns:
        Combined weight between 0 and 1
    """
    # Convert hierarchy distance to similarity using exponential decay
    hierarchy_similarity = math.exp(-3 * hierarchy_distance)
    
    # Combine weights
    combined = (semantic_weight * semantic_similarity + 
                hierarchy_weight * hierarchy_similarity)
    
    return combined

# -------- Rationale generation helpers (concurrent) --------

async def _rationale_for_pair(text_a: str, text_b: str, model: str, max_tokens: int) -> str:
    """Generate a short rationale explaining why two pdf_objects are related."""
    try:
        a_snip = (text_a or "").strip()
        b_snip = (text_b or "").strip()
        if len(a_snip) > 800:
            a_snip = a_snip[:800] + " ..."
        if len(b_snip) > 800:
            b_snip = b_snip[:800] + " ..."
        system = "You explain concisely why two document snippets are related. Use one or two sentences. Avoid quoting long text."
        user = f"Snippet A:\n{a_snip}\n\nSnippet B:\n{b_snip}\n\nExplain the relationship succinctly."

        params: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "stream": False,
            "timeout": 60,
        }
        params["temperature"] = 1.0 if "gpt-5" in (model or "").lower() else 0.1
        sid = os.getenv("LITELLM_SESSION_ID") or get_run_id()
        out = await litellm_call([params], concurrency=1, desc="graph_rationale", session_id=sid)
        return ((out[0] if out else "").strip())[:600]
    except Exception:
        return ""

async def enrich_edges_with_rationales(edges: List[Dict[str, Any]], doc_text_map: Dict[str, str]) -> None:
    """Attach rationale text to each edge using concurrent LLM calls."""
    if not edges:
        return
    sem = asyncio.Semaphore(GRAPH_RATIONALE_CONCURRENCY)

    async def _task(edge: Dict[str, Any]) -> None:
        try:
            from_id = str(edge.get("_from", ""))
            to_id = str(edge.get("_to", ""))
            ta = doc_text_map.get(from_id, "")
            tb = doc_text_map.get(to_id, "")
            if not ta or not tb:
                edge["rationale"] = ""
                edge["rationale_model"] = GRAPH_RATIONALE_MODEL
                return
            async with sem:
                rationale = await _rationale_for_pair(ta, tb, GRAPH_RATIONALE_MODEL, GRAPH_RATIONALE_MAX_TOKENS)
                edge["rationale"] = rationale
                edge["rationale_model"] = GRAPH_RATIONALE_MODEL
        except Exception:
            edge["rationale"] = ""
            edge["rationale_model"] = GRAPH_RATIONALE_MODEL

    await asyncio.gather(*(_task(e) for e in edges))


async def find_and_create_relationships(
    documents: List[Dict[str, Any]],
    embeddings: NDArray[np.float32],
    index: faiss.IndexFlatIP,
    k_neighbors: int = 10,
    similarity_threshold: float = 0.55,
    batch_size: int = 100,
    skip_db_insert: bool = False,
    db: Optional[StandardDatabase] = None,
    edge_collection: Optional[str] = None
):
    """Find similar documents and create edge relationships."""
    edge_buffer = []
    total_edges = 0
    
    # Pre-compute text lookup map for rationales
    doc_text_map: Dict[str, str] = {
        f"pdf_objects/{d.get('_key')}": (d.get('text_content') or "")
        for d in documents
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Finding relationships...", total=len(documents))
        
        for idx, doc in enumerate(documents):
            query_embedding = embeddings[idx:idx+1]
            similarities, indices = index.search(query_embedding, k_neighbors + 1)  # type: ignore[misc]
            
            for rank, (sim_idx, similarity) in enumerate(zip(indices[0][1:], similarities[0][1:]), start=1):
                if similarity < similarity_threshold:
                    continue
                
                neighbor_doc = documents[int(sim_idx)]
                hierarchy_dist = calculate_hierarchy_distance(doc, neighbor_doc)
                combined_weight = calculate_combined_weight(
                    similarity, hierarchy_dist,
                    semantic_weight=GRAPH_SEMANTIC_WEIGHT,
                    hierarchy_weight=GRAPH_HIERARCHY_WEIGHT,
                )
                
                edge_doc = {
                    '_from': f"pdf_objects/{doc['_key']}",
                    '_to': f"pdf_objects/{neighbor_doc['_key']}",
                    'relationship_type': 'semantic_similarity',
                    'semantic_score': float(similarity),
                    'hierarchy_distance': hierarchy_dist,
                    'weight': float(combined_weight),
                    'source_pdf': doc['source_pdf'],
                    'discovery_method': 'faiss_hierarchical',
                    'knn_rank': int(rank),
                    'neighbor_index': int(sim_idx),
                    'created_at': datetime.now(timezone.utc).isoformat()
                }
                
                edge_buffer.append(edge_doc)
                
                if not skip_db_insert and len(edge_buffer) >= batch_size:
                    try:
                        if GRAPH_ENABLE_RATIONALES:
                            await enrich_edges_with_rationales(edge_buffer, doc_text_map)
                        assert db is not None and edge_collection is not None
                        edge_col = db.collection(edge_collection)
                        result = edge_col.import_bulk(edge_buffer, on_duplicate='ignore')
                        created = 0
                        try:
                            created = int(result.get('created', 0))  # type: ignore[attr-defined]
                        except Exception:
                            created = 0
                        total_edges += created
                        edge_buffer.clear()
                    except ArangoError as e:
                        logger.error(f"Failed to insert edges: {e}")
            
            progress.update(task, advance=1)
    
    if not skip_db_insert and edge_buffer:
        try:
            if GRAPH_ENABLE_RATIONALES:
                await enrich_edges_with_rationales(edge_buffer, doc_text_map)
            assert db is not None and edge_collection is not None
            edge_col = db.collection(edge_collection)
            result = edge_col.import_bulk(edge_buffer, on_duplicate='ignore')
            created = 0
            try:
                created = int(result.get('created', 0))  # type: ignore[attr-defined]
            except Exception:
                created = 0
            total_edges += created
        except ArangoError as e:
            logger.error(f"Failed to insert final edges: {e}")
    
    if skip_db_insert and GRAPH_ENABLE_RATIONALES and edge_buffer:
        await enrich_edges_with_rationales(edge_buffer, doc_text_map)

    if not skip_db_insert:
        logger.success(f"Created {total_edges} edge relationships")
    
    return edge_buffer if skip_db_insert else total_edges


@app.command()
def run(
    input_json: Path = typer.Argument(..., help="Path to Stage 10 flattened data JSON.", exists=True),
    output_dir: Path = typer.Option("data/results/pipeline", "-o", help="Parent directory for pipeline results."),
    k_neighbors: int = typer.Option(10, help="Number of neighbors to find for similarity."),
    similarity_threshold: float = typer.Option(0.55, help="Minimum similarity to create an edge."),
    skip_graph_creation: bool = typer.Option(False, "--skip-graph-creation", help="Prepare graph edges but do not export to ArangoDB."),
):
    """Builds graph relationships between PDF objects using FAISS and hierarchy."""
    console.print("[bold green]Building PDF Knowledge Graph (Stage 11)[/bold green]")

    # --- Directory and Data Setup ---
    stage_output_dir = output_dir / "11_arango_create_graph"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    with open(input_json, 'r') as f:
        documents = json.load(f)

    if not documents:
        console.print("[yellow]No documents to process. Exiting.[/yellow]")
        return

    # Global toggle to disable relationship building entirely
    if not GRAPH_RELATIONSHIPS_ENABLED:
        if skip_graph_creation:
            output_path = json_output_dir / "11_graph_edges.json"
            with open(output_path, 'w') as f:
                json.dump([], f, indent=2)
            console.print(f"[yellow]Relationships disabled (GRAPH_RELATIONSHIPS_ENABLED=false). Wrote 0 edges to: {output_path}[/yellow]")
        else:
            confirmation = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "Skipped",
                "edges_created": 0,
                "reason": "GRAPH_RELATIONSHIPS_ENABLED=false"
            }
            output_path = json_output_dir / "11_graph_confirmation.json"
            with open(output_path, 'w') as f:
                json.dump(confirmation, f, indent=2)
            console.print(f"[yellow]Relationships disabled (GRAPH_RELATIONSHIPS_ENABLED=false). Confirmation saved to: {output_path}[/yellow]")
        return

    docs_with_embed = [doc for doc in documents if doc.get('embedding')]
    if not docs_with_embed:
        if skip_graph_creation:
            output_path = json_output_dir / "11_graph_edges.json"
            with open(output_path, 'w') as f:
                json.dump([], f, indent=2)
            console.print(f"[yellow]No embeddings found; wrote 0 edges to: {output_path}[/yellow]")
            return
        else:
            confirmation = {
                "timestamp": datetime.now().isoformat(),
                "status": "Completed",
                "edges_created": 0,
            }
            output_path = json_output_dir / "11_graph_confirmation.json"
            with open(output_path, 'w') as f:
                json.dump(confirmation, f, indent=2)
            console.print(f"[yellow]No embeddings found; confirmation saved to: {output_path}[/yellow]")
            return
    embeddings = np.array([doc['embedding'] for doc in docs_with_embed], dtype='float32')

    # --- FAISS Indexing ---
    console.print("Building FAISS index...")
    index = build_faiss_index(embeddings)

    # --- Relationship Calculation ---
    console.print("Finding and creating relationships...")
    
    db = None
    edge_collection = GRAPH_EDGE_COLLECTION
    if not skip_graph_creation:
        try:
            host = os.getenv("ARANGO_HOST", "localhost")
            port = int(os.getenv("ARANGO_PORT", 8529))
            user = os.getenv("ARANGO_USER", "root")
            password = os.getenv("ARANGO_PASSWORD")
            db_name = os.getenv("ARANGO_DATABASE", "pdf_knowledge_base")
            
            if not password:
                raise ValueError("ARANGO_PASSWORD environment variable is not set.")
            
            client = ArangoClient(hosts=f"http://{host}:{port}")
            db = client.db(db_name, username=user, password=password)
            db.version()
            logger.success(f"Connected to ArangoDB database '{db_name}'.")
            edge_collection = ensure_graph_and_edge_collection(
                db,
                graph_name=GRAPH_GRAPH_NAME,
                edge_collection=GRAPH_EDGE_COLLECTION,
                vertex_collection=GRAPH_VERTEX_COLLECTION
            )
        except (ArangoError, ValueError) as e:
            logger.error(f"Failed to connect to ArangoDB: {e}")
            raise typer.Exit(1)

    edges = asyncio.run(find_and_create_relationships(
        documents=docs_with_embed,
        embeddings=embeddings,
        index=index,
        k_neighbors=k_neighbors if k_neighbors else GRAPH_K,
        similarity_threshold=similarity_threshold if similarity_threshold else GRAPH_SIM_THRESHOLD,
        skip_db_insert=skip_graph_creation,
        db=db,
        edge_collection=edge_collection
    ))

    # --- Final Output ---
    if skip_graph_creation:
        console.print("[yellow]--skip-graph-creation flag is set. Saving graph edges to JSON.[/yellow]")
        output_path = json_output_dir / "11_graph_edges.json"
        with open(output_path, 'w') as f:
            json.dump(edges, f, indent=2)
        edges_list = cast(List[Dict[str, Any]], edges)
        console.print(f"📄 Saved {len(edges_list)} graph edges to: {output_path}")
    else:
        confirmation = {
            "timestamp": datetime.now().isoformat(),
            "status": "Completed",
            "edges_created": edges,
        }
        output_path = json_output_dir / "11_graph_confirmation.json"
        with open(output_path, 'w') as f:
            json.dump(confirmation, f, indent=2)
        console.print(f"✅ Graph creation complete. Confirmation saved to: {output_path}")

@app.command("debug-bundle")
def debug_bundle(
    bundle: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Bundle JSON with key 'documents' (flattened pdf_objects)"),
    output_dir: Path = typer.Option("data/results/pipeline", "-o", help="Parent directory for pipeline results."),
    k_neighbors: int = typer.Option(10, help="Number of neighbors to find for similarity."),
    similarity_threshold: float = typer.Option(0.55, help="Minimum similarity to create an edge."),
):
    """Run Stage 11 from a single JSON bundle, emitting edges JSON without DB access."""
    stage_output_dir = output_dir / "11_arango_create_graph"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    try:
        data = json.loads(bundle.read_text())
        documents = data.get("documents")
        if not isinstance(documents, list) or not documents:
            raise ValueError("Bundle must include non-empty 'documents' list")
    except Exception as e:
        typer.secho(f"Failed to load bundle: {e}", fg=typer.colors.RED); raise typer.Exit(1)

    docs_with_embed = [doc for doc in documents if doc.get('embedding')]
    if not docs_with_embed:
        typer.secho("No documents with embeddings provided.", fg=typer.colors.YELLOW)
        output_path = json_output_dir / "11_graph_edges.json"
        output_path.write_text(json.dumps([], indent=2))
        console.print(f"[yellow]Saved 0 edges to {output_path}")
        return

    embeddings = np.array([doc['embedding'] for doc in docs_with_embed], dtype='float32')
    index = build_faiss_index(embeddings)

    edges = asyncio.run(find_and_create_relationships(
        documents=docs_with_embed,
        embeddings=embeddings,
        index=index,
        k_neighbors=k_neighbors,
        similarity_threshold=similarity_threshold,
        skip_db_insert=True,
        db=None,
        edge_collection=GRAPH_EDGE_COLLECTION,
    ))

    output_path = json_output_dir / "11_graph_edges.json"
    output_path.write_text(json.dumps(edges, indent=2))
    console.print(f"[green]Debug bundle: saved {len(edges)} graph edges to {output_path}")
 
if __name__ == "__main__":
    app()
