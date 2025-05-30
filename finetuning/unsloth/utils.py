"""
Utility functions for Unsloth integration with Surya models.

This module provides helper functions for setting up datasets, preparing models,
and handling model uploads to HuggingFace.
"""

import os
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple, Callable

import torch
import numpy as np
from PIL import Image
from tqdm.auto import tqdm
from datasets import Dataset, DatasetDict
from transformers import (
    PreTrainedModel,
    PreTrainedTokenizer,
    TrainingArguments,
    Trainer,
)
from huggingface_hub import HfApi, upload_folder

logger = logging.getLogger(__name__)


def prepare_layout_dataset(
    data_dir: str,
    image_size: Tuple[int, int] = (512, 512),
    augment: bool = True,
) -> DatasetDict:
    """
    Prepare layout dataset for fine-tuning.
    
    Args:
        data_dir: Directory containing prepared layout data
        image_size: Size to resize images to
        augment: Whether to apply data augmentation
        
    Returns:
        DatasetDict: Dataset dictionary with train, validation, and test splits
    """
    splits_dir = os.path.join(data_dir, "splits")
    images_dir = os.path.join(data_dir, "images")
    annotations_dir = os.path.join(data_dir, "annotations")
    
    datasets = {}
    
    for split in ["train", "val", "test"]:
        split_file = os.path.join(splits_dir, f"{split}.json")
        
        if not os.path.exists(split_file):
            logger.warning(f"Split file {split_file} not found, skipping {split} split")
            continue
        
        with open(split_file, 'r') as f:
            split_data = json.load(f)
        
        pages = split_data.get("pages", [])
        if not pages:
            logger.warning(f"No pages found in {split} split")
            continue
        
        # Prepare dataset entries
        dataset_entries = []
        
        for page in tqdm(pages, desc=f"Processing {split} split"):
            image_path = page["image_path"]
            doc_name = page["doc_name"]
            page_num = page["page_num"]
            
            # Get annotation
            annotation_path = os.path.join(annotations_dir, f"{doc_name}_page_{page_num}.json")
            
            if not os.path.exists(annotation_path):
                logger.warning(f"Annotation file {annotation_path} not found, skipping page")
                continue
            
            with open(annotation_path, 'r') as f:
                annotation = json.load(f)
            
            # Load and preprocess image
            try:
                image = Image.open(image_path).convert("RGB")
                image = image.resize(image_size)
                
                # Convert image to array
                image_array = np.array(image)
                
                # Extract regions from annotation
                if "regions" in annotation:
                    regions = annotation["regions"]
                elif "shapes" in annotation:  # labelme format
                    regions = []
                    for shape in annotation["shapes"]:
                        regions.append({
                            "label": shape["label"],
                            "points": shape["points"],
                        })
                else:
                    regions = []
                
                # Create dataset entry
                dataset_entries.append({
                    "image": image_array,
                    "regions": regions,
                    "image_path": image_path,
                    "annotation_path": annotation_path,
                    "doc_name": doc_name,
                    "page_num": page_num,
                })
                
            except Exception as e:
                logger.error(f"Error processing page {image_path}: {e}")
                continue
        
        # Create dataset for this split
        datasets[split] = Dataset.from_list(dataset_entries)
    
    return DatasetDict(datasets)


def prepare_ocr_dataset(
    data_dir: str,
    tokenizer: Optional[PreTrainedTokenizer] = None,
    max_length: int = 512,
) -> DatasetDict:
    """
    Prepare OCR dataset for fine-tuning.
    
    Args:
        data_dir: Directory containing prepared OCR data
        tokenizer: Tokenizer for encoding text
        max_length: Maximum sequence length
        
    Returns:
        DatasetDict: Dataset dictionary with train, validation, and test splits
    """
    splits_dir = os.path.join(data_dir, "splits")
    line_crops_dir = os.path.join(data_dir, "line_crops")
    transcriptions_dir = os.path.join(data_dir, "transcriptions")
    
    datasets = {}
    
    for split in ["train", "val", "test"]:
        split_file = os.path.join(splits_dir, f"{split}.json")
        
        if not os.path.exists(split_file):
            logger.warning(f"Split file {split_file} not found, skipping {split} split")
            continue
        
        with open(split_file, 'r') as f:
            split_data = json.load(f)
        
        lines = split_data.get("lines", [])
        if not lines:
            logger.warning(f"No lines found in {split} split")
            continue
        
        # Prepare dataset entries
        dataset_entries = []
        
        for line in tqdm(lines, desc=f"Processing {split} split"):
            image_path = line["image_path"]
            text_path = line["text_path"]
            
            # Load line image
            try:
                image = Image.open(image_path).convert("RGB")
                image_array = np.array(image)
                
                # Load text
                with open(text_path, 'r', encoding='utf-8') as f:
                    text = f.read().strip()
                
                # Create dataset entry
                dataset_entry = {
                    "image": image_array,
                    "text": text,
                    "line_id": line["line_id"],
                }
                
                # Add tokenized text if tokenizer is provided
                if tokenizer is not None:
                    tokenized = tokenizer(
                        text,
                        truncation=True,
                        max_length=max_length,
                        padding="max_length",
                        return_tensors="pt",
                    )
                    
                    dataset_entry["input_ids"] = tokenized["input_ids"][0].tolist()
                    dataset_entry["attention_mask"] = tokenized["attention_mask"][0].tolist()
                
                dataset_entries.append(dataset_entry)
                
            except Exception as e:
                logger.error(f"Error processing line {image_path}: {e}")
                continue
        
        # Create dataset for this split
        datasets[split] = Dataset.from_list(dataset_entries)
    
    return DatasetDict(datasets)


def prepare_detection_dataset(
    data_dir: str,
    image_size: Tuple[int, int] = (512, 512),
) -> DatasetDict:
    """
    Prepare detection dataset for fine-tuning.
    
    Args:
        data_dir: Directory containing prepared detection data
        image_size: Size to resize images to
        
    Returns:
        DatasetDict: Dataset dictionary with train, validation, and test splits
    """
    splits_dir = os.path.join(data_dir, "splits")
    region_crops_dir = os.path.join(data_dir, "region_crops")
    annotations_dir = os.path.join(data_dir, "line_annotations")
    
    datasets = {}
    
    for split in ["train", "val", "test"]:
        split_file = os.path.join(splits_dir, f"{split}.json")
        
        if not os.path.exists(split_file):
            logger.warning(f"Split file {split_file} not found, skipping {split} split")
            continue
        
        with open(split_file, 'r') as f:
            split_data = json.load(f)
        
        regions = split_data.get("regions", [])
        if not regions:
            logger.warning(f"No regions found in {split} split")
            continue
        
        # Prepare dataset entries
        dataset_entries = []
        
        for region in tqdm(regions, desc=f"Processing {split} split"):
            image_path = region["image_path"]
            annotation_path = region["annotation_path"]
            
            # Load region image
            try:
                image = Image.open(image_path).convert("RGB")
                image = image.resize(image_size)
                image_array = np.array(image)
                
                # Load annotation
                with open(annotation_path, 'r') as f:
                    annotation = json.load(f)
                
                lines = annotation.get("lines", [])
                
                # Create dataset entry
                dataset_entries.append({
                    "image": image_array,
                    "lines": lines,
                    "region_id": region["region_id"],
                    "image_path": image_path,
                    "annotation_path": annotation_path,
                })
                
            except Exception as e:
                logger.error(f"Error processing region {image_path}: {e}")
                continue
        
        # Create dataset for this split
        datasets[split] = Dataset.from_list(dataset_entries)
    
    return DatasetDict(datasets)


@dataclass
class UploadConfig:
    """Configuration for uploading models to HuggingFace Hub."""
    
    model_path: str
    repo_id: str
    commit_message: str = "Upload fine-tuned model"
    create_repo: bool = True
    private: bool = False
    token: Optional[str] = None
    repo_type: str = "model"
    tags: List[str] = None


def upload_model_to_hf(config: UploadConfig) -> str:
    """
    Upload fine-tuned model to HuggingFace Hub.
    
    Args:
        config: Upload configuration
        
    Returns:
        str: URL of the uploaded model
    """
    # Initialize HF API
    api = HfApi(token=config.token)
    
    # Create repository if needed
    if config.create_repo:
        api.create_repo(
            repo_id=config.repo_id,
            repo_type=config.repo_type,
            private=config.private,
            exist_ok=True,
        )
    
    # Upload model
    tags = config.tags or ["surya", "fine-tuned", "marker"]
    
    # Upload folder
    url = upload_folder(
        folder_path=config.model_path,
        repo_id=config.repo_id,
        commit_message=config.commit_message,
        token=config.token,
        ignore_patterns=["*.tmp", "*.log", ".git*", "__pycache__"],
    )
    
    # Add tags
    api.add_tags(
        repo_id=config.repo_id,
        tags=tags
    )
    
    return url


def create_save_callback(
    output_dir: str,
    save_steps: int = 500,
    save_total_limit: int = 3,
) -> Callable:
    """
    Create a callback for saving models during training.
    
    Args:
        output_dir: Directory to save models to
        save_steps: Save every n steps
        save_total_limit: Maximum number of checkpoints to keep
        
    Returns:
        Callable: Save callback function
    """
    os.makedirs(output_dir, exist_ok=True)
    saved_models = []
    
    def save_model_callback(trainer: Trainer, args: TrainingArguments, state, control, **kwargs):
        """Callback to save model during training."""
        if state.global_step % save_steps == 0:
            # Create checkpoint directory
            checkpoint_dir = os.path.join(output_dir, f"checkpoint-{state.global_step}")
            os.makedirs(checkpoint_dir, exist_ok=True)
            
            # Save model
            trainer.save_model(checkpoint_dir)
            
            # Save optimizer and scheduler
            trainer.save_state()
            
            # Add to saved models
            saved_models.append(checkpoint_dir)
            
            # Remove old checkpoints if limit is reached
            if save_total_limit > 0 and len(saved_models) > save_total_limit:
                old_checkpoint = saved_models.pop(0)
                for file in os.listdir(old_checkpoint):
                    file_path = os.path.join(old_checkpoint, file)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            os.rmdir(file_path)
                    except Exception as e:
                        logger.error(f"Error removing checkpoint file {file_path}: {e}")
            
        return control
    
    return save_model_callback