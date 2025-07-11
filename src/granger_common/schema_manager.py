#!/usr/bin/env python3
"""
Module: schema_manager.py
Description: Standardized schema versioning and migration for module communication

This ensures all Granger modules can communicate consistently even as schemas evolve.

External Dependencies:
- pydantic: Data validation and settings management
- typing: Built-in type hints
- semver: Semantic versioning

Sample Input:
>>> schema = SchemaManager()
>>> data_v1 = {"id": "123", "name": "test", "data": "content"}
>>> data_v2 = schema.migrate(data_v1, from_version="1.0", to_version="2.0")

Expected Output:
>>> {
...     "id": "123",
...     "name": "test", 
...     "payload": {"data": "content"},
...     "metadata": {"migrated_from": "1.0", "migrated_at": "2024-06-09T10:00:00"},
...     "version": "2.0"
... }

Example Usage:
>>> from granger_common.schema_manager import SchemaManager, Message
>>> 
>>> # Sender (using v2.0)
>>> message = Message(
...     id="123",
...     name="document_processed",
...     payload={"text": "content"},
...     metadata={"source": "marker"}
... )
>>> 
>>> # Receiver (expects v1.0)
>>> schema = SchemaManager()
>>> v1_data = schema.downgrade(message.dict(), to_version="1.0")
"""

from typing import Dict, Any, Optional, List, Union, Callable
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
from loguru import logger
import json


class SchemaVersion(str, Enum):
    """Supported schema versions."""
    V1_0 = "1.0"
    V1_1 = "1.1"
    V2_0 = "2.0"
    V2_1 = "2.1"


class BaseMessage(BaseModel):
    """Base message model that all versions inherit from."""
    id: str
    name: str
    version: str = SchemaVersion.V2_1.value
    
    class Config:
        use_enum_values = True


class MessageV1(BaseMessage):
    """Version 1.0 message schema."""
    version: str = SchemaVersion.V1_0.value
    data: Any
    

class MessageV1_1(BaseMessage):
    """Version 1.1 message schema - added timestamp."""
    version: str = SchemaVersion.V1_1.value
    data: Any
    timestamp: datetime = Field(default_factory=datetime.now)


class MessageV2(BaseMessage):
    """Version 2.0 message schema - restructured with payload/metadata."""
    version: str = SchemaVersion.V2_0.value
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class MessageV2_1(MessageV2):
    """Version 2.1 message schema - added routing info."""
    version: str = SchemaVersion.V2_1.value
    routing: Optional[Dict[str, Any]] = Field(default_factory=dict)


# Type alias for current message version
Message = MessageV2_1


class SchemaMigration:
    """Handles migration between schema versions."""
    
    def __init__(self):
        # Define migration functions
        self.migrations = {
            ("1.0", "1.1"): self._migrate_1_0_to_1_1,
            ("1.1", "2.0"): self._migrate_1_1_to_2_0,
            ("2.0", "2.1"): self._migrate_2_0_to_2_1,
        }
        
        self.downgrades = {
            ("1.1", "1.0"): self._downgrade_1_1_to_1_0,
            ("2.0", "1.1"): self._downgrade_2_0_to_1_1,
            ("2.1", "2.0"): self._downgrade_2_1_to_2_0,
        }
    
    def _migrate_1_0_to_1_1(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add timestamp to v1.0 data."""
        data["timestamp"] = datetime.now().isoformat()
        data["version"] = "1.1"
        logger.debug("Migrated from 1.0 to 1.1: added timestamp")
        return data
    
    def _migrate_1_1_to_2_0(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Restructure data into payload/metadata format."""
        # Extract core data
        old_data = data.pop("data", {})
        timestamp = data.get("timestamp", datetime.now().isoformat())
        
        # Restructure
        data["payload"] = {"data": old_data} if not isinstance(old_data, dict) else old_data
        data["metadata"] = {
            "migrated_from": "1.1",
            "migrated_at": datetime.now().isoformat(),
            "original_timestamp": timestamp
        }
        data["version"] = "2.0"
        
        logger.debug("Migrated from 1.1 to 2.0: restructured to payload/metadata")
        return data
    
    def _migrate_2_0_to_2_1(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add routing information."""
        data["routing"] = data.get("routing", {})
        data["version"] = "2.1"
        logger.debug("Migrated from 2.0 to 2.1: added routing")
        return data
    
    def _downgrade_1_1_to_1_0(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove timestamp."""
        data.pop("timestamp", None)
        data["version"] = "1.0"
        logger.debug("Downgraded from 1.1 to 1.0: removed timestamp")
        return data
    
    def _downgrade_2_0_to_1_1(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten payload back to data field."""
        payload = data.pop("payload", {})
        metadata = data.pop("metadata", {})
        
        # Flatten payload
        data["data"] = payload
        data["timestamp"] = data.get("timestamp", datetime.now().isoformat())
        data["version"] = "1.1"
        
        # Store metadata in data if important
        if metadata.get("important_fields"):
            data["data"]["_metadata"] = metadata
        
        logger.debug("Downgraded from 2.0 to 1.1: flattened payload to data")
        return data
    
    def _downgrade_2_1_to_2_0(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove routing information."""
        data.pop("routing", None)
        data["version"] = "2.0"
        logger.debug("Downgraded from 2.1 to 2.0: removed routing")
        return data


class SchemaManager:
    """
    Manages schema versioning and migration for all Granger modules.
    
    This ensures backward and forward compatibility between modules
    using different schema versions.
    """
    
    def __init__(self):
        self.migrator = SchemaMigration()
        self.version_order = ["1.0", "1.1", "2.0", "2.1"]
        
        # Model mapping
        self.models = {
            "1.0": MessageV1,
            "1.1": MessageV1_1,
            "2.0": MessageV2,
            "2.1": MessageV2_1
        }
    
    def get_version_path(self, from_version: str, to_version: str) -> List[str]:
        """Get migration path between versions."""
        try:
            from_idx = self.version_order.index(from_version)
            to_idx = self.version_order.index(to_version)
            
            if from_idx < to_idx:
                # Upgrade path
                return self.version_order[from_idx:to_idx + 1]
            else:
                # Downgrade path
                return self.version_order[to_idx:from_idx + 1][::-1]
                
        except ValueError as e:
            raise ValueError(f"Unknown version: {e}")
    
    def migrate(
        self, 
        data: Dict[str, Any], 
        from_version: Optional[str] = None,
        to_version: str = SchemaVersion.V2_1.value
    ) -> Dict[str, Any]:
        """
        Migrate data between schema versions.
        
        Args:
            data: Data to migrate
            from_version: Source version (auto-detected if None)
            to_version: Target version
            
        Returns:
            Migrated data
        """
        # Auto-detect version if not provided
        if from_version is None:
            from_version = data.get("version", "1.0")
        
        if from_version == to_version:
            logger.debug(f"No migration needed, already at version {to_version}")
            return data
        
        # Get migration path
        path = self.get_version_path(from_version, to_version)
        logger.info(f"Migration path: {' -> '.join(path)}")
        
        # Apply migrations
        current_data = data.copy()
        for i in range(len(path) - 1):
            current_version = path[i]
            next_version = path[i + 1]
            
            if self.version_order.index(next_version) > self.version_order.index(current_version):
                # Upgrade
                migration_key = (current_version, next_version)
                if migration_key in self.migrator.migrations:
                    current_data = self.migrator.migrations[migration_key](current_data)
            else:
                # Downgrade
                migration_key = (current_version, next_version)
                if migration_key in self.migrator.downgrades:
                    current_data = self.migrator.downgrades[migration_key](current_data)
        
        return current_data
    
    def validate(self, data: Dict[str, Any], version: Optional[str] = None) -> BaseMessage:
        """
        Validate data against schema version.
        
        Args:
            data: Data to validate
            version: Version to validate against (auto-detected if None)
            
        Returns:
            Validated message model
        """
        if version is None:
            version = data.get("version", "2.1")
        
        model_class = self.models.get(version)
        if not model_class:
            raise ValueError(f"Unknown schema version: {version}")
        
        return model_class(**data)
    
    def ensure_compatibility(
        self, 
        sender_data: Dict[str, Any],
        receiver_version: str
    ) -> Dict[str, Any]:
        """
        Ensure data is compatible with receiver's expected version.
        
        Args:
            sender_data: Data from sender
            receiver_version: Version expected by receiver
            
        Returns:
            Data compatible with receiver's version
        """
        sender_version = sender_data.get("version", "1.0")
        
        if sender_version == receiver_version:
            return sender_data
        
        logger.info(
            f"Ensuring compatibility: {sender_version} -> {receiver_version}"
        )
        
        return self.migrate(sender_data, sender_version, receiver_version)
    
    def get_schema_info(self, version: str) -> Dict[str, Any]:
        """Get information about a schema version."""
        model_class = self.models.get(version)
        if not model_class:
            raise ValueError(f"Unknown schema version: {version}")
        
        # Get field information
        fields = {}
        for field_name, field_info in model_class.__fields__.items():
            fields[field_name] = {
                "type": str(field_info.annotation),
                "required": field_info.required,
                "default": field_info.default if not field_info.required else None
            }
        
        return {
            "version": version,
            "fields": fields,
            "model": model_class.__name__
        }


# Global schema manager instance
schema_manager = SchemaManager()


def create_message(
    id: str,
    name: str, 
    payload: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    routing: Optional[Dict[str, Any]] = None,
    version: str = SchemaVersion.V2_1.value
) -> Message:
    """
    Helper to create a message with current schema version.
    
    Args:
        id: Unique message identifier
        name: Message type/name
        payload: Message payload data
        metadata: Optional metadata
        routing: Optional routing information
        version: Schema version to use
        
    Returns:
        Message instance
    """
    return Message(
        id=id,
        name=name,
        payload=payload,
        metadata=metadata or {},
        routing=routing or {},
        version=version
    )


if __name__ == "__main__":
    # Validation tests
    print("🧪 Testing SchemaManager...")
    
    manager = SchemaManager()
    
    # Test 1: Version detection and migration
    print("\nTest 1: Migration from v1.0 to v2.1")
    v1_data = {
        "id": "123",
        "name": "test_message",
        "data": {"content": "Hello World"},
        "version": "1.0"
    }
    
    v2_data = manager.migrate(v1_data, to_version="2.1")
    print(f"  Original (v1.0): {json.dumps(v1_data, indent=2)}")
    print(f"  Migrated (v2.1): {json.dumps(v2_data, default=str, indent=2)}")
    
    # Test 2: Downgrade
    print("\nTest 2: Downgrade from v2.1 to v1.0")
    v1_again = manager.migrate(v2_data, to_version="1.0")
    print(f"  Downgraded (v1.0): {json.dumps(v1_again, default=str, indent=2)}")
    
    # Test 3: Compatibility ensure
    print("\nTest 3: Ensure compatibility")
    sender_msg = create_message(
        id="456",
        name="document_ready",
        payload={"doc_id": "abc123", "pages": 50},
        metadata={"source": "marker"}
    )
    
    # Receiver expects v1.1
    compatible_data = manager.ensure_compatibility(
        sender_msg.dict(), 
        receiver_version="1.1"
    )
    print(f"  Sender (v2.1): {sender_msg.version}")
    print(f"  Receiver needs: v1.1")
    print(f"  Compatible data: {json.dumps(compatible_data, default=str, indent=2)}")
    
    # Test 4: Schema info
    print("\nTest 4: Schema information")
    for version in ["1.0", "1.1", "2.0", "2.1"]:
        info = manager.get_schema_info(version)
        print(f"  Version {version}: {len(info['fields'])} fields")
    
    print("\n✅ SchemaManager validation complete!")