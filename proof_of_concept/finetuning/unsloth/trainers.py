"""
Module: trainers.py
Description: Implementation of trainers functionality

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
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Callable

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import transformers
from transformers import (
    PreTrainedModel,
    PreTrainedTokenizer,
    Trainer,
    TrainingArguments,
    TrainerCallback,
    TrainerState,
    TrainerControl,
)
from peft import PeftModel, LoraConfig

try:
    from unsloth import FastLanguageModel
except ImportError:
    print("Unsloth not found. Install with: pip install unsloth")

# Local imports
from .utils import create_save_callback

logger = logging.getLogger(__name__)


@dataclass
class SuryaTrainingArguments(TrainingArguments):
    """Training arguments for Surya models."""
    
    # Model-specific arguments
    model_type: str = field(
        default="layout",
        metadata={"help": "Type of Surya model to fine-tune: layout, ocr, detection"}
    )
    
    # Unsloth-specific arguments
    use_unsloth: bool = field(
        default=True,
        metadata={"help": "Whether to use Unsloth optimizations"}
    )
    
    # LoRA configuration
    lora_r: int = field(
        default=16,
        metadata={"help": "LoRA attention dimension"}
    )
    lora_alpha: int = field(
        default=32,
        metadata={"help": "LoRA alpha parameter"}
    )
    lora_dropout: float = field(
        default=0.05,
        metadata={"help": "LoRA dropout probability"}
    )
    
    # Quantization configuration
    load_in_4bit: bool = field(
        default=True,
        metadata={"help": "Whether to load model in 4-bit precision"}
    )
    bnb_4bit_compute_dtype: str = field(
        default="float16",
        metadata={"help": "Compute dtype for 4-bit model"}
    )
    bnb_4bit_quant_type: str = field(
        default="nf4",
        metadata={"help": "Quantization type: nf4 or fp4"}
    )
    bnb_4bit_use_double_quant: bool = field(
        default=True,
        metadata={"help": "Whether to use double quantization"}
    )
    
    # Optimization arguments
    save_pretrained_merged: bool = field(
        default=True,
        metadata={"help": "Whether to save the merged model (adapter + base)"}
    )
    save_steps: int = field(
        default=500,
        metadata={"help": "Save checkpoint every X updates steps"}
    )
    
    # Early stopping
    early_stopping_patience: Optional[int] = field(
        default=None,
        metadata={"help": "Number of evaluation calls with no improvement after which training will be stopped"}
    )
    early_stopping_threshold: Optional[float] = field(
        default=None,
        metadata={"help": "Minimum improvement required to continue training"}
    )


class EarlyStoppingCallback(TrainerCallback):
    """
    Callback for early stopping.
    
    Stop training when the evaluation metric stops improving.
    """
    
    def __init__(
        self,
        metric_name: str = "eval_loss",
        patience: int = 3,
        threshold: float = 0.0,
        mode: str = "min",
    ):
        """
        Initialize the callback.
        
        Args:
            metric_name: Name of the metric to monitor
            patience: Number of evaluations with no improvement after which training will be stopped
            threshold: Minimum improvement required to continue training
            mode: Whether to minimize or maximize the metric (min or max)
        """
        self.metric_name = metric_name
        self.patience = patience
        self.threshold = threshold
        self.mode = mode
        self.best_value = float("inf") if mode == "min" else float("-inf")
        self.waiting = 0
    
    def on_evaluate(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        metrics: Dict[str, float],
        **kwargs,
    ):
        """
        Event called after evaluation.
        
        Args:
            args: Training arguments
            state: Trainer state
            control: Trainer control
            metrics: Evaluation metrics
        """
        if self.metric_name not in metrics:
            logger.warning(
                f"Early stopping metric {self.metric_name} not found in evaluation metrics. "
                f"Available metrics: {list(metrics.keys())}"
            )
            return control
        
        current_value = metrics[self.metric_name]
        
        # Check if improved
        if self.mode == "min":
            improved = current_value < self.best_value - self.threshold
        else:
            improved = current_value > self.best_value + self.threshold
        
        if improved:
            self.best_value = current_value
            self.waiting = 0
        else:
            self.waiting += 1
            if self.waiting >= self.patience:
                logger.info(
                    f"Early stopping triggered: {self.metric_name} did not improve for {self.patience} evaluations. "
                    f"Best value: {self.best_value}, Current value: {current_value}"
                )
                control.should_training_stop = True
        
        return control


class SuryaLayoutTrainer(Trainer):
    """Trainer for Surya's layout models with Unsloth optimizations."""
    
    def __init__(
        self,
        model: Union[PreTrainedModel, nn.Module],
        args: Union[SuryaTrainingArguments, TrainingArguments],
        **kwargs,
    ):
        """
        Initialize the trainer.
        
        Args:
            model: Model to train
            args: Training arguments
            **kwargs: Additional arguments for the Trainer
        """
        super().__init__(model=model, args=args, **kwargs)
        
        # Setup callbacks
        self.add_callback(create_save_callback(
            output_dir=args.output_dir,
            save_steps=args.save_steps,
        ))
        
        # Add early stopping if requested
        if getattr(args, "early_stopping_patience", None):
            self.add_callback(EarlyStoppingCallback(
                patience=args.early_stopping_patience,
                threshold=args.early_stopping_threshold or 0.0,
            ))
    
    def save_model(self, output_dir=None, _internal_call=False):
        """
        Save model with Unsloth optimizations if enabled.
        
        Args:
            output_dir: Directory to save model to
            _internal_call: Whether this is an internal call
        """
        output_dir = output_dir or self.args.output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Save model
        if isinstance(self.model, PeftModel):
            # Save adapter
            self.model.save_pretrained(output_dir)
            
            # Save merged model if requested
            if getattr(self.args, "save_pretrained_merged", False):
                merged_dir = os.path.join(output_dir, "merged")
                os.makedirs(merged_dir, exist_ok=True)
                
                # Get merged model (base + adapter)
                if hasattr(self.model, "merge_and_unload"):
                    merged_model = self.model.merge_and_unload()
                else:
                    # Manual merge
                    merged_model = self.model.base_model
                
                # Save merged model
                merged_model.save_pretrained(merged_dir)
                
                # Save tokenizer if available
                if hasattr(self, "tokenizer") and self.tokenizer is not None:
                    self.tokenizer.save_pretrained(merged_dir)
        else:
            # Regular save
            super().save_model(output_dir, _internal_call)


class SuryaOCRTrainer(Trainer):
    """Trainer for Surya's OCR models with Unsloth optimizations."""
    
    def __init__(
        self,
        model: Union[PreTrainedModel, nn.Module],
        args: Union[SuryaTrainingArguments, TrainingArguments],
        **kwargs,
    ):
        """
        Initialize the trainer.
        
        Args:
            model: Model to train
            args: Training arguments
            **kwargs: Additional arguments for the Trainer
        """
        super().__init__(model=model, args=args, **kwargs)
        
        # Setup callbacks
        self.add_callback(create_save_callback(
            output_dir=args.output_dir,
            save_steps=args.save_steps,
        ))
        
        # Add early stopping if requested
        if getattr(args, "early_stopping_patience", None):
            self.add_callback(EarlyStoppingCallback(
                patience=args.early_stopping_patience,
                threshold=args.early_stopping_threshold or 0.0,
            ))
    
    def compute_loss(self, model, inputs, return_outputs=False):
        """
        Custom compute_loss for OCR training.
        
        Args:
            model: The model to compute loss for
            inputs: The inputs to the model
            return_outputs: Whether to return outputs along with the loss
            
        Returns:
            Loss value, and optionally model outputs
        """
        if "labels" in inputs:
            labels = inputs.pop("labels")
        else:
            # Try to find input_ids converted from text
            labels = inputs.get("input_ids", None)
        
        # Forward pass
        outputs = model(**inputs)
        
        # Calculate loss
        if labels is not None:
            loss = outputs.loss
        else:
            # Default cross-entropy loss
            logits = outputs.logits
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = inputs["input_ids"][..., 1:].contiguous()
            loss_fct = nn.CrossEntropyLoss()
            loss = loss_fct(
                shift_logits.view(-1, shift_logits.size(-1)),
                shift_labels.view(-1)
            )
        
        return (loss, outputs) if return_outputs else loss
    
    def save_model(self, output_dir=None, _internal_call=False):
        """
        Save model with Unsloth optimizations if enabled.
        
        Args:
            output_dir: Directory to save model to
            _internal_call: Whether this is an internal call
        """
        output_dir = output_dir or self.args.output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Save model
        if isinstance(self.model, PeftModel):
            # Save adapter
            self.model.save_pretrained(output_dir)
            
            # Save merged model if requested
            if getattr(self.args, "save_pretrained_merged", False):
                merged_dir = os.path.join(output_dir, "merged")
                os.makedirs(merged_dir, exist_ok=True)
                
                # Get merged model (base + adapter)
                if hasattr(self.model, "merge_and_unload"):
                    merged_model = self.model.merge_and_unload()
                else:
                    # Manual merge
                    merged_model = self.model.base_model
                
                # Save merged model
                merged_model.save_pretrained(merged_dir)
                
                # Save tokenizer if available
                if hasattr(self, "tokenizer") and self.tokenizer is not None:
                    self.tokenizer.save_pretrained(merged_dir)
        else:
            # Regular save
            super().save_model(output_dir, _internal_call)


class SuryaDetectionTrainer(Trainer):
    """Trainer for Surya's detection models with Unsloth optimizations."""
    
    def __init__(
        self,
        model: Union[PreTrainedModel, nn.Module],
        args: Union[SuryaTrainingArguments, TrainingArguments],
        **kwargs,
    ):
        """
        Initialize the trainer.
        
        Args:
            model: Model to train
            args: Training arguments
            **kwargs: Additional arguments for the Trainer
        """
        super().__init__(model=model, args=args, **kwargs)
        
        # Setup callbacks
        self.add_callback(create_save_callback(
            output_dir=args.output_dir,
            save_steps=args.save_steps,
        ))
        
        # Add early stopping if requested
        if getattr(args, "early_stopping_patience", None):
            self.add_callback(EarlyStoppingCallback(
                patience=args.early_stopping_patience,
                threshold=args.early_stopping_threshold or 0.0,
            ))
    
    def compute_loss(self, model, inputs, return_outputs=False):
        """
        Custom compute_loss for detection model training.
        
        Args:
            model: The model to compute loss for
            inputs: The inputs to the model
            return_outputs: Whether to return outputs along with the loss
            
        Returns:
            Loss value, and optionally model outputs
        """
        # Detection models use a combination of classification and regression losses
        # This is a simplified implementation
        
        # Get labels
        labels = inputs.pop("labels", None)
        
        # Forward pass
        outputs = model(**inputs)
        
        # Calculate loss
        if hasattr(outputs, "loss") and outputs.loss is not None:
            loss = outputs.loss
        elif labels is not None:
            # Implement custom detection loss
            logits = outputs.logits
            loss_fct = nn.MSELoss()  # Simplified; real impl would use detection-specific loss
            loss = loss_fct(logits, labels)
        else:
            raise ValueError("No labels provided for detection model training")
        
        return (loss, outputs) if return_outputs else loss
    
    def save_model(self, output_dir=None, _internal_call=False):
        """
        Save model with Unsloth optimizations if enabled.
        
        Args:
            output_dir: Directory to save model to
            _internal_call: Whether this is an internal call
        """
        output_dir = output_dir or self.args.output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Save model
        if isinstance(self.model, PeftModel):
            # Save adapter
            self.model.save_pretrained(output_dir)
            
            # Save merged model if requested
            if getattr(self.args, "save_pretrained_merged", False):
                merged_dir = os.path.join(output_dir, "merged")
                os.makedirs(merged_dir, exist_ok=True)
                
                # Get merged model (base + adapter)
                if hasattr(self.model, "merge_and_unload"):
                    merged_model = self.model.merge_and_unload()
                else:
                    # Manual merge
                    merged_model = self.model.base_model
                
                # Save merged model
                merged_model.save_pretrained(merged_dir)
        else:
            # Regular save
            super().save_model(output_dir, _internal_call)


def get_trainer_class(model_type: str) -> Trainer:
    """
    Get the appropriate trainer class for a model type.
    
    Args:
        model_type: Type of Surya model (layout, ocr, detection)
        
    Returns:
        Trainer: Trainer class for the model type
    """
    trainers = {
        "layout": SuryaLayoutTrainer,
        "ocr": SuryaOCRTrainer,
        "detection": SuryaDetectionTrainer,
    }
    
    return trainers.get(model_type, Trainer)