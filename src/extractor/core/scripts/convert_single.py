"""
Module: convert_single.py
Description: Functions for convert single operations

External Dependencies:
- click: [Documentation URL]
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

import os

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"  # Transformers uses .isin for a simple op, which is not supported on MPS

import time
import click

from extractor.core.config.parser import ConfigParser
from extractor.core.config.printer import CustomClickPrinter
from extractor.core.logger import configure_logging
from extractor.core.models import create_model_dict
from extractor.core.output import save_output

configure_logging()


@click.command(cls=CustomClickPrinter, help="Convert a single PDF to markdown.")
@click.argument("fpath", type=str)
@ConfigParser.common_options
def convert_single_cli(fpath: str, **kwargs):
    models = create_model_dict()
    start = time.time()
    config_parser = ConfigParser(kwargs)

    converter_cls = config_parser.get_converter_cls()
    converter = converter_cls(
        config=config_parser.generate_config_dict(),
        artifact_dict=models,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service()
    )
    rendered = converter(fpath)
    import pdb; pdb.set_trace()
    out_folder = config_parser.get_output_folder(fpath)
    with open("/home/graham/workspace/experiments/extractor/output_path.txt", "w") as f:
        f.write(out_folder)
    save_output(rendered, out_folder, config_parser.get_base_filename(fpath))

    print(f"Saved markdown to {out_folder}")
    print(f"Total time: {time.time() - start}")
