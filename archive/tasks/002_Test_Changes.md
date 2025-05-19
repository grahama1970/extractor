# Verification Tasks for Marker Enhancements

This document outlines the tasks to verify that all enhancements listed in the CHANGELOG.md are properly implemented and working as expected.

## Page Range Processing

**Task:** Verify that Marker supports processing specific page ranges from PDFs.

**Steps:**
1. Run the conversion script with the `--page_range` parameter:
   ```bash
   python convert_single.py data/input/2505.03335v2.pdf --page_range 0-2 --output_dir ./test_results
   ```
2. Verify that only pages 0-2 are processed and included in the output
3. Test with comma-separated ranges:
   ```bash
   python convert_single.py data/input/2505.03335v2.pdf --page_range 0,3,5 --output_dir ./test_results
   ```

## Tree-Sitter Language Detection

**Task:** Verify that Tree-Sitter accurately detects programming languages in code blocks.

**Steps:**
1. Create a test document with code blocks from multiple languages
2. Run the processing script:
   ```bash
   python examples/simple/code_language_detection_debug.py
   ```
3. Check if the code blocks have the correct language identifier
4. Verify the fallback heuristic detection works when Tree-Sitter is unavailable

## LiteLLM Integration

**Task:** Verify that LiteLLM integration supports multiple models via environment variables.

**Steps:**
1. Set different model environment variables:
   ```bash
   export OPENAI_API_KEY=your_key
   ```
2. Test with different models by setting the `litellm_model` parameter:
   ```python
   # Test with OpenAI model
   service = LiteLLMService(config={"litellm_model": "openai/gpt-4o-mini"})
   
   # Test with another provider
   service = LiteLLMService(config={"litellm_model": "anthropic/claude-3-opus-20240229"})
   ```
3. Verify the correct API keys are loaded from the environment variables
4. Test the caching mechanism:
   ```bash
   python examples/simple/litellm_cache_debug.py
   ```

## Asynchronous Image Description

**Task:** Verify that async image description processor works with batching and concurrency control.

**Steps:**
1. Process a document with multiple images using async processor:
   ```python
   from marker.processors.llm.llm_image_description_async import LLMImageDescriptionAsyncProcessor
   
   # Configure with different batch sizes and concurrency limits
   processor = LLMImageDescriptionAsyncProcessor(
       config={"batch_size": 5, "max_concurrent_images": 3}
   )
   ```
2. Verify multiple images are processed concurrently
3. Check batching mechanism works as expected
4. Test with various batch sizes and concurrency limits

## Section Hierarchy and Breadcrumbs

**Task:** Verify section hierarchy and breadcrumb generation.

**Steps:**
1. Process a document with multiple nested section headers
2. Check the generated breadcrumbs for each section
3. Verify the section hierarchy is correctly represented in the output
4. Test the `get_section_breadcrumbs()` method on the Document class
5. Check that HTML output includes proper section data attributes

## ArangoDB JSON Output

**Task:** Verify ArangoDB JSON renderer produces correct output with section context.

**Steps:**
1. Configure Marker to use the ArangoDB JSON renderer:
   ```bash
   python convert_single.py data/input/2505.03335v2.pdf --output_format json --output_dir ./test_results
   ```
2. Check the output JSON structure
3. Verify each content object has complete section context
4. Test with documents having various section hierarchies
5. Use the debug script:
   ```bash
   python examples/simple/arangodb_json_debug.py
   ```

## Camelot Table Extraction

**Task:** Verify Camelot integration for table extraction fallback.

**Steps:**
1. Process a document with complex tables
2. Check how low-confidence tables trigger the Camelot fallback
3. Verify the table extraction quality with and without Camelot
4. Test the conditions that trigger Camelot fallback

## Document Object Traversal

**Task:** Verify document object traversal APIs.

**Steps:**
1. Test navigation methods on Document objects:
   ```python
   # Test methods like:
   document.get_next_block(block)
   document.get_prev_block(block)
   document.contained_blocks([BlockTypes.SectionHeader])
   ```
2. Verify section-based traversal:
   ```python
   # Test section context tracking
   section = document.contained_blocks([BlockTypes.SectionHeader])[0]
   section_content = section.get_section_content(document)
   ```
3. Test breadcrumb-based navigation
4. Verify easy document traversal for agents and humans

## General Testing

**Task:** Ensure all example and debug scripts in the `/examples` directory run without errors.

**Steps:**
1. Run each example script:
   ```bash
   for script in examples/simple/*.py; do python $script; done
   ```
2. Check for any errors or warnings
3. Verify the output of each example

## Additional Tasks

**Task:** Check any other CHANGELOG.md items not covered above.

**Steps:**
1. Review CHANGELOG.md for any missed features
2. Create and execute tests for those features
3. Document the results