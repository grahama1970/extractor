"""
Module: create_view.py

External Dependencies:
- arango: https://docs.python-arango.com/
- loguru: https://loguru.readthedocs.io/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

from typing import Dict, Any, List
from arango import ArangoClient, ArangoError, ServerConnectionError
from loguru import logger
from app.backend.arangodb_helper.aql_queries.connect_to_arango_client import connect_to_arango_client

def validate_analyzers(db, analyzers: Dict[str, Dict[str, List[str]]]):
    """
    Validate that all specified analyzers exist in the database.

    This function ensures that the analyzers specified in the configuration
    are available in the database. If any analyzers are missing, a warning
    is logged.

    Args:
        db: ArangoDB database instance.
        analyzers (Dict[str, Dict[str, List[str]]]): Analyzers configuration mapping collections
            to their field-analyzer mappings.

    Raises:
        Exception: If an error occurs while fetching analyzers from the database.
    """
    try:
        # Fetch all existing analyzers in the database
        existing_analyzers = {analyzer["name"] for analyzer in db.analyzers()}
        missing_analyzers = set()

        # Check each analyzer specified in the config
        for collection_analyzers in analyzers.values():
            for analyzer_list in collection_analyzers.values():
                for analyzer in analyzer_list:
                    if analyzer not in existing_analyzers:
                        missing_analyzers.add(analyzer)

        # Log missing analyzers
        if missing_analyzers:
            logger.warning(f"The following analyzers do not exist: {', '.join(missing_analyzers)}. Ensure they are created beforehand.")
    except Exception as e:
        logger.error(f"Error while validating analyzers: {e}")
        raise


def create_or_update_arango_view(db, view_config: Dict[str, Any]):
    """
    Create or update an ArangoSearch view based on the provided configuration.

    This function creates a new ArangoSearch view if it doesn't exist or updates'
    an existing view based on the provided properties. It supports a `force`
    flag to allow overwriting an existing view.

    Args:
        db: ArangoDB database instance.
        view_config (Dict[str, Any]): Configuration for the view, including:
            - view_name: Name of the view to create or update.
            - collections: List of collections to link to the view.
            - analyzers: Nested dictionary specifying field-analyzer mappings for each collection.
            - force: Boolean flag to overwrite the view if it already exists.

    Returns:
        view: The updated or newly created ArangoSearch view object.

    Raises:
        ValueError: If any collections specified in the config do not exist in the database.
        Exception: For any other unexpected errors during the process.
    """
    view_name = view_config["view_name"]
    collections = view_config["collections"]
    analyzers = view_config.get("analyzers", {})
    force = view_config.get("force", False)

    logger.info(f"Creating or updating ArangoSearch view '{view_name}'...")

    # Cache existing views and collections
    existing_views = {view['name'] for view in db.views()}
    existing_collections = {collection["name"] for collection in db.collections()}

    # Validate analyzers before proceeding
    validate_analyzers(db, analyzers)

    # Define links configuration for the view
    links = {
        collection: {
            "fields": {
                field: {"analyzers": analyzer_list}
                for field, analyzer_list in analyzers.get(collection, {}).items()
            },
            "includeAllFields": False,  # Index only specified fields
            "storeValues": "none",      # Avoid storing field values
            "trackListPositions": False # Disable position tracking for list fields
        }
        for collection in collections if collection in existing_collections
    }

    # Check for missing collections and raise an error if any are missing
    missing_collections = [col for col in collections if col not in existing_collections]
    if missing_collections:
        raise ValueError(f"The following collections do not exist: {', '.join(missing_collections)}")

    # Prepare view properties
    view_properties = {"links": links}

    try:
        # If the view exists, update or skip based on the 'force' flag
        if view_name in existing_views:
            if force:
                # Replace the existing view with new properties
                db.replace_arangosearch_view(view_name, properties=view_properties)
                logger.info(f"View '{view_name}' replaced with new properties.")
            else:
                logger.info(f"View '{view_name}' already exists. Skipping update.")
        else:
            # Create a new view if it doesn't exist
            view_properties['cleanupIntervalMsec'] = 500
            db.replace_arangosearch_view(name=view_name, properties=view_properties)
            logger.info(f"View '{view_name}' created.")

        # Return the updated or newly created view object
        return db.view(view_name)
    
    except ServerConnectionError as e:
        logger.error(f"Failed to connect to ArangoDB: {e}")
    except ArangoError as e:
        logger.error(f"ArangoDB error during execution: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in script execution: {e}")


def verify_view_links(view) -> bool:
    """
    Verify that the view has properly configured links.

    Args:
        view: The ArangoDB view object.

    Returns:
        bool: True if links are properly configured, False otherwise.
    """
    links = view.get('links', {})

    if links:
        logger.info(f"Links successfully added to the view: {', '.join(links.keys())}")
        return True
    else:
        logger.warning("No links found in the view properties.")
        return False

    
if __name__ == "__main__":
    # Configuration for connecting to ArangoDB and defining the view
    config = {
        "arango_config": {
            "host": "http://localhost:8529",
            "username": "root",
            "password": "openSesame",
            "db_name": "verifaix",
            "view": {
                "view_name": "microsoft_search_view",
                "force": False,
                "collections": [
                    "microsoft_products",
                    "microsoft_issues",
                    "microsoft_glossary"
                ],
                "analyzers": {
                    "microsoft_glossary": {
                        "term": ["text_en"],
                        "definition": ["text_en"],
                        "metatags": ["identity"],
                    },
                    "microsoft_products": {
                        "name": ["text_en"],
                        "description": ["text_en"],
                        "category": ["identity"],
                    },
                    "microsoft_issues": {
                        "description": ["text_en"],
                        "issue_type": ["identity"],
                        "severity": ["identity"],
                        "status": ["identity"],
                    },
                },
            }
        },
    }

    try:
        # Initialize ArangoDB client
        db = connect_to_arango_client(config["arango_config"])

        # Create or update the view
        updated_view = create_or_update_arango_view(db, config["arango_config"]["view"])

        # Verify the links in the view
        if not verify_view_links(updated_view):
            logger.error("Failed to verify view links. Exiting.")
            exit(1)

        # Print the full view properties
        logger.info("Full view properties:")
        logger.info(updated_view.get('links', {}))

    except Exception as e:
        logger.error(f"Error in script execution: {e}")
