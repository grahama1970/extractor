Total tables found: {table_count}")

def test_with_arangodb_renderer():
    """Test with ArangoDB renderer"""
    from marker.models import create_model_dict
    from marker.converters.pdf import PdfConverter
    
    pdf_path = "data/input/2505.03335v2.pdf"
    output_dir = "data/output/test_arangodb"
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n\nTesting with ArangoDB renderer...")
    models = create_model_dict()
    
    converter = PdfConverter(
        artifact_dict=models,
        processor_list=None,  # Use default processors
        renderer="arangodb_json",  # ArangoDB renderer
        config={"output_dir": output_dir}
    )
    
    print(f"Converting {pdf_path}...")
    result = converter(pdf_path)
    
    # Save output
    from marker.output import save_output
    save_output(result, output_dir, "test_arangodb")
    
    print(f"Output saved to {output_dir}")

if __name__ == "__main__":
    # First test basic conversion
    test_basic_conversion()
    
    # Then test with ArangoDB renderer
    test_with_arangodb_renderer()