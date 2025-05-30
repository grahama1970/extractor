import asyncio
from pydantic import BaseModel
from tqdm import tqdm
import litellm

from marker.core.processors.llm import PromptData, BaseLLMSimpleBlockProcessor, BlockData
from marker.core.schema import BlockTypes
from marker.core.schema.document import Document
from marker.core.services.litellm import LiteLLMService
from marker.core.services.utils.log_utils import log_api_request, log_api_response, log_api_error

from typing import Annotated, List, Dict, Any, Optional


class LLMImageDescriptionProcessor(BaseLLMSimpleBlockProcessor):
    block_types = (BlockTypes.Picture, BlockTypes.Figure,)
    extract_images: Annotated[
        bool,
        "Extract images from the document."
    ] = True
    image_description_prompt: Annotated[
        str,
        "The prompt to use for generating image descriptions.",
        "Default is a string containing the prompt."
    ] = """You are a document analysis expert who specializes in creating text descriptions for images.
You will receive an image of a picture or figure.  Your job will be to create a short description of the image.
**Instructions:**
1. Carefully examine the provided image.
2. Analyze any text that was extracted from within the image.
3. Output a faithful description of the image.  Make sure there is enough specific detail to accurately reconstruct the image.  If the image is a figure or contains numeric data, include the numeric data in the output.
**Example:**
Input:
```text
"Fruit Preference Survey"
20, 15, 10
Apples, Bananas, Oranges
```
Output:
In this figure, a bar chart titled "Fruit Preference Survey" is showing the number of people who prefer different types of fruits.  The x-axis shows the types of fruits, and the y-axis shows the number of people.  The bar chart shows that most people prefer apples, followed by bananas and oranges.  20 people prefer apples, 15 people prefer bananas, and 10 people prefer oranges.
**Input:**
```text
{raw_text}
```
"""
    use_async_batch: Annotated[
        bool,
        "Whether to use async batch processing for image descriptions."
    ] = True
    max_batch_size: Annotated[
        int,
        "Maximum number of images to process in a single batch."
    ] = 5
    detail_level: Annotated[
        str,
        "Level of detail in the image descriptions: 'brief', 'standard', or 'detailed'."
    ] = "standard"
    litellm_model: Annotated[
        Optional[str],
        "The LiteLLM model to use in provider/model format. If None, will use the LiteLLM service model."
    ] = None

    def inference_blocks(self, document: Document) -> List[BlockData]:
        blocks = super().inference_blocks(document)
        if self.extract_images:
            return []
        return blocks

    def block_prompts(self, document: Document) -> List[PromptData]:
        prompt_data = []
        for block_data in self.inference_blocks(document):
            block = block_data["block"]
            # Adjust prompt based on detail level
            detail_instruction = ""
            if self.detail_level == "brief":
                detail_instruction = "Keep your description concise (1-2 sentences)."
            elif self.detail_level == "detailed":
                detail_instruction = "Provide a detailed description including all visible elements and their relationships."

            modified_prompt = self.image_description_prompt.replace("{raw_text}", block.raw_text(document))
            if detail_instruction:
                modified_prompt = modified_prompt.replace("3. Output a faithful description", f"3. {detail_instruction} Output a faithful description")

            image = self.extract_image(document, block)

            prompt_data.append({
                "prompt": modified_prompt,
                "image": image,
                "block": block,
                "schema": ImageSchema,
                "page": block_data["page"]
            })

        return prompt_data

    def __call__(self, document: Document):
        if not self.use_llm or not hasattr(document, "llm_service") or document.llm_service is None:
            return

        # Get all blocks to process
        inference_blocks = []
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                inference_blocks.append({
                    "page": page,
                    "block": block
                })

        if not inference_blocks:
            return

        # Process blocks with async batch if enabled
        if self.use_async_batch:
            # Ensure we have a LiteLLM service
            llm_service = document.llm_service
            if not isinstance(llm_service, LiteLLMService):
                print("Warning: Async batch processing requires LiteLLMService. Falling back to sequential processing.")
                self._process_sequentially(document, inference_blocks)
                return

            try:
                # Process all blocks in async batches using a new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._process_async_batch(document, inference_blocks, llm_service))
                finally:
                    loop.close()
            except Exception as e:
                print(f"Error in async batch processing: {e}. Falling back to sequential processing.")
                self._process_sequentially(document, inference_blocks)
        else:
            # Process sequentially
            self._process_sequentially(document, inference_blocks)

    def _process_sequentially(self, document: Document, blocks: List[dict]):
        """Process image blocks sequentially using the standard method."""
        total_blocks = len(blocks)
        if total_blocks == 0:
            return

        with tqdm(total=total_blocks, desc="Processing images", disable=getattr(self, "disable_tqdm", False)) as pbar:
            for block_data in blocks:
                block = block_data["block"]
                page = block_data["page"]

                prompt = self.image_description_prompt.replace("{raw_text}", block.raw_text(document))
                image = self.extract_image(document, block)

                try:
                    response = document.llm_service(
                        prompt,
                        image,
                        block,
                        ImageSchema
                    )
                    self.rewrite_block(response, {"block": block}, document)
                except Exception as e:
                    print(f"Error processing image: {e}")
                    block.update_metadata(llm_error_count=1)

                pbar.update(1)

    async def _process_async_batch(self, document: Document, blocks: List[dict], llm_service: LiteLLMService):
        """Process images in async batches using LiteLLM's acompletion feature."""
        total_blocks = len(blocks)

        # Prepare all the prompts and images
        all_prompts = []

        for block_data in blocks:
            block = block_data["block"]
            prompt = self.image_description_prompt.replace("{raw_text}", block.raw_text(document))
            image = self.extract_image(document, block)

            # Prepare the image data
            image_data = llm_service.prepare_images(image)

            # Prepare the messages
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that always responds with valid JSON. Your response must be compatible with the provided schema and contain the word 'json' to ensure proper formatting."
                },
                {
                    "role": "user",
                    "content": [
                        *image_data,
                        {"type": "text", "text": prompt},
                    ],
                }
            ]

            all_prompts.append({
                "messages": messages,
                "block": block,
            })

        # Process in batches
        batch_size = min(self.max_batch_size, total_blocks)
        results = {}

        with tqdm(total=total_blocks, desc="Processing images", disable=getattr(self, "disable_tqdm", False)) as pbar:
            for i in range(0, total_blocks, batch_size):
                batch = all_prompts[i:i+batch_size]
                batch_tasks = []

                for item in batch:
                    # Get the LiteLLM model to use
                    model = self.litellm_model or llm_service.litellm_model

                    # Create the completion kwargs
                    completion_kwargs = {
                        "model": model,
                        "messages": item["messages"],
                        "api_key": llm_service.get_api_key(model),
                    }

                    # Add response_format if it's an OpenAI model
                    if model.startswith("openai/") or model.startswith("azure/"):
                        completion_kwargs["response_format"] = {"type": "json_object"}

                    # Log the request
                    log_api_request("LiteLLM Batch", completion_kwargs)

                    # Create the task
                    task = self._async_completion(completion_kwargs, item["block"])
                    batch_tasks.append(task)

                # Run all tasks concurrently
                batch_results = await asyncio.gather(*batch_tasks)

                # Process results
                for result in batch_results:
                    if result and "block" in result and "response" in result:
                        block = result["block"]
                        response = result["response"]

                        if response:
                            try:
                                # Extract and process response
                                response_text = response.choices[0].message.content
                                from marker.core.services.utils.json_utils import clean_json_string
                                json_data = clean_json_string(response_text, return_dict=True)

                                # Update the block with the description
                                if json_data and "image_description" in json_data:
                                    block.description = json_data["image_description"]
                                    # Update token usage metadata
                                    if hasattr(response, "usage") and response.usage:
                                        block.update_metadata(
                                            llm_tokens_used=response.usage.total_tokens,
                                            llm_request_count=1
                                        )
                            except Exception as e:
                                print(f"Error processing response: {e}")
                                block.update_metadata(llm_error_count=1)

                    pbar.update(1)

    async def _async_completion(self, completion_kwargs: dict, block) -> Dict[str, Any]:
        """Execute an async completion and return both the response and the block."""
        try:
            response = await litellm.acompletion(**completion_kwargs)
            log_api_response("LiteLLM Batch", response)
            return {"block": block, "response": response}
        except Exception as e:
            log_api_error("LiteLLM Batch", e, completion_kwargs)
            block.update_metadata(llm_error_count=1)
            return {"block": block, "response": None}

    def rewrite_block(self, response: dict, prompt_data: PromptData, document: Document):
        """Apply the image description to the block."""
        block = prompt_data["block"]

        if not response or "image_description" not in response:
            block.update_metadata(llm_error_count=1)
            return

        image_description = response["image_description"]
        if len(image_description) < 10:
            block.update_metadata(llm_error_count=1)
            return

        block.description = image_description

class ImageSchema(BaseModel):
    image_description: str
