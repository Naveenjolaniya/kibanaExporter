#!/usr/bin/env python3

import json
import pandas as pd
import os
import logging

# Default variables
DEFAULT_NDJSON_FILE = "./export1/ndjson/admin.ndjson"
DEFAULT_OUTPUT_DIR = "./output"
ENVIRONMENT_PREFIXES = ['Dev:', 'Test:', 'Sim:', 'Live:']
LOG_FILE = "./process.log"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

def modify_with_prefix(obj, prefix):
    # Base case: if obj is not a dictionary, return it as is
    if isinstance(obj, dict):
        modified_obj = {}
        for key, value in obj.items():
            if isinstance(value, dict):
                # Recursively modify nested dictionaries
                modified_value = modify_with_prefix(value, prefix)
            elif isinstance(value, list):
                # Apply prefix logic to each item in the list
                modified_value = [modify_with_prefix(item, prefix) for item in value]
            else:
                # Apply prefix logic to non-dictionary values
                modified_value = f"{prefix}{value}" if '*' in str(value) else value

            modified_obj[key] = modified_value
        return modified_obj
    elif isinstance(obj, list):
        # Apply prefix logic to each item in the list
        return [modify_with_prefix(item, prefix) for item in obj]
    else:
        # Apply prefix logic to non-dictionary values
        return f"{prefix}{obj}" if '*' in str(obj) else obj

# Function to extract and modify attributes from NDJSON
def extract_and_modify_attributes(ndjson_file, output_dir, prefixes):
    logging.info(f"Starting extraction and modification process for file: {ndjson_file}")

    # Extract space name from NDJSON file path
    space_name = os.path.splitext(os.path.basename(ndjson_file))[0]

    # Load NDJSON data
    with open(ndjson_file, 'r') as file:
        original_objects = [json.loads(line) for line in file]
    logging.info(f"Loaded {len(original_objects)} objects from NDJSON file.")

    for prefix in prefixes:
        attributes_list = []
        modified_objects = []
        references_list = []
        searchSourceJSON_list = []
        panelsJSON_list = []

        for obj in original_objects:
            # Specifically modify attributes field
            attributes = obj.get('attributes', {})
            attributes['id'] = obj.get('id', '')

            modified_attributes = modify_with_prefix(attributes, prefix)
            attributes_list.append(modified_attributes)

            # Specifically modify references field
            references = obj.get('references', {})
            modified_references = modify_with_prefix(references, prefix)
            references_list.append(modified_references)

            # Modify the entire object, including nested objects
            modified_obj = modify_with_prefix(obj, prefix)
            modified_objects.append(modified_obj)

            # Specifically modify searchSourceJSON field
            searchSourceJSON = obj.get('searchSourceJSON', {})
            modified_searchSourceJSON = modify_with_prefix(searchSourceJSON, prefix)
            searchSourceJSON_list.append(modified_searchSourceJSON)

            # Specifically modify panelsJSON field
            panelsJSON = obj.get('panelsJSON', {})
            modified_panelsJSON = modify_with_prefix(panelsJSON, prefix)
            panelsJSON_list.append(modified_panelsJSON)

            # Update the object with modified attributes and references
            modified_obj['attributes'] = modified_attributes
            modified_obj['references'] = modified_references
            modified_obj['searchSourceJSON'] = modified_searchSourceJSON
            modified_obj['panelsJSON'] = modified_panelsJSON

        # Create a DataFrame from the list of modified attributes
        df = pd.DataFrame(attributes_list)

        # Create environment-specific folder
        env_dir = os.path.join(output_dir, prefix.strip(':'))
        if not os.path.exists(env_dir):
            os.makedirs(env_dir)

        # Create subdirectories for Excel and NDJSON files
        excel_dir = os.path.join(env_dir, 'excel')
        ndjson_dir = os.path.join(env_dir, 'ndjson')
        if not os.path.exists(excel_dir):
            os.makedirs(excel_dir)
        if not os.path.exists(ndjson_dir):
            os.makedirs(ndjson_dir)

        # Save the DataFrame to an Excel file
        excel_path = os.path.join(excel_dir, f'modified_object_attributes_{prefix.strip(":")}.xlsx')
        df.to_excel(excel_path, index=False)
        logging.info(f"Extracted and modified object attributes to Excel for {prefix.strip(':')}: {excel_path}")

        # Save modified objects to NDJSON file, including space name
        ndjson_path = os.path.join(ndjson_dir, f'{space_name}_modified_objects_{prefix.strip(":")}.ndjson')
        with open(ndjson_path, 'w') as file:
            for obj in modified_objects:
                file.write(json.dumps(obj) + '\n')
        logging.info(f"Modified objects saved to NDJSON for {prefix.strip(':')}: {ndjson_path}")

    logging.info("Extraction and modification process completed.")

# Main function
def main():
    ndjson_file = input(f"Enter path to NDJSON file (default: {DEFAULT_NDJSON_FILE}): ") or DEFAULT_NDJSON_FILE
    output_dir = input(f"Enter output directory (default: {DEFAULT_OUTPUT_DIR}): ") or DEFAULT_OUTPUT_DIR

    extract_and_modify_attributes(ndjson_file, output_dir, ENVIRONMENT_PREFIXES)

if __name__ == "__main__":
    main()
