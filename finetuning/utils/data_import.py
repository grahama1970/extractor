{text}"
            ax.set_title(title)
            
            # Remove axes
            ax.axis('off')
            
        except Exception as e:
            logger.error(f"Error displaying sample {i}: {e}")
            ax.text(0.5, 0.5, f"Error: {e}", 
                    horizontalalignment='center', verticalalignment='center')
    
    # Hide any unused axes
    for i in range(len(samples), grid_size[0] * grid_size[1]):
        row = i // grid_size[1]
        col = i % grid_size[1]
        axes[row, col].axis('off')
    
    plt.tight_layout()
    
    # Save or return
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        return output_path
    else:
        return fig

def setup_data_directories(
    output_dir: str,
    mode: str = "ocr"
) -> Dict[str, str]:
    """
    Create necessary directories for data preparation.
    
    Args:
        output_dir: Base directory for output
        mode: Data preparation mode (ocr, layout, detection)
        
    Returns:
        Dictionary with directory paths
    """
    base_dir = Path(output_dir)
    
    # Create mode-specific directories
    if mode == "layout":
        dirs = {
            "images": base_dir / "images",
            "annotations": base_dir / "annotations",
            "splits": base_dir / "splits",
        }
    elif mode == "ocr":
        dirs = {
            "line_crops": base_dir / "line_crops",
            "transcriptions": base_dir / "transcriptions",
            "splits": base_dir / "splits",
        }
    elif mode == "detection":
        dirs = {
            "region_crops": base_dir / "region_crops",
            "line_annotations": base_dir / "line_annotations",
            "splits": base_dir / "splits",
        }
    else:
        raise ValueError(f"Unknown mode: {mode}")
    
    # Create all directories
    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    
    return {k: str(v) for k, v in dirs.items()}


if __name__ == "__main__":
    # Simple CLI for testing
    import argparse
    
    parser = argparse.ArgumentParser(description="OCR data import/export utilities")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Convert PDF command
    pdf_parser = subparsers.add_parser("pdf2img", help="Convert PDF pages to images")
    pdf_parser.add_argument("pdf_path", help="Path to PDF file")
    pdf_parser.add_argument("output_dir", help="Directory to save images")
    pdf_parser.add_argument("--dpi", type=int, default=300, help="DPI for rendering")
    pdf_parser.add_argument("--first-page", type=int, help="First page to convert (1-indexed)")
    pdf_parser.add_argument("--last-page", type=int, help="Last page to convert (1-indexed)")
    
    # Prepare images command
    img_parser = subparsers.add_parser("prepare", help="Prepare images for annotation")
    img_parser.add_argument("image_dir", help="Directory containing source images")
    img_parser.add_argument("--output-dir", help="Directory to save prepared images")
    img_parser.add_argument("--resize", help="Resize images to width,height")
    img_parser.add_argument("--max-images", type=int, help="Maximum number of images to prepare")
    
    # Prepare dataset command
    dataset_parser = subparsers.add_parser("dataset", help="Prepare dataset from annotations")
    dataset_parser.add_argument("annotations_path", help="Path to annotations JSON file")
    dataset_parser.add_argument("output_dir", help="Directory to save prepared data")
    dataset_parser.add_argument("--train-split", type=float, default=0.8, help="Proportion for training set")
    dataset_parser.add_argument("--val-split", type=float, default=0.1, help="Proportion for validation set")
    dataset_parser.add_argument("--test-split", type=float, default=0.1, help="Proportion for test set")
    
    # Analyze dataset command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze OCR dataset")
    analyze_parser.add_argument("dataset_dir", help="Path to dataset directory")
    analyze_parser.add_argument("--sample-size", type=int, default=5, help="Number of samples to include in report")
    
    # Validate dataset command
    validate_parser = subparsers.add_parser("validate", help="Validate OCR dataset")
    validate_parser.add_argument("dataset_dir", help="Path to dataset directory")
    
    # Visualize dataset command
    viz_parser = subparsers.add_parser("visualize", help="Visualize OCR dataset samples")
    viz_parser.add_argument("dataset_dir", help="Path to dataset directory")
    viz_parser.add_argument("output_path", help="Path to save visualization")
    viz_parser.add_argument("--num-samples", type=int, default=10, help="Number of samples to visualize")
    
    args = parser.parse_args()
    
    # Execute command
    if args.command == "pdf2img":
        image_paths = convert_pdf_to_images(
            args.pdf_path, 
            args.output_dir,
            dpi=args.dpi,
            first_page=args.first_page,
            last_page=args.last_page
        )
        print(f"Converted {len(image_paths)} pages to images")
        
    elif args.command == "prepare":
        resize = None
        if args.resize:
            try:
                resize = tuple(map(int, args.resize.split(',')))
            except:
                print(f"Invalid resize format: {args.resize}. Expected 'width,height'")
        
        image_paths = prepare_images_for_annotation(
            args.image_dir,
            args.output_dir,
            resize=resize,
            max_images=args.max_images
        )
        print(f"Prepared {len(image_paths)} images")
        
    elif args.command == "dataset":
        output_dir = prepare_dataset_from_annotations(
            args.annotations_path,
            args.output_dir,
            train_split=args.train_split,
            val_split=args.val_split,
            test_split=args.test_split
        )
        print(f"Prepared dataset at: {output_dir}")
        
    elif args.command == "analyze":
        stats = analyze_dataset(args.dataset_dir, args.sample_size)
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        
    elif args.command == "validate":
        validation = validate_dataset(args.dataset_dir)
        if validation["valid"]:
            print("Dataset is valid")
        else:
            print("Dataset validation failed:")
            print(f"  Errors: {len(validation['errors'])}")
            print(f"  Warnings: {len(validation['warnings'])}")
            print(f"  Missing files: {len(validation['missing_files'])}")
            print(f"  Empty text: {len(validation['empty_text'])}")
            print(f"  Invalid images: {len(validation['invalid_images'])}")
            
    elif args.command == "visualize":
        output_path = visualize_dataset_samples(
            args.dataset_dir,
            args.output_path,
            num_samples=args.num_samples
        )
        if output_path:
            print(f"Visualization saved to: {output_path}")
        else:
            print("Failed to create visualization")