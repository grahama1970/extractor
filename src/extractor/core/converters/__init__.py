"""
Module: __init__.py
Description: Base converter classes for document processing

External Dependencies:
- pydantic: https://docs.pydantic.dev/
- inspect: https://docs.python.org/3/library/inspect.html

Sample Input:
>>> config = {"use_llm": False, "max_pages": 10}
>>> converter = BaseConverter(config)

Expected Output:
>>> # Provides base converter functionality
>>> # Subclasses implement specific conversion logic

Example Usage:
>>> from extractor.core.converters import BaseConverter
>>> class MyConverter(BaseConverter):
...     def __call__(self, filepath):
...         return f"Processing: {filepath}"
>>> converter = MyConverter({"debug": True})
"""

import inspect
import os
from typing import Optional, List, Type, get_origin, get_args

from pydantic import BaseModel

from extractor.core.processors import BaseProcessor
from extractor.core.processors.llm import BaseLLMSimpleBlockProcessor
from extractor.core.processors.llm.llm_meta import LLMSimpleBlockMetaProcessor
from extractor.core.util import assign_config, download_font


class BaseConverter:
    def __init__(self, config: Optional[BaseModel | dict] = None):
        assign_config(self, config)
        self.config = config
        self.llm_service = None

        # Download render font, needed for some providers
        download_font()

    def __call__(self, *args, **kwargs):
        raise NotImplementedError

    def resolve_dependencies(self, cls):
        """Robust dependency resolver.

        - Pass through artifact_dict values even if None (for optional params).
        - Consider parameter optional if it has a default or Optional/Union[..., None] annotation.
        - Hard-fail only for required params missing from artifact_dict.
        - On failure, print debug info when CONVERTER_DEBUG is set or config enables diagnostics.
        """
        sig = inspect.signature(cls.__init__)
        params = sig.parameters
        resolved = {}
        missing_required: List[str] = []
        artifact = getattr(self, "artifact_dict", {}) or {}
        artifact_keys = set(artifact.keys())

        def _is_optional(p: inspect.Parameter) -> bool:
            if p.default != inspect.Parameter.empty:
                return True
            ann = p.annotation
            if ann is inspect._empty:
                return False
            origin = get_origin(ann)
            # Optional[T]
            if origin is Optional:
                return True
            # Union[..., None]
            if origin is not None:
                args = get_args(ann)
                if any(a is type(None) for a in args):
                    return True
            return False

        for name, p in params.items():
            if name == "self":
                continue
            if name == "config":
                resolved[name] = self.config
                continue
            if name == "llm_service":
                resolved[name] = self.llm_service
                continue
            if name in artifact_keys:
                # Honor provided artifact value (even None for optional params)
                resolved[name] = artifact.get(name)
                continue
            if p.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL):
                continue
            if p.default != inspect.Parameter.empty:
                resolved[name] = p.default
                continue
            if _is_optional(p):
                resolved[name] = None
                continue
            # Required and missing
            missing_required.append(name)

        if missing_required:
            debug = False
            try:
                debug = bool(os.getenv("CONVERTER_DEBUG")) or bool(getattr(self, "config", {}) or {}).get(
                    "diagnostics_debug", False
                )
            except Exception:
                debug = False
            if debug:
                print(
                    f"[converter.resolve_dependencies] Missing for {cls.__name__}: {missing_required}; "
                    f"artifact keys={sorted(artifact_keys)}"
                )
            raise ValueError(
                f"Cannot resolve dependency for parameter(s): {', '.join(missing_required)} (class={cls.__name__})"
            )

        return cls(**resolved)

    def initialize_processors(
        self, processor_cls_lst: List[Type[BaseProcessor]]
    ) -> List[BaseProcessor]:
        processors = []
        for processor_cls in processor_cls_lst:
            processors.append(self.resolve_dependencies(processor_cls))

        simple_llm_processors = [
            p for p in processors if issubclass(type(p), BaseLLMSimpleBlockProcessor)
        ]
        other_processors = [
            p for p in processors if not issubclass(type(p), BaseLLMSimpleBlockProcessor)
        ]

        if not simple_llm_processors:
            return processors

        llm_positions = [
            i for i, p in enumerate(processors) if issubclass(type(p), BaseLLMSimpleBlockProcessor)
        ]
        insert_position = max(0, llm_positions[-1] - len(simple_llm_processors) + 1)

        meta_processor = LLMSimpleBlockMetaProcessor(
            processor_lst=simple_llm_processors,
            llm_service=self.llm_service,
            config=self.config,
        )
        other_processors.insert(insert_position, meta_processor)
        return other_processors


if __name__ == "__main__":
    # Test base converter functionality
    print("🧪 Testing Base Converter")
    print("=" * 50)

    # Test 1: Create base converter
    print("\n📝 Test 1: Initialize Base Converter")
    try:
        config = {"use_llm": False, "max_pages": 10}
        converter = BaseConverter(config)
        print("✅ Base converter initialized")
        print(f"   - Config: {converter.config}")
        print(f"   - LLM service: {converter.llm_service}")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")

    # Test 2: Test dependency resolution
    print("\n📝 Test 2: Dependency Resolution")
    try:
        # Create a test class
        class TestProcessor:
            def __init__(self, config=None, llm_service=None):
                self.config = config
                self.llm_service = llm_service

        converter = BaseConverter({"test": True})
        converter.artifact_dict = {"llm_service": None}

        # Resolve dependencies
        processor = converter.resolve_dependencies(TestProcessor)
        print("✅ Dependency resolution works")
        print(f"   - Processor config: {processor.config}")
        print(f"   - Processor llm_service: {processor.llm_service}")
    except Exception as e:
        print(f"❌ Dependency resolution failed: {e}")

    # Test 3: Test processor initialization
    print("\n📝 Test 3: Processor Initialization")
    try:
        from extractor.core.processors.text import TextProcessor

        converter = BaseConverter({})
        converter.artifact_dict = {}

        # Initialize processors
        processors = converter.initialize_processors([TextProcessor])
        print("✅ Processor initialization works")
        print(f"   - Initialized {len(processors)} processor(s)")
        if processors:
            print(f"   - First processor: {processors[0].__class__.__name__}")
    except Exception as e:
        print(f"⚠️  Processor initialization: {e}")
        print("   - This may require full processor setup")

    # Test 4: Test not implemented call
    print("\n📝 Test 4: Call Method Check")
    try:
        converter = BaseConverter({})
        converter("test.pdf")
        print("❌ Should have raised NotImplementedError")
    except NotImplementedError:
        print("✅ Call method properly raises NotImplementedError")
        print("   - Subclasses must implement __call__")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

    print("\n" + "=" * 50)
    print("✅ Base converter validation complete")
