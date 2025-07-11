"""
Module: adapters.py

External Dependencies:
- torch: https://pytorch.org/docs/
- transformers: https://huggingface.co/docs/transformers/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import os
from typing import Dict, Any, List, Optional, Union, Tuple

import torch
from peft import LoraConfig, TaskType
from transformers import PreTrainedModel


def get_layout_lora_config(
    r: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.05,
    target_modules: Optional[List[str]] = None,
) -> LoraConfig:
    """
    Get LoRA configuration for layout model fine-tuning.
    
    Args:
        r: LoRA rank
        lora_alpha: LoRA alpha parameter
        lora_dropout: Dropout probability for LoRA layers
        target_modules: List of module names to apply LoRA to. If None, uses default modules.
        
    Returns:
        LoraConfig: Configuration for LoRA fine-tuning
    """
    if target_modules is None:
        # Target transformer blocks in the layout model (modified SegFormer)
        target_modules = [
            "attention.query",
            "attention.key",
            "attention.value",
            "attention.output.dense",
            "output.dense",
            "intermediate.dense",
        ]
    
    return LoraConfig(
        r=r,
        lora_alpha=lora_alpha,
        target_modules=target_modules,
        lora_dropout=lora_dropout,
        bias="none",
        inference_mode=False,
        task_type=TaskType.SEQ_CLS,  # Layout model performs classification
    )


def get_ocr_lora_config(
    r: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.05,
    target_modules: Optional[List[str]] = None,
) -> LoraConfig:
    """
    Get LoRA configuration for OCR model fine-tuning.
    
    Args:
        r: LoRA rank
        lora_alpha: LoRA alpha parameter
        lora_dropout: Dropout probability for LoRA layers
        target_modules: List of module names to apply LoRA to. If None, uses default modules.
        
    Returns:
        LoraConfig: Configuration for LoRA fine-tuning
    """
    if target_modules is None:
        # Target transformer blocks in the OCR model (modified Donut)
        target_modules = [
            "q_proj",
            "k_proj",
            "v_proj",
            "out_proj",
            "fc1",
            "fc2",
        ]
    
    return LoraConfig(
        r=r,
        lora_alpha=lora_alpha,
        target_modules=target_modules,
        lora_dropout=lora_dropout,
        bias="none",
        inference_mode=False,
        task_type=TaskType.SEQ_2_SEQ_LM,  # OCR model performs seq2seq
    )


def get_detection_lora_config(
    r: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.05,
    target_modules: Optional[List[str]] = None,
) -> LoraConfig:
    """
    Get LoRA configuration for detection model fine-tuning.
    
    Args:
        r: LoRA rank
        lora_alpha: LoRA alpha parameter
        lora_dropout: Dropout probability for LoRA layers
        target_modules: List of module names to apply LoRA to. If None, uses default modules.
        
    Returns:
        LoraConfig: Configuration for LoRA fine-tuning
    """
    if target_modules is None:
        # Target transformer blocks in the detection model (modified EfficientVit)
        target_modules = [
            "attn.qkv",
            "attn.proj",
            "ffn.fc1",
            "ffn.fc2",
        ]
    
    return LoraConfig(
        r=r,
        lora_alpha=lora_alpha,
        target_modules=target_modules,
        lora_dropout=lora_dropout,
        bias="none",
        inference_mode=False,
        task_type=TaskType.FEATURE_EXTRACTION,  # Detection model performs feature extraction
    )


def create_qlora_model(
    base_model: PreTrainedModel,
    lora_config: LoraConfig,
    quantization_config: Optional[Dict[str, Any]] = None,
) -> Tuple[PreTrainedModel, Dict[str, Any]]:
    """
    Apply QLoRA to a base model using Unsloth's optimizations.'
    
    Args:
        base_model: Base pre-trained model
        lora_config: LoRA configuration
        quantization_config: Quantization configuration dict. If None, uses default 4-bit config.
        
    Returns:
        Tuple[PreTrainedModel, Dict[str, Any]]: Fine-tuned model and training arguments
    """
    try:
        from unsloth import FastLanguageModel
    except ImportError:
        raise ImportError(
            "Unsloth is required for QLoRA. Install it with: pip install unsloth"
        )
    
    if quantization_config is None:
        quantization_config = {
            "load_in_4bit": True,
            "bnb_4bit_compute_dtype": "float16",
            "bnb_4bit_quant_type": "nf4",
            "bnb_4bit_use_double_quant": True,
        }
    
    # Use Unsloth's FastLanguageModel for optimized QLoRA
    model, tokenizer = FastLanguageModel.from_pretrained(
        model=base_model,
        max_seq_length=512,  # Adjust based on your model requirements
        **quantization_config
    )
    
    # Add LoRA adapters
    model = FastLanguageModel.get_peft_model(
        model=model,
        lora_config=lora_config,
    )
    
    # Prepare training arguments based on model type
    if hasattr(base_model, "config") and hasattr(base_model.config, "model_type"):
        model_type = base_model.config.model_type
    else:
        model_type = "custom"
    
    training_args = {
        "gradient_accumulation_steps": 4,
        "gradient_checkpointing": True,
        "learning_rate": 2e-4,
        "optim": "adamw_torch",
        "max_grad_norm": 0.3,
        "warmup_ratio": 0.03,
        "num_train_epochs": 1,
        "use_flash_attention_2": True,
        "save_safetensors": True,
    }
    
    # Adjust training args based on model type
    if model_type == "segformer":  # Layout model
        training_args["learning_rate"] = 1e-4
    elif model_type == "donut":  # OCR model
        training_args["learning_rate"] = 5e-5
    elif model_type == "efficientvit":  # Detection model
        training_args["learning_rate"] = 3e-4
    
    return model, training_args