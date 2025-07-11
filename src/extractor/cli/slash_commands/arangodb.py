"""ArangoDB slash commands for marker.
Module: arangodb.py

Provides commands for database operations, import/export, and search.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import typer
from loguru import logger
import json

from .base import CommandGroup, validate_file_path, validate_url, format_output
from extractor.core.arangodb.pipeline import ArangoDBPipeline as ArangoDBImporter
from extractor.core.renderers.arangodb_json import ArangoDBRenderer
from extractor.core.schema.document import Document


class ArangoDBCommands(CommandGroup):
    """ArangoDB integration commands."""
    
    def __init__(self):
        super().__init__(
            name="marker-db",
            description="ArangoDB database operations for marker documents",
            category="database"
        )
    
    def _setup_commands(self):
        """Setup ArangoDB command handlers."""
        super()._setup_commands()
        
        @self.app.command()
        def setup(
            url: str = typer.Option("http://localhost:8529", help="ArangoDB URL"),
            database: str = typer.Option("marker", help="Database name"),
            username: str = typer.Option("root", help="Username"),
            password: str = typer.Option("", help="Password", prompt=True, hide_input=True),
            create_db: bool = typer.Option(True, help="Create database if not exists")
        ):
            """Initialize ArangoDB for marker documents."""
            try:
                from extractor.core.utils.arango_setup import setup_arangodb
                
                logger.info(f"Setting up ArangoDB at {url}")
                
                # Create database and collections
                setup_arangodb(
                    url=url,
                    username=username,
                    password=password,
                    database=database,
                    create_if_not_exists=create_db
                )
                
                print(f" ArangoDB setup complete")
                print(f"  Database: {database}")
                print(f"  Collections: documents, blocks, entities, relationships")
                print(f"  Indexes created for efficient search")
                
            except Exception as e:
                logger.error(f"Setup failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def import_doc(
            json_path: str = typer.Argument(..., help="Path to marker JSON output"),
            url: str = typer.Option("http://localhost:8529", help="ArangoDB URL"),
            database: str = typer.Option("marker", help="Database name"),
            username: str = typer.Option("root", help="Username"),
            password: str = typer.Option(None, help="Password"),
            batch_size: int = typer.Option(100, help="Batch size for import"),
            skip_existing: bool = typer.Option(False, help="Skip documents that already exist")
        ):
            """Import marker extraction results into ArangoDB."""
            try:
                json_path = validate_file_path(json_path)
                
                # Prompt for password if not provided
                if password is None:
                    password = typer.prompt("Password", hide_input=True)
                
                logger.info(f"Importing {json_path} to ArangoDB")
                
                # Create importer
                importer = ArangoDBImporter(
                    url=url,
                    username=username,
                    password=password,
                    database=database
                )
                
                # Import document
                stats = importer.import_document(
                    json_path,
                    batch_size=batch_size,
                    skip_existing=skip_existing
                )
                
                print(f" Import complete")
                print(f"  Documents: {stats.get('documents', 0)}")
                print(f"  Blocks: {stats.get('blocks', 0)}")
                print(f"  Entities: {stats.get('entities', 0)}")
                print(f"  Relationships: {stats.get('relationships', 0)}")
                
                if stats.get('errors'):
                    print(f"  ⚠️  Errors: {stats['errors']}")
                
            except Exception as e:
                logger.error(f"Import failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def search(
            query: str = typer.Argument(..., help="Search query"),
            url: str = typer.Option("http://localhost:8529", help="ArangoDB URL"),
            database: str = typer.Option("marker", help="Database name"),
            username: str = typer.Option("root", help="Username"),
            password: str = typer.Option(None, help="Password"),
            collection: str = typer.Option("blocks", help="Collection to search"),
            limit: int = typer.Option(10, help="Maximum results"),
            output_format: str = typer.Option("text", help="Output format (text, json, table)")
        ):
            """Search extracted content in ArangoDB."""
            try:
                # Prompt for password if not provided
                if password is None:
                    password = typer.prompt("Password", hide_input=True)
                
                from arango import ArangoClient
                
                # Connect to ArangoDB
                client = ArangoClient(hosts=url)
                db = client.db(database, username=username, password=password)
                
                # Build AQL query
                aql = f"""
                FOR doc IN {collection}
                    FILTER CONTAINS(LOWER(doc.text), LOWER(@query))
                    LIMIT @limit
                    RETURN {{
                        _key: doc._key,
                        type: doc.block_type,
                        text: SUBSTRING(doc.text, 0, 200),
                        page: doc.page_range[0],
                        document: doc.document_id
                    }}
                """
                
                # Execute search
                cursor = db.aql.execute(
                    aql,
                    bind_vars={'query': query, 'limit': limit}
                )
                
                results = list(cursor)
                
                if not results:
                    print(f"No results found for '{query}'")
                    return
                
                print(f"Found {len(results)} results for '{query}':\n")
                
                # Format output
                if output_format == "json":
                    print(json.dumps(results, indent=2))
                elif output_format == "table":
                    print(format_output(results, "table"))
                else:
                    # Text format
                    for i, result in enumerate(results, 1):
                        print(f"{i}. [{result['type']}] Page {result.get('page', 'N/A')}")
                        print(f"   {result['text']}...")
                        print(f"   Document: {result['document']}")
                        print()
                
            except Exception as e:
                logger.error(f"Search failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def export(
            document_id: str = typer.Argument(..., help="Document ID to export"),
            output_path: Optional[str] = typer.Option(None, help="Output file path"),
            url: str = typer.Option("http://localhost:8529", help="ArangoDB URL"),
            database: str = typer.Option("marker", help="Database name"),
            username: str = typer.Option("root", help="Username"),
            password: str = typer.Option(None, help="Password"),
            format: str = typer.Option("json", help="Export format (json, markdown)")
        ):
            """Export a document from ArangoDB."""
            try:
                # Prompt for password if not provided
                if password is None:
                    password = typer.prompt("Password", hide_input=True)
                
                from arango import ArangoClient
                
                # Connect to ArangoDB
                client = ArangoClient(hosts=url)
                db = client.db(database, username=username, password=password)
                
                # Get document
                doc_collection = db.collection('documents')
                doc_data = doc_collection.get(document_id)
                
                if not doc_data:
                    print(f"Document '{document_id}' not found")
                    raise typer.Exit(1)
                
                # Get associated blocks
                aql = """
                FOR block IN blocks
                    FILTER block.document_id == @doc_id
                    SORT block.page_range[0], block.order
                    RETURN block
                """
                
                cursor = db.aql.execute(aql, bind_vars={'doc_id': document_id})
                blocks = list(cursor)
                
                # Reconstruct document
                doc_data['blocks'] = blocks
                
                # Setup output path
                if output_path:
                    output_file = Path(output_path)
                else:
                    output_file = Path(f"{document_id}_export.{format}")
                
                # Export based on format
                if format == "json":
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(doc_data, f, indent=2, ensure_ascii=False)
                elif format == "markdown":
                    # Convert to markdown
                    from extractor.core.renderers.markdown import MarkdownRenderer
                    # Note: This would need proper document reconstruction
                    # For now, just save as JSON
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(doc_data, f, indent=2, ensure_ascii=False)
                
                print(f" Exported document to: {output_file}")
                
            except Exception as e:
                logger.error(f"Export failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def stats(
            url: str = typer.Option("http://localhost:8529", help="ArangoDB URL"),
            database: str = typer.Option("marker", help="Database name"),
            username: str = typer.Option("root", help="Username"),
            password: str = typer.Option(None, help="Password")
        ):
            """Show database statistics."""
            try:
                # Prompt for password if not provided
                if password is None:
                    password = typer.prompt("Password", hide_input=True)
                
                from arango import ArangoClient
                
                # Connect to ArangoDB
                client = ArangoClient(hosts=url)
                db = client.db(database, username=username, password=password)
                
                print(f" Database Statistics for '{database}':\n")
                
                # Get collection stats
                collections = ['documents', 'blocks', 'entities', 'relationships']
                for coll_name in collections:
                    try:
                        coll = db.collection(coll_name)
                        count = coll.count()
                        print(f"  {coll_name}: {count:,} items")
                    except:
                        print(f"  {coll_name}: Not found")
                
                # Get block type distribution
                aql = """
                FOR block IN blocks
                    COLLECT type = block.block_type WITH COUNT INTO count
                    SORT count DESC
                    RETURN {type: type, count: count}
                """
                
                cursor = db.aql.execute(aql)
                block_types = list(cursor)
                
                if block_types:
                    print(f"\n Block Type Distribution:")
                    for bt in block_types:
                        print(f"  {bt['type']}: {bt['count']:,}")
                
                # Get document stats
                aql = """
                FOR doc IN documents
                    COLLECT WITH COUNT INTO total
                    RETURN {
                        total: total,
                        avg_pages: AVG(doc.page_count),
                        max_pages: MAX(doc.page_count),
                        min_pages: MIN(doc.page_count)
                    }
                """
                
                cursor = db.aql.execute(aql)
                doc_stats = list(cursor)
                
                if doc_stats and doc_stats[0]['total'] > 0:
                    stats = doc_stats[0]
                    print(f"\n Document Statistics:")
                    print(f"  Total documents: {stats['total']:,}")
                    print(f"  Average pages: {stats['avg_pages']:.1f}")
                    print(f"  Min pages: {stats['min_pages']}")
                    print(f"  Max pages: {stats['max_pages']}")
                
            except Exception as e:
                logger.error(f"Failed to get stats: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def visualize(
            document_id: Optional[str] = typer.Option(None, help="Specific document to visualize"),
            output_path: str = typer.Option("graph.html", help="Output HTML file"),
            url: str = typer.Option("http://localhost:8529", help="ArangoDB URL"),
            database: str = typer.Option("marker", help="Database name"),
            username: str = typer.Option("root", help="Username"),
            password: str = typer.Option(None, help="Password"),
            max_nodes: int = typer.Option(100, help="Maximum nodes to display")
        ):
            """Generate visualization of document structure."""
            try:
                # Prompt for password if not provided
                if password is None:
                    password = typer.prompt("Password", hide_input=True)
                
                from arango import ArangoClient
                
                # Connect to ArangoDB
                client = ArangoClient(hosts=url)
                db = client.db(database, username=username, password=password)
                
                # Build query based on whether document_id is provided
                if document_id:
                    aql = """
                    LET doc = DOCUMENT(CONCAT('documents/', @doc_id))
                    LET blocks = (
                        FOR block IN blocks
                            FILTER block.document_id == @doc_id
                            LIMIT @max_nodes
                            RETURN {
                                id: block._key,
                                label: block.block_type,
                                group: block.block_type,
                                title: SUBSTRING(block.text, 0, 100)
                            }
                    )
                    RETURN {
                        nodes: APPEND([{
                            id: doc._key,
                            label: doc.filename,
                            group: "document",
                            title: doc.filename
                        }], blocks),
                        edges: (
                            FOR block IN blocks
                                RETURN {
                                    from: doc._key,
                                    to: block.id
                                }
                        )
                    }
                    """
                    bind_vars = {'doc_id': document_id, 'max_nodes': max_nodes}
                else:
                    # Visualize overall structure
                    aql = """
                    LET docs = (
                        FOR doc IN documents
                            LIMIT 10
                            RETURN {
                                id: doc._key,
                                label: doc.filename,
                                group: "document",
                                title: doc.filename
                            }
                    )
                    LET entities = (
                        FOR entity IN entities
                            LIMIT @max_nodes
                            RETURN {
                                id: entity._key,
                                label: entity.name,
                                group: entity.type,
                                title: entity.type
                            }
                    )
                    RETURN {
                        nodes: APPEND(docs, entities),
                        edges: (
                            FOR rel IN relationships
                                LIMIT @max_nodes
                                RETURN {
                                    from: rel._from,
                                    to: rel._to,
                                    label: rel.type
                                }
                        )
                    }
                    """
                    bind_vars = {'max_nodes': max_nodes}
                
                # Execute query
                cursor = db.aql.execute(aql, bind_vars=bind_vars)
                graph_data = list(cursor)[0] if cursor else {'nodes': [], 'edges': []}
                
                # Generate HTML visualization
                html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Marker Document Graph</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style type="text/css">
        #mynetwork {{
            width: 100%;
            height: 600px;
            border: 1px solid lightgray;
        }}
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
        }}
        h1 {{
            color: #333;
        }}
        .legend {{
            margin-top: 20px;
            padding: 10px;
            background: #f5f5f5;
            border-radius: 5px;
        }}
        .legend-item {{
            display: inline-block;
            margin-right: 20px;
        }}
        .legend-color {{
            display: inline-block;
            width: 20px;
            height: 20px;
            margin-right: 5px;
            vertical-align: middle;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <h1>Marker Document Graph Visualization</h1>
    <div id="mynetwork"></div>
    <div class="legend">
        <div class="legend-item">
            <span class="legend-color" style="background: #97C2FC;"></span>
            <span>Document</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background: #FFFF00;"></span>
            <span>Text</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background: #FB7E81;"></span>
            <span>Table</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background: #7BE141;"></span>
            <span>Code</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background: #FFA807;"></span>
            <span>Entity</span>
        </div>
    </div>

    <script type="text/javascript">
        // Create nodes and edges
        var nodes = new vis.DataSet({json.dumps(graph_data['nodes'])});
        var edges = new vis.DataSet({json.dumps(graph_data['edges'])});

        // Create a network
        var container = document.getElementById('mynetwork');
        var data = {{
            nodes: nodes,
            edges: edges
        }};
        
        // Configure options
        var options = {{
            nodes: {{
                shape: 'dot',
                size: 20,
                font: {{
                    size: 14
                }}
            }},
            edges: {{
                arrows: 'to',
                font: {{
                    size: 12,
                    align: 'middle'
                }}
            }},
            groups: {{
                document: {{color: '#97C2FC'}},
                Text: {{color: '#FFFF00'}},
                Table: {{color: '#FB7E81'}},
                Code: {{color: '#7BE141'}},
                Figure: {{color: '#C2FABC'}},
                Entity: {{color: '#FFA807'}}
            }},
            physics: {{
                enabled: true,
                barnesHut: {{
                    gravitationalConstant: -2000,
                    centralGravity: 0.3,
                    springLength: 95,
                    springConstant: 0.04
                }}
            }}
        }};

        // Initialize network
        var network = new vis.Network(container, data, options);
    </script>
</body>
</html>
"""
                
                # Write HTML file
                output_file = Path(output_path)
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                print(f" Visualization saved to: {output_file}")
                print(f"  Nodes: {len(graph_data['nodes'])}")
                print(f"  Edges: {len(graph_data['edges'])}")
                print(f"\nOpen in browser to view interactive graph")
                
            except Exception as e:
                logger.error(f"Visualization failed: {e}")
                raise typer.Exit(1)
    
    def get_examples(self) -> List[str]:
        """Get example usage."""
        return [
            "/marker-db setup --database marker --create-db",
            "/marker-db import-doc output.json --batch-size 500",
            "/marker-db search 'machine learning' --limit 20",
            "/marker-db export doc_123 --format markdown",
            "/marker-db stats",
            "/marker-db visualize --document-id doc_123 --output-path graph.html",
        ]