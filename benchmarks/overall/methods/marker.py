"""
Module: marker.py
Description: Document processing and marking functionality

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import os
import tempfile
import time

from benchmarks.overall.methods import BaseMethod, BenchmarkResult
from marker.config.parser import ConfigParser
from marker.converters.pdf import PdfConverter


class MarkerMethod(BaseMethod):
    model_dict: dict = None
    use_llm: bool = False

    def __call__(self, sample) -> BenchmarkResult:
        pdf_bytes = sample["pdf"]  # This is a single page PDF
        parser = ConfigParser({
                "page_range": "0",
                "disable_tqdm": True,
                "use_llm": self.use_llm,
                "redo_inline_math": self.use_llm,
                "llm_service": "marker.services.litellm.LiteLLMService",
            })

        block_converter = PdfConverter(
            artifact_dict=self.model_dict,
            config=parser.generate_config_dict(),
            llm_service=parser.get_llm_service()
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", mode="wb") as f:
            f.write(pdf_bytes)
            start = time.time()
            rendered = block_converter(f.name)
            total = time.time() - start

        return {
            "markdown": rendered.markdown,
            "time": total
        }

