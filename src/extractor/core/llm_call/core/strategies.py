"""Strategy registry and loader for validation strategies.
Module: strategies.py

This module provides a pluggable system for validation strategies.
"""

import importlib
import importlib.util
import inspect
from pathlib import Path
from typing import Any, Dict, List, Type, Optional

from loguru import logger

from extractor.core.llm_call.core.base import ValidationStrategy, BaseValidator


class StrategyRegistry:
    """Registry for validation strategies.
    
    Maintains a central registry of available validation strategies and provides
    methods for registration, discovery, and instantiation.
    """
    
    def __init__(self):
        self._strategies: Dict[str, Type[ValidationStrategy]] = {}
        self._instances: Dict[str, ValidationStrategy] = {}
        self._strategy_info: Dict[str, Dict[str, Any]] = {}
    
    def register(self, name: str, strategy_class: Type[ValidationStrategy], **metadata) -> None:
        """Register a validation strategy.
        
        Args:
            name: Unique name for the strategy
            strategy_class: The strategy class to register
            **metadata: Additional metadata about the strategy
        """
        if name in self._strategies:
            logger.warning(f"Overwriting existing strategy: {name}")
        
        self._strategies[name] = strategy_class
        self._strategy_info[name] = {
            "class": strategy_class,
            "module": strategy_class.__module__,
            "doc": inspect.getdoc(strategy_class),
            **metadata
        }
        logger.debug(f"Registered strategy: {name}")
    
    def unregister(self, name: str) -> None:
        """Unregister a validation strategy."""
        if name in self._strategies:
            del self._strategies[name]
            if name in self._instances:
                del self._instances[name]
            if name in self._strategy_info:
                del self._strategy_info[name]
            logger.debug(f"Unregistered strategy: {name}")
    
    def get(self, name: str, **kwargs) -> ValidationStrategy:
        """Get a strategy instance.
        
        Args:
            name: Name of the strategy
            **kwargs: Arguments passed to strategy constructor
            
        Returns:
            ValidationStrategy instance
            
        Raises:
            ValueError: If strategy not found
        """
        # Check if we already have an instance with these args
        instance_key = f"{name}:{str(kwargs)}"
        
        if instance_key in self._instances:
            return self._instances[instance_key]
        
        if name not in self._strategies:
            available = ", ".join(self._strategies.keys())
            raise ValueError(f"Strategy '{name}' not found. Available: {available}")
        
        # Create new instance
        strategy_class = self._strategies[name]
        try:
            instance = strategy_class(**kwargs)
            self._instances[instance_key] = instance
            logger.debug(f"Created instance of strategy: {name}")
            return instance
        except Exception as e:
            logger.error(f"Failed to instantiate strategy '{name}': {e}")
            raise
    
    def list_all(self) -> List[Dict[str, Any]]:
        """List all registered strategies with their metadata."""
        return [
            {
                "name": name,
                "class": info["class"].__name__,
                "module": info["module"],
                "description": info["doc"],
                **{k: v for k, v in info.items() if k not in ["class", "module", "doc"]}
            }
            for name, info in self._strategy_info.items()
        ]
    
    def discover_strategies(self, path: Path) -> None:
        """Discover and load strategies from a directory.
        
        Args:
            path: Directory path to search for strategy modules
        """
        if not path.is_dir():
            logger.warning(f"Strategy path is not a directory: {path}")
            return
        
        logger.info(f"Discovering strategies in: {path}")
        
        for py_file in path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            
            try:
                # Import the module
                module_name = py_file.stem
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Find strategy classes in the module
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, BaseValidator) and
                            obj != BaseValidator):
                            
                            # Check if class has the @validator decorator
                            if hasattr(obj, "_validator_name"):
                                strategy_name = obj._validator_name
                            else:
                                strategy_name = name.lower()
                            
                            self.register(strategy_name, obj)
                            logger.info(f"Discovered strategy: {strategy_name} in {py_file.name}")
                            
            except Exception as e:
                logger.error(f"Failed to load strategies from {py_file}: {e}")
    
    def load_from_file(self, file_path: Path, name: Optional[str] = None) -> None:
        """Load a specific validator from a file.
        
        Args:
            file_path: Path to the Python file containing the validator
            name: Optional name to register the validator as
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        module_name = file_path.stem
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find validator classes
            validators_found = 0
            for obj_name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, BaseValidator) and
                    obj != BaseValidator):
                    
                    if name:
                        self.register(name, obj)
                    elif hasattr(obj, "_validator_name"):
                        self.register(obj._validator_name, obj)
                    else:
                        self.register(obj_name.lower(), obj)
                    
                    validators_found += 1
            
            if validators_found == 0:
                raise ValueError(f"No validators found in {file_path}")
            
            logger.info(f"Loaded {validators_found} validators from {file_path}")


# Global registry instance
registry = StrategyRegistry()


def validator(name: str):
    """Decorator to register a validator with the global registry.
    
    Args:
        name: Name to register the validator under
        
    Example:
        @validator("my_validator")
        class MyValidator(BaseValidator):
            ...
    """
    def decorator(cls):
        # Store the validator name on the class
        cls._validator_name = name
        
        # Register with global registry
        registry.register(name, cls)
        
        return cls
    
    return decorator


# Discover built-in validators on module load
try:
    builtin_validators_path = Path(__file__).parent.parent / "validators"
    if builtin_validators_path.exists():
        registry.discover_strategies(builtin_validators_path)
except Exception as e:
    logger.warning(f"Failed to discover built-in validators: {e}")