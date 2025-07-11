"""
Module: ocr_config.py
Description: Configuration management and settings

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

# OCR model fine-tuning configuration
config = {
    # Model parameters
    "model_type": "ocr",
    "max_length": 512,  # Maximum sequence length
    
    # Training parameters
    "batch_size": 8,
    "learning_rate": 5e-5,
    "epochs": 3,
    "gradient_accumulation_steps": 4,
    "weight_decay": 0.01,
    "warmup_ratio": 0.05,
    
    # Optimizer settings
    "optim": "adamw_torch",  # Recommended by Unsloth
    "max_grad_norm": 0.3,    # Recommended by Unsloth for stability
    
    # LoRA parameters (for efficient fine-tuning)
    "lora_r": 16,            # LoRA attention dimension
    "lora_alpha": 32,        # LoRA alpha (scaling factor)
    "lora_dropout": 0.05,    # Dropout probability for LoRA layers
    
    # Training mode - Choose one
    "full_finetune": False,  # Set to True for full fine-tuning (no LoRA)
    "load_in_8bit": False,   # Set to True for 8-bit quantization
    "load_in_4bit": True,    # Set to True for 4-bit quantization (default)
    
    # Target modules for LoRA (layers to fine-tune)
    # These are tailored for Transformer-based OCR models
    "target_modules": [
        "q_proj",     # Query projection
        "k_proj",     # Key projection
        "v_proj",     # Value projection
        "out_proj",   # Output projection
        "fc1",        # First fully connected layer
        "fc2",        # Second fully connected layer
        "down_proj",  # Down projection (if present)
        "up_proj",    # Up projection (if present)
        "gate_proj",  # Gate projection (if present)
    ],
    
    # 4-bit quantization parameters (for maximum memory efficiency)
    "bnb_4bit_compute_dtype": "float16",  # Compute type for 4-bit quantization
    "bnb_4bit_quant_type": "nf4",         # Quantization type (nf4 or fp4)
    "bnb_4bit_use_double_quant": True,    # Whether to use double quantization
    
    # Unsloth-specific optimizations
    "use_flash_attention_2": True,  # Use Flash Attention 2 if available
    "rope_scaling": {               # RoPE scaling for position embeddings
        "type": "dynamic",          # Dynamic scaling for better handling of sequence lengths
        "factor": 2.0               # Scaling factor
    },
    
    # Evaluation
    "evaluation_strategy": "steps",
    "eval_steps": 100,
    "save_strategy": "steps",
    "save_steps": 100,
    "save_total_limit": 3,
    "load_best_model_at_end": True,
    "metric_for_best_model": "eval_loss",
    "greater_is_better": False,
    
    # Early stopping
    "early_stopping_patience": 3,
    "early_stopping_threshold": 0.01,
    
    # Mixed precision
    "fp16": True,
    
    # Logging
    "logging_steps": 10,
    "report_to": "wandb",  # Set to "none" to disable
    
    # HuggingFace Hub
    "push_to_hub": False,
    "hub_model_id": None,  # e.g., "username/model-name"
    "hub_private": False,
    
    # Advanced parameters
    "save_pretrained_merged": True,  # Save merged model (adapter + base)
}