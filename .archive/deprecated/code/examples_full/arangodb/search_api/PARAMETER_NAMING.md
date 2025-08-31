# Search Module Parameter Naming Conventions

This document establishes the standard parameter naming conventions for all search modules in the Complexity project. Following these conventions ensures a consistent API across different search methods and makes the codebase more maintainable.

## Common Parameter Names

| Parameter | Type | Description | Used In |
|-----------|------|-------------|---------|
| `query_text` | str | The main search query text | All search modules |
| `db` | StandardDatabase | ArangoDB database connection | All modules |
| `collections` | List[str] | List of collections to search in | All modules |
| `top_n` | int | Maximum number of results to return | All modules |
| `min_score` | float or Dict[str, float] | Minimum score threshold | All modules |
| `tag_list` | List[str] | List of tags to filter results | All modules |
| `filter_expr` | str | Additional AQL filter expression | All modules |
| `output_format` | str | Output format (table/json) | All modules |
| `offset` | int | Pagination offset | All modules |
| `fields_to_return` | List[str] | Fields to include in results | All modules |

## Module-Specific Parameters

### Hybrid Search

| Parameter | Type | Description |
|-----------|------|-------------|
| `initial_k` | int | Number of candidates from each search method |
| `weights` | Dict[str, float] | Weights for different search types |
| `rrf_k` | int | Constant for RRF calculation |
| `use_graph` | bool | Whether to include graph traversal |
| `use_perplexity` | bool | Whether to use Perplexity API |

### Semantic Search

| Parameter | Type | Description |
|-----------|------|-------------|
| `query_embedding` | List[float] | Embedding vector of the query |
| `embedding_field` | str | Field containing embeddings |
| `similarity_threshold` | float | Minimum similarity score (0-1) |

### Tag Search

| Parameter | Type | Description |
|-----------|------|-------------|
| `tags` | List[str] | List of tags to search for |
| `require_all_tags` | bool | Whether all tags must be present |
| `limit` | int | Maximum number of results (alias for top_n) |

### Keyword Search

| Parameter | Type | Description |
|-----------|------|-------------|
| `search_term` | str | The keyword(s) to search for (alias for query_text) |
| `similarity_threshold` | float | Minimum similarity for fuzzy matching (0-100) |
| `fields_to_search` | List[str] | Fields to search within |

## Parameter Transformation

When integrating search functions into the CLI or other interfaces, transform parameters as follows:

| CLI/External Parameter | Internal Parameter | Transformation |
|------------------------|---------------------|----------------|
| `threshold` (semantic) | `min_score` or `similarity_threshold` | Direct mapping |
| `threshold` (bm25) | `min_score` | Direct mapping |
| `query` | `query_text` or `search_term` | Direct mapping |
| `tags` (comma-separated string) | `tag_list` | Split string into list |
| `fields` (comma-separated string) | `fields_to_return` or `fields_to_search` | Split string into list |

## Standardization Guidelines

1. Always use `query_text` for the main search query parameter
2. Use `top_n` for maximum result count (not `limit` or `max_results`)
3. Always accept `collections` as a list, defaulting to a standard value
4. Use consistent parameter order across modules:
   - Core parameters (db, query, collections)
   - Filter parameters (filter_expr, tag_list, min_score)
   - Pagination/limiting parameters (top_n, offset)
   - Output control parameters (output_format, fields_to_return)
   - Special features parameters (use_graph, weights, etc.)