=== Analyzing Surya {model_type} model for Unsloth compatibility ===\n")
    
    # Create models dictionary
    models = create_model_dict(device="cpu")
    
    # Get model key
    model_key = f"{model_type}_model"
    if model_key not in models:
        print(f"Error: Unknown model type '{model_type}'")
        print(f"Available model types: {', '.join([k.replace('_model', '') for k in models.keys()])}")
        return
    
    # Get model instance
    model_instance = models[model_key]
    model = model_instance.model
    
    # Display model information
    print(f"Model class: {model.__class__.__name__}")
    print(f"Base model class: {model.__class__.__bases__[0].__name__}")
    print(f"Model modules: {len(list(model.named_modules()))}")
    print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Check for Transformer architecture
    is_transformer = False
    if hasattr(model, "config") and hasattr(model.config, "model_type"):
        is_transformer = True
        print(f"Model type from config: {model.config.model_type}")
    
    # Check for attention modules
    has_attention = False
    attention_module_types = set()
    for name, module in model.named_modules():
        if "attention" in name.lower():
            has_attention = True
            attention_module_types.add(module.__class__.__name__)
    
    if has_attention:
        print(f"Attention modules found: {', '.join(attention_module_types)}")
    else:
        print("No attention modules found")
    
    # Check for modules that can be targeted by LoRA
    lora_target_modules = []
    potential_lora_targets = ["q_proj", "k_proj", "v_proj", "out_proj", "fc1", "fc2", 
                             "up_proj", "down_proj", "gate_proj", "dense", "attention"]
    
    for name, module in model.named_modules():
        for target in potential_lora_targets:
            if target in name and hasattr(module, "weight") and module.weight is not None:
                lora_target_modules.append(name)
                break
    
    print(f"\nPotential LoRA target modules ({len(lora_target_modules)}):")
    for i, module in enumerate(lora_target_modules[:10]):
        print(f"  {module}")
    if len(lora_target_modules) > 10:
        print(f"  ... and {len(lora_target_modules) - 10} more")
    
    # Unsloth compatibility assessment
    if UNSLOTH_AVAILABLE:
        # Check for supported architectures
        supported_architectures = ["BertForMaskedLM", "GPT2LMHeadModel", "LlamaForCausalLM", 
                                  "MistralForCausalLM", "GemmaForCausalLM", "PhiForCausalLM",
                                  "OPTForCausalLM", "MPTForCausalLM", "FalconForCausalLM"]
        
        if model.__class__.__name__ in supported_architectures:
            print("\n✅ Model architecture is officially supported by Unsloth")
        elif is_transformer and has_attention:
            print("\n⚠️ Model architecture is not officially supported by Unsloth, but may work")
            print("   The model has transformer and attention components that Unsloth can optimize")
        else:
            print("\n❌ Model architecture is likely not compatible with Unsloth")
            print("   Using standard fine-tuning is recommended")
        
        # Recommend configuration
        print("\nRecommended configuration:")
        if is_transformer and has_attention:
            print("""
config = {
    # Choose one of these options:
    "full_finetune": False,  # Set to True for full fine-tuning (no LoRA)
    "load_in_8bit": False,   # Set to True for 8-bit quantization
    "load_in_4bit": True,    # Default: 4-bit quantization
    
    # LoRA parameters:
    "lora_r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    
    # Target modules for LoRA:
    "target_modules": [
        # Select appropriate modules from the list above
        "q_proj", "k_proj", "v_proj", "out_proj"
    ],
}
            """)
        else:
            print("""
config = {
    # Standard fine-tuning:
    "full_finetune": True,  # Full fine-tuning without LoRA
    
    # Training parameters:
    "learning_rate": 5e-5,
    "batch_size": 8,
    "epochs": 3
}
            """)
    else:
        print("\n❓ Unsloth compatibility cannot be determined (Unsloth not available)")
        print("   Install Unsloth to get more detailed compatibility information")
    
    print("\n=== Analysis complete ===\n")


def main():
    """Parse arguments and run analysis."""
    parser = argparse.ArgumentParser(description="Check Surya model compatibility with Unsloth")
    parser.add_argument("--model_type", type=str, default="recognition",
                       help="Type of Surya model to analyze (recognition, layout, etc.)")
    
    args = parser.parse_args()
    analyze_model(args.model_type)


if __name__ == "__main__":
    main()