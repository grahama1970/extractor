"""
Module: equation.py

External Dependencies:
- surya: [Documentation URL]
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

from typing import Annotated, List, Optional, Tuple

from surya.recognition import RecognitionPredictor as TexifyPredictor  # Use RecognitionPredictor instead
from extractor.core.processors import BaseProcessor
from extractor.core.processors.util import add_math_spans_to_line
from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks import Equation
from extractor.core.schema.document import Document
from extractor.core.settings import settings


class EquationProcessor(BaseProcessor):
    """
    A processor for recognizing equations in the document.
    """
    block_types: Annotated[
        Tuple[BlockTypes],
        "The block types to process.",
    ] = (BlockTypes.Equation,)
    model_max_length: Annotated[
        int,
        "The maximum number of tokens to allow for the Texify model.",
    ] = 768
    texify_batch_size: Annotated[
        Optional[int],
        "The batch size to use for the Texify model.",
        "Default is None, which will use the default batch size for the model."
    ] = None
    token_buffer: Annotated[
        int,
        "The number of tokens to buffer above max for the Texify model.",
    ] = 256
    disable_tqdm: Annotated[
        bool,
        "Whether to disable the tqdm progress bar.",
    ] = False
    texify_inline_spans: Annotated[
        bool,
        "Whether to run texify on inline math spans."
    ] = False

    def __init__(self, texify_model: TexifyPredictor, config=None):
        super().__init__(config)

        self.texify_model = texify_model

    def __call__(self, document: Document):
        equation_data = []

        for page in document.pages:
            equation_blocks = page.contained_blocks(document, self.block_types)
            math_blocks = []
            if self.texify_inline_spans:
                math_blocks = page.contained_blocks(document, (BlockTypes.Line,))
                math_blocks = [m for m in math_blocks if m.formats and "math" in m.formats]

            for block in equation_blocks + math_blocks:
                image = block.get_image(document, highres=False).convert("RGB")
                raw_text = block.raw_text(document)
                # Simple token estimation - avg 4 chars per token
                token_count = len(raw_text) // 4

                equation_data.append({
                    "image": image,
                    "block_id": block.id,
                    "token_count": token_count,
                    "page": page
                })

        if len(equation_data) == 0:
            return

        predictions = self.get_latex_batched(equation_data)
        for prediction, equation_d in zip(predictions, equation_data):
            conditions = [
                len(prediction) > equation_d["token_count"] * .4,
                len(prediction.strip()) > 0
            ]
            if not all(conditions):
                continue

            block = document.get_block(equation_d["block_id"])
            if isinstance(block, Equation):
                prediction = self.inline_to_block(prediction)
                block.html = prediction
            else:
                block.structure = []
                add_math_spans_to_line(prediction, block, equation_d["page"])

    def inline_to_block(self, latex: str):
        latex = latex.strip()
        math_count = latex.count("<math")
        math_start = latex.startswith("<math>")
        math_end = latex.endswith("</math>")
        if any([
            math_count != 1,
            not math_start,
            not math_end
        ]):
            return latex

        latex = latex.replace("<math>", '<math display="block">')
        return latex


    def get_batch_size(self):
        if self.texify_batch_size is not None:
            return self.texify_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 6
        elif settings.TORCH_DEVICE_MODEL == "mps":
            return 6
        return 2

    def get_latex_batched(self, equation_data: List[dict]):
        """Process equations with proper bbox handling to match marker-pdf"""
        # Extract images and bboxes from equation data
        inference_images = []
        bboxes_list = []
        
        for eq in equation_data:
            inference_images.append(eq["image"])
            # Create a bbox that covers the entire image
            h, w = eq["image"].height, eq["image"].width
            bbox = [[0, 0, w, h]]  # Single bbox covering whole image
            bboxes_list.append(bbox)
        
        self.texify_model.disable_tqdm = self.disable_tqdm
        
        # Now pass bboxes to avoid det_predictor requirement
        model_output = self.texify_model(
            images=inference_images,
            bboxes=bboxes_list,  # ADD THIS to match marker-pdf!
            task_names=["block_without_boxes"] * len(inference_images),
            recognition_batch_size=self.get_batch_size(),
            sort_lines=False
        )
        predictions = [output.text_lines[0].text if output.text_lines else "" for output in model_output]

        for i, pred in enumerate(predictions):
            # Simple token estimation for validation
            token_count = len(pred) // 4
            # If we're at the max token length, the prediction may be repetitive or invalid
            if token_count >= self.model_max_length - 1:
                predictions[i] = ""
        return predictions

    def get_total_texify_tokens(self, text):
        # Surya's RecognitionPredictor uses ocr_tokenizer instead of tokenizer
        if hasattr(self.texify_model.processor, 'ocr_tokenizer'):
            tokenizer = self.texify_model.processor.ocr_tokenizer
        else:
            tokenizer = self.texify_model.processor.tokenizer
        tokens = tokenizer(text)
        return len(tokens["input_ids"])