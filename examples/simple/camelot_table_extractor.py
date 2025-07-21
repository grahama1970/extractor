"""
Module: camelot_table_extractor.py
Description: Implementation of camelot table extractor functionality

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

Row1,Data1\nRow2,Data2\n",
                        "json": '{"Col1":{"0":"Row1","1":"Row2"},"Col2":{"0":"Data1","1":"Data2"}}',
                        "html": "<table border=\"1\"><tr><th>Col1</th><th>Col2</th></tr><tr><td>Row1</td><td>Data1</td></tr><tr><td>Row2</td><td>Data2</td></tr></table>",
                        "raw_text": [["Col1", "Col2"], ["Row1", "Data1"], ["Row2", "Data2"]],
                        "parsing_report": {"whitespace": 0},
                        "dataframe": [{"Col1": "Row1", "Col2": "Data1"}, {"Col1": "Row2", "Col2": "Data2"}]
                    }]
                }
                
                # Save to files
                save_tables_to_files(mock_results, temp_dir)
                
                # Check if files were created
                files_to_check = ["table_1.csv", "table_1.json", "table_1.html", "all_tables.json"]
                for file_name in files_to_check:
                    file_path = os.path.join(temp_dir, file_name)
                    if not os.path.exists(file_path):
                        all_validation_failures.append(f"Expected file {file_name} to be created, but it wasn't")
                
                logger.info("✅ File saving test passed")
        except Exception as e:
            logger.error(f"File saving test error: {e}")
            import traceback
            traceback.print_exc()
            all_validation_failures.append(f"File saving test error: {e}")
        
        # Output final results
        if all_validation_failures:
            print(f"\n❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
            for i, failure in enumerate(all_validation_failures):
                print(f"  {i+1}. {failure}")
            sys.exit(1)  # Exit with error code
        else:
            print(f"\n✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
            print("Camelot table extractor is validated and working correctly")
            sys.exit(0)  # Exit with success code
    
    # Normal execution: extract tables from the specified PDF
    pdf_path = args.input_pdf
    logger.info(f"Extracting tables from {pdf_path}, pages {args.pages}")
    
    if args.flavor == "both":
        results = extract_tables_with_both_flavors(
            pdf_path, pages=args.pages, line_scale=args.line_scale
        )
    else:
        results = extract_tables_with_camelot(
            pdf_path, pages=args.pages, flavor=args.flavor, line_scale=args.line_scale
        )
    
    # Print basic info
    logger.info(f"Extraction status: {results['extraction_status']}")
    if results['error']:
        logger.error(f"Error: {results['error']}")
    
    logger.info(f"Found {results['table_count']} tables")
    
    # Save tables to files if output directory specified
    if args.output_dir:
        save_tables_to_files(results, args.output_dir, formats=args.formats)
    else:
        # Print table info to console
        for i, table in enumerate(results.get('tables', [])):
            print(f"\nTable {i+1}:")
            print(f"Page: {table['page']}")
            print(f"Flavor: {table['flavor']}")
            print(f"Accuracy: {table['accuracy']:.2f}%")
            print(f"Dimensions: {table['shape'][0]} rows × {table['shape'][1]} columns")
            print("\nCSV preview:")
            print(table['csv'][:500] + "..." if len(table['csv']) > 500 else table['csv'])