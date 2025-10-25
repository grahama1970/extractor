#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Smoke: ensure SciLLM-first import path works and no hard litellm import
breaks runtime for key modules.
"""
import sys
sys.path.insert(0,'src')

failed = []
mods = [
    'extractor.pipeline.steps.06a_title_caption_enricher',
    'extractor.pipeline.utils.llm_utils',
]
for m in mods:
    try:
        __import__(m)
    except Exception as e:
        failed.append((m, str(e)))

print({"ok": not failed, "failed": failed})
