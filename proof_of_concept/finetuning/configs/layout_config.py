"""
Module: layout_config.py
Description: Configuration management and settings

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

# Layout model fine-tuning configuration
config = {
    # Model parameters
    "model_type": "layout",
    "image_size": (512, 512),  # Width, Height
    
    # Training parameters
    "batch_size": 8,
    "learning_rate": 2e-4,
    "epochs": 3,
    "gradient_accumulation_steps": 4,
    "weight_decay": 0.01,
    "warmup_ratio": 0.05,
    
    # LoRA parameters (for efficient fine-tuning)
    "lora_r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    
    # Target modules for LoRA (layers to fine-tune)
    "target_modules": [
        "attention.query",
        "attention.key", 
        "attention.value",
        "attention.output.dense", 
        "output.dense",
        "intermediate.dense",
    ],
    
    # Quantization parameters (for memory efficiency)
    "load_in_4bit": True,
    "bnb_4bit_compute_dtype": "float16",
    "bnb_4bit_quant_type": "nf4",
    "bnb_4bit_use_double_quant": True,
    
    # Data augmentation
    "augmentation": {
        "enabled": True,
        "random_rotation": 5,  # degrees
        "random_crop": 0.05,   # fraction
        "color_jitter": {
            "brightness": 0.2,
            "contrast": 0.2,
            "saturation": 0.2,
            "hue": 0.1,
        },
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
    "model_max_length": 512,  # Maximum sequence length
}