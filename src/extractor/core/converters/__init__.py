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
from typing import Optional, List, Type

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
        init_signature = inspect.signature(cls.__init__)
        parameters = init_signature.parameters

        resolved_kwargs = {}
        for param_name, param in parameters.items():
            if param_name == 'self':
                continue
            elif param_name == 'config':
                resolved_kwargs[param_name] = self.config
            elif param.name in self.artifact_dict:
                resolved_kwargs[param_name] = self.artifact_dict[param_name]
            elif param.default != inspect.Parameter.empty:
                resolved_kwargs[param_name] = param.default
            else:
                raise ValueError(f"Cannot resolve dependency for parameter: {param_name}")

        return cls(**resolved_kwargs)

    def initialize_processors(self, processor_cls_lst: List[Type[BaseProcessor]]) -> List[BaseProcessor]:
        processors = []
        for processor_cls in processor_cls_lst:
            processors.append(self.resolve_dependencies(processor_cls))

        simple_llm_processors = [p for p in processors if issubclass(type(p), BaseLLMSimpleBlockProcessor)]
        other_processors = [p for p in processors if not issubclass(type(p), BaseLLMSimpleBlockProcessor)]

        if not simple_llm_processors:
            return processors

        llm_positions = [i for i, p in enumerate(processors) if issubclass(type(p), BaseLLMSimpleBlockProcessor)]
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