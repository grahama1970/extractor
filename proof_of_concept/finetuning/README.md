# Surya Model Fine-tuning

This directory contains scripts, utilities, and configuration files for fine-tuning Surya models on client-specific data. These tools enable customization of Marker's OCR, layout analysis, and text recognition capabilities for domain-specific documents.

## Directory Structure

```
finetuning/
├── configs/              # Configuration files for different fine-tuning scenarios
│   ├── layout_config.py  # Configuration for layout model fine-tuning
│   ├── ocr_config.py     # Configuration for OCR model fine-tuning
│   └── table_config.py   # Configuration for table recognition fine-tuning
│
├── data/                 # Sample data and utilities for data preparation (created when scripts run)
│   └── README.md         # Instructions for data preparation
│
├── notebooks/            # Jupyter notebooks for interactive fine-tuning
│   ├── layout_finetuning.ipynb    # Interactive layout model fine-tuning
│   ├── ocr_finetuning.ipynb       # Interactive OCR model fine-tuning
│   └── model_evaluation.ipynb     # Notebook for evaluating fine-tuned models
│
├── scripts/              # Automation scripts for fine-tuning workflows
│   ├── prepare_data.py   # Script to prepare and format training data
│   ├── finetune_layout.py  # Script for layout model fine-tuning
│   ├── finetune_ocr.py     # Script for OCR model fine-tuning
│   ├── evaluate_models.py  # Script for evaluating fine-tuned models
│   └── upload_to_hf.py     # Script for uploading models to HuggingFace
│
├── unsloth/              # Unsloth fine-tuning utilities
│   ├── adapters.py       # Adapter configurations for efficient fine-tuning
│   ├── trainers.py       # Custom training loops and utilities
│   └── utils.py          # Utility functions for Unsloth integration
│
└── README.md             # This file
```

## Installation Requirements

```bash
# Install fine-tuning dependencies
pip install transformers>=4.34.0 peft>=0.7.0 bitsandbytes>=0.41.0 accelerate>=0.23.0
pip install datasets huggingface_hub python-dotenv
pip install wandb  # For experiment tracking (optional)

# Set up Unsloth - either via pip or git
# Option 1: Install via pip (simpler but may not have latest features)
pip install unsloth

# Option 2: Clone the repository (recommended for latest features)
mkdir -p repos
git clone https://github.com/unslothai/unsloth.git repos/unsloth
# Add to PYTHONPATH or use UNSLOTH_PATH in .env
```

### Environment Setup

Copy the template `.env.template` file to create your own configuration:

```bash
cp .env.template .env
```

Then edit the `.env` file to add your HuggingFace token and other configuration:

```
# HuggingFace configuration
HF_TOKEN=your_huggingface_token_here
HF_USERNAME=your_huggingface_username

# Unsloth configuration
UNSLOTH_PATH=/path/to/repos/unsloth

# Weights & Biases configuration (optional)
WANDB_PROJECT=surya-finetuning
WANDB_ENTITY=your_wandb_username
```

## Checking Model Compatibility

Before fine-tuning, check if your Surya models are compatible with Unsloth optimizations:

```bash
# Check OCR (Recognition) model compatibility
python finetuning/utils/check_model_compatibility.py --model_type recognition

# Check Layout model compatibility
python finetuning/utils/check_model_compatibility.py --model_type layout
```

This will analyze the model architecture and provide recommendations for fine-tuning.

## Quickstart

### 1. Prepare Your Data

Data should be formatted according to the requirements of the specific Surya model you want to fine-tune. See the individual model sections below for details.

### 2. Run Fine-tuning

Use the provided scripts to fine-tune models:

```bash
# For layout model fine-tuning
python finetuning/scripts/finetune_layout.py --config finetuning/configs/layout_config.py --output_dir models/client_name

# For OCR model fine-tuning
python finetuning/scripts/finetune_ocr.py --config finetuning/configs/ocr_config.py --output_dir models/client_name
```

### 3. Evaluate Models

```bash
python finetuning/scripts/evaluate_models.py --model_path models/client_name/layout --test_data path/to/test_data
```

### 4. Upload to HuggingFace

```bash
python finetuning/scripts/upload_to_hf.py --model_path models/client_name/layout --repo_name client-name/surya-layout-finetuned
```

## Fine-tuning Surya Models

Surya consists of multiple models that can be individually fine-tuned:

### Layout Model (LayoutPredictor)

The layout model identifies document regions (text, table, figure, etc.) and determines reading order.

**Data format:**
- Images of document pages
- Annotations with labeled regions (text, table, figure, etc.)

**Fine-tuning approach:**
- Unsloth QLoRA fine-tuning with 4-bit quantization
- Training strategies: gradient accumulation, mixed precision

### OCR Model (RecognitionPredictor)

The OCR model converts text regions into machine-readable text.

**Data format:**
- Cropped images of text lines
- Ground truth text transcriptions

**Fine-tuning approach:**
- Sequence-to-sequence fine-tuning
- Specialized for domain-specific terminology

### Line Detection Model (DetectionPredictor)

The line detection model identifies individual text lines in document regions.

**Data format:**
- Document region images
- Bounding box annotations for text lines

**Fine-tuning approach:**
- Object detection fine-tuning
- Custom post-processing optimization

## Using Fine-tuned Models in Marker

To use your fine-tuned models with Marker:

```python
from marker.models import create_model_dict
from marker.converters.pdf import PdfConverter

# Configure custom model paths
custom_models = create_model_dict(
    device="cuda",
    custom_model_paths={
        "layout_model": "path/to/finetuned/layout",
        "recognition_model": "path/to/finetuned/ocr",
        "detection_model": "path/to/finetuned/detection",
    }
)

# Use custom models with Marker
converter = PdfConverter(
    artifact_dict=custom_models,
    config=config
)

# Convert documents
result = converter("document.pdf")
```

## Advanced Configuration

See the `configs/` directory for detailed configuration options for each model.

## Resources

- [Surya GitHub Repository](https://github.com/VikParuchuri/surya)
- [Unsloth Documentation](https://unsloth.ai/)
- [HuggingFace Documentation](https://huggingface.co/docs)
- [Marker Documentation](https://github.com/VikParuchuri/marker)