# ===========================
# Script 2: modify_ndjson_env.py
# ===========================

import argparse
import json
import os
from pathlib import Path
import logging
import re
import sys

def setup_file_logging(log_file_path):
    logger = logging.getLogger("modify_ndjson")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')

    file_handler = logging.FileHandler(log_file_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

def modify_value(value, env_prefix):
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            modified = modify_dict(parsed, env_prefix)
            return json.dumps(modified)
        except (json.JSONDecodeError, TypeError):
            if '*' in value and not value.startswith(f"{env_prefix}:"):
                return f"{env_prefix}:{value}"
            return value
    elif isinstance(value, list):
        return [modify_value(v, env_prefix) for v in value]
    elif isinstance(value, dict):
        return modify_dict(value, env_prefix)
    return value

def modify_dict(d, env_prefix):
    return {k: modify_value(v, env_prefix) for k, v in d.items()}

def modify_ndjson_file(input_path, output_path, env_prefix, logger):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(input_path, 'r') as infile, open(output_path, 'w') as outfile:
        for line_num, line in enumerate(infile, start=1):
            try:
                obj = json.loads(line)
                if 'attributes' in obj:
                    obj['attributes'] = modify_dict(obj['attributes'], env_prefix)
                outfile.write(json.dumps(obj) + '\n')
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse line {line_num} in {input_path}: {e}")

def get_input_or_default(prompt, default):
    try:
        user_input = input(f"{prompt} [Default: {default}]: ").strip()
        return user_input if user_input else default
    except EOFError:
        return default

def main():
    parser = argparse.ArgumentParser(description="Kibana NDJSON Tool with mode support")
    parser.add_argument('--mode', choices=['export', 'modify'], help='Mode of operation: export or modify')
    parser.add_argument('--input-ndjson', help='Input NDJSON file path (for modify mode)')
    parser.add_argument('--output-dir', help='Directory to store modified files')
    parser.add_argument('--env', choices=['dev', 'test', 'sim', 'live', 'all'], help='Environment prefix to add')
    args = parser.parse_args()

    mode = args.mode or get_input_or_default("Enter mode (export or modify)", "export")

    if mode == 'export':
        print("Export mode selected. Please run export_kibana_data.py")
        return

    elif mode == 'modify':
        input_ndjson = args.input_ndjson or get_input_or_default("Enter input NDJSON path", "./input.ndjson")
        output_dir = args.output_dir or get_input_or_default("Enter output directory", "./modified_output")
        env = args.env or get_input_or_default("Enter environment (dev, test, sim, live, all)", "dev")

        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        logger = setup_file_logging(output_dir_path / "modification.log")

        try:
            envs = ['dev', 'test', 'sim', 'live'] if env == 'all' else [env]
            input_path = Path(input_ndjson)

            for env_item in envs:
                env_output_dir = output_dir_path / env_item
                output_file = env_output_dir / input_path.name
                logger.info(f"Modifying for environment: {env_item}")
                modify_ndjson_file(input_path, output_file, env_item, logger)
                logger.info(f"Output written to: {output_file}")

        except Exception as e:
            logger.exception(f"An error occurred during modification: {e}")
            sys.exit(1)

if __name__ == '__main__':
    main()
