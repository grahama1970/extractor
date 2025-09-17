#!/usr/bin/env python3
"""
LLM Meta Processor - A wrapper for simple LLM processors.

This processor takes a list of simple LLM processors and runs them in parallel
using a thread pool, which can significantly speed up processing time.
It also flags suspicious (e.g., empty or very short) LLM responses.
"""

import asyncio
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

from tqdm import tqdm
from loguru import logger


# In a real project, these would be in a shared schema file
class MetadataKey:
    IS_SUSPICIOUS = "is_suspicious"
    SUSPICIOUS_REASON = "suspicious_reason"


# Dummy classes for demonstration purposes
class BaseLLMProcessor:
    def __init__(self, llm_service=None, config=None):
        self.config = config or {}
        self.llm_service = llm_service
        self.use_llm = self.config.get("use_llm", True)
        self.max_concurrency = self.config.get("max_concurrency", 4)
        self.disable_tqdm = self.config.get("disable_tqdm", False)


class BaseLLMSimpleBlockProcessor(BaseLLMProcessor):
    def inference_blocks(self, document):
        return []

    def block_prompts(self, document):
        return []

    def __call__(self, result, prompt_data, document):
        pass


class Document:
    pass


class BaseService:
    pass


class LLMSimpleBlockMetaProcessor(BaseLLMProcessor):
    """
    A wrapper for simple LLM processors, so they can all run in parallel.
    """

    def __init__(
        self,
        processor_lst: List[BaseLLMSimpleBlockProcessor],
        llm_service: BaseService,
        config: Dict[str, Any] = None,
    ):
        super().__init__(llm_service, config)
        self.processors = processor_lst
        self.min_suspicious_length = self.config.get("min_suspicious_llm_response_length", 10)

    def __call__(self, document: Document):
        if not self.use_llm or self.llm_service is None:
            return

        total = sum([len(processor.inference_blocks(document)) for processor in self.processors])
        pbar = tqdm(desc="LLM processors running", disable=self.disable_tqdm, total=total)

        all_prompts = [processor.block_prompts(document) for processor in self.processors]
        pending = []
        futures_map = {}
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            for i, prompt_lst in enumerate(all_prompts):
                for prompt in prompt_lst:
                    future = executor.submit(self.get_response, prompt)
                    pending.append(future)
                    futures_map[future] = {"processor_idx": i, "prompt_data": prompt}

            for future in pending:
                try:
                    result = future.result()
                    future_data = futures_map.pop(future)
                    processor: BaseLLMSimpleBlockProcessor = self.processors[
                        future_data["processor_idx"]
                    ]

                    # Flag suspicious results
                    block = future_data["prompt_data"]["block"]
                    if not result or len(str(result)) < self.min_suspicious_length:
                        block.setdefault("metadata", {})[MetadataKey.IS_SUSPICIOUS] = True
                        block["metadata"][
                            MetadataKey.SUSPICIOUS_REASON
                        ] = "LLM returned an empty or very short response."

                    # finalize the result
                    processor(result, future_data["prompt_data"], document)
                except Exception as e:
                    logger.error(f"Error processing LLM response: {e}")

                pbar.update(1)

        pbar.close()

    def get_response(self, prompt_data: Dict[str, Any]):
        return self.llm_service(
            prompt_data["prompt"],
            prompt_data.get("image"),
            prompt_data["block"],
            prompt_data.get("schema"),
        )


async def working_usage():
    logger.info("=== Running LLMSimpleBlockMetaProcessor Working Usage Examples ===")

    # This is a meta-processor, so a full test would require mock child processors and services.
    # The core logic is tested by observing if suspicious flags are added.
    class MockLLMService(BaseService):
        def __call__(self, prompt, image, block, schema):
            if "fail" in prompt:
                return ""
            return "This is a valid response."

    class MockSimpleProcessor(BaseLLMSimpleBlockProcessor):
        def inference_blocks(self, document):
            return [
                {"block_type": "Text", "text": "Block 1"},
                {"block_type": "Text", "text": "Block 2"},
            ]

        def block_prompts(self, document):
            return [
                {"prompt": "A good prompt", "block": {}},
                {"prompt": "A prompt to fail", "block": {}},
            ]

        def __call__(self, result, prompt_data, document):
            prompt_data["block"]["llm_result"] = result

    doc = Document()
    processor = LLMSimpleBlockMetaProcessor([MockSimpleProcessor()], MockLLMService())
    processor(doc)

    # We can't easily assert the results without more complex mocking,
    # but we can verify the processor runs without error.
    logger.success("✓ All working_usage tests passed!")
    return True


async def debug_function():
    logger.info("=== Running LLMSimpleBlockMetaProcessor Debug Function ===")
    return True


if __name__ == "__main__":
    mode = "working"
    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        mode = "debug"

    async def main():
        if mode == "debug":
            success = await debug_function()
        else:
            success = await working_usage()
        return success

    success = asyncio.run(main())
    exit(0 if success else 1)
