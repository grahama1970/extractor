import duckdb
import logging

logger = logging.getLogger(__name__)

def create_schema(con: duckdb.DuckDBPyConnection):
    """
    Applies the schema DDL to the DuckDB connection.
    Creates tables: sections, blocks, tables, figures, requirements.
    Creates macros: box_overlap, box_area.
    Creates views: v_clean_blocks.
    """
    logger.info("Initializing DuckDB Schema...")
    
    con.execute("""
        -- MACROS for Spatial Logic
        CREATE MACRO IF NOT EXISTS box_overlap(ax0, ay0, ax1, ay1, bx0, by0, bx1, by1) AS
            GREATEST(0.0, LEAST(ax1, bx1) - GREATEST(ax0, bx0)) * 
            GREATEST(0.0, LEAST(ay1, by1) - GREATEST(ay0, by0));
        
        CREATE MACRO IF NOT EXISTS box_area(x0, y0, x1, y1) AS
            (x1 - x0) * (y1 - y0);

        -- TABLES
        CREATE TABLE IF NOT EXISTS sections (
            id VARCHAR PRIMARY KEY,
            title VARCHAR,
            page_start INTEGER,
            page_end INTEGER,
            parent_id VARCHAR,
            -- LLM enrichment columns (added to schema to prevent runtime ALTER TABLE drift)
            llm_summary VARCHAR,
            llm_key_concepts VARCHAR,  -- JSON array of key concepts
            llm_metadata VARCHAR       -- JSON object with token usage, model, latency
        );
        
        CREATE TABLE IF NOT EXISTS blocks (
            id VARCHAR PRIMARY KEY,
            page INTEGER,
            x0 DOUBLE,
            y0 DOUBLE,
            x1 DOUBLE,
            y1 DOUBLE,
            text VARCHAR,
            type VARCHAR,
            section_id VARCHAR -- Foreign Key to sections.id (logical)
        );

        CREATE TABLE IF NOT EXISTS tables (
            id VARCHAR PRIMARY KEY,
            page INTEGER,
            x0 DOUBLE,
            y0 DOUBLE,
            x1 DOUBLE,
            y1 DOUBLE,
            csv_data VARCHAR,
            html_data VARCHAR,
            section_id VARCHAR,
            sort_order INTEGER,  -- page * 10000 + y0 for reading order
            llm_title VARCHAR,
            llm_description VARCHAR,
            image_path VARCHAR
        );
        
        CREATE TABLE IF NOT EXISTS figures (
            id VARCHAR PRIMARY KEY,
            page INTEGER,
            x0 DOUBLE,
            y0 DOUBLE,
            x1 DOUBLE,
            y1 DOUBLE,
            image_path VARCHAR,
            section_id VARCHAR,
            sort_order INTEGER,  -- page * 10000 + y0 for reading order
            llm_title VARCHAR,
            llm_description VARCHAR
        );
        
        CREATE TABLE IF NOT EXISTS requirements (
             id VARCHAR PRIMARY KEY,
             req_id VARCHAR,          -- Human-readable ID like REQ-4.1.5-001
             section_id VARCHAR,
             text VARCHAR,
             type VARCHAR,            -- Function, Interface, Physical, etc.
             confidence DOUBLE,
             citation_snippet VARCHAR,
             is_table_row BOOLEAN DEFAULT FALSE,
             is_conditional BOOLEAN DEFAULT FALSE,  -- When X, shall Y
             condition_text VARCHAR,  -- The condition clause if is_conditional
             sort_order INTEGER,      -- Reading order within document
             page INTEGER,
             y0 DOUBLE,               -- For positioning context
             metadata_json VARCHAR,   -- JSON metadata (bbox, source, etc.)
             run_id VARCHAR           -- Execution run ID for safe cleanup
        );
        
        CREATE TABLE IF NOT EXISTS lean4_proofs (
             id VARCHAR PRIMARY KEY,
             requirement_id VARCHAR,  -- FK to requirements.id
             theorem_strategy VARCHAR,  -- LLM-generated proof strategy
             lean4_code VARCHAR,      -- Generated Lean4 theorem code
             compilation_status VARCHAR,  -- pending, success, error
             compilation_error VARCHAR,
             proof_result VARCHAR,    -- proven, counterexample, timeout
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS annotations (
            id VARCHAR PRIMARY KEY,
            page INTEGER,
            type VARCHAR,
            x0 DOUBLE,
            y0 DOUBLE,
            x1 DOUBLE,
            y1 DOUBLE,
            human_note VARCHAR,
            image_path VARCHAR,
            provenance VARCHAR
        );
        
        -- merged_content: Unified reading order for all content types
        CREATE TABLE IF NOT EXISTS merged_content (
             id VARCHAR PRIMARY KEY,
             section_id VARCHAR,
             page INTEGER,
             type VARCHAR,           -- 'text', 'section', 'figure', 'table', 'requirement'
             content VARCHAR,
             asset_id VARCHAR,       -- FK to requirements.id, figures.id, etc.
             sort_order INTEGER      -- Reading order position
        );

        -- VIEWS
        
        -- v_clean_blocks: Removes blocks that are effectively "covered" by tables or figures
        -- Rule: If overlap area > 50% of the block's area, assume the block is just capturing the table text poorly.
        CREATE OR REPLACE VIEW v_clean_blocks AS
        SELECT b.*
        FROM blocks b
        WHERE NOT EXISTS (
            SELECT 1 FROM tables t
            WHERE b.page = t.page
            AND box_overlap(b.x0, b.y0, b.x1, b.y1, t.x0, t.y0, t.x1, t.y1) >= 0.5 * box_area(b.x0, b.y0, b.x1, b.y1)
        )
        AND NOT EXISTS (
            SELECT 1 FROM figures f
            WHERE b.page = f.page
            AND box_overlap(b.x0, b.y0, b.x1, b.y1, f.x0, f.y0, f.x1, f.y1) >= 0.5 * box_area(b.x0, b.y0, b.x1, b.y1)
        );

        -- v_corpus_sections: Facilitates the "Focused Extraction" by providing a single point of access
        -- Note: This is a logical view concept. Since Tables/Figures are 1-to-Many with Sections,
        -- we typically query them separately. However, this view can check coverage.
        -- For now, we rely on the `section_id` FK which we populate in Stage 07.
    """)
    logger.info("Schema initialized successfully.")
