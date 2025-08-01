#!/usr/bin/env python3

import argparse
import requests
import logging
import os
import json
import pandas as pd

# Default variables
DEFAULT_KIBANA_URL = "https://elastic.sys.dom:5601"
DEFAULT_EXPORT_DIR = "./export"
DEFAULT_OBJECT_TYPES = ["*"]
DEFAULT_SPACES = []
LOG_FILE = "./export.log"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Function to retrieve all spaces
def get_spaces(session, url):
    response = session.get(f"{url}/api/spaces/space", verify=False)
    response.raise_for_status()
    return response.json()

# Function to save space details to a JSON file
def export_space_details(spaces, export_dir):
    with open(os.path.join(export_dir, 'spaces_details.json'), 'w') as file:
        json.dump(spaces, file)
    logging.info("Exported space details.")

# Function to export objects from spaces
def export_objects(session, url, export_dir, space, object_types):
    logging.info(f"object_types: {object_types}")
    space_id = space['id']
    export_url = f"{url}/s/{space_id}/api/saved_objects/_export"
    params = {"type": object_types}
    logging.info(f"Requesting URL: {export_url} with params: {json.dumps(params)}")
    response = session.post(export_url, json=params, verify=False)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logging.error(f"Failed to export objects for space {space_id}: {e}")
        logging.error(f"Response was: {response.text}")
        return

    # Create subdirectories for NDJSON and Excel files
    ndjson_dir = os.path.join(export_dir, 'ndjson')
    excel_dir = os.path.join(export_dir, 'excel')
    os.makedirs(ndjson_dir, exist_ok=True)
    os.makedirs(excel_dir, exist_ok=True)

    # Save NDJSON file
    ndjson_path = os.path.join(ndjson_dir, f"{space_id}.ndjson")
    with open(ndjson_path, 'wb') as file:
        file.write(response.content)
    logging.info(f"Export successful for space {space_id}: {ndjson_path}")

    # Export objects to Excel
    export_objects_to_excel(response.content, excel_dir, space_id)

# Function to export objects to Excel
def export_objects_to_excel(ndjson_content, excel_dir, space_id):
    # Parse NDJSON content into a list of dictionaries
    objects = [json.loads(line) for line in ndjson_content.decode('utf-8').splitlines()]
    # Filter objects to include only dashboards and rules
    #filtered_objects = [obj for obj in objects if obj['_type'] in ['dashboard', 'rule']]

    # Create a DataFrame from the list of objects
    df1 = pd.DataFrame(objects)

    # Create a DataFrame from the filtered list of objects
    # df = pd.DataFrame(filtered_objects)

    # Save the DataFrame to an Excel file
    excel_path = os.path.join(excel_dir, f"{space_id}_objects.xlsx")
    df1.to_excel(excel_path, index=False)

    # Select only the required columns
    #required_columns = ['name', 'created_by', 'updated_by']
    #df_filtered = df[required_columns]

    # Specify the new folder path for saving the Excel file
    #new_excel_dir = os.path.join(excel_dir, 'filtered')
    #os.makedirs(new_excel_dir, exist_ok=True)

    logging.info(f"Exported objects to Excel for space {space_id}: {excel_path}")

    # Save the filtered DataFrame to an Excel file in the new folder
    # excel_path = os.path.join(new_excel_dir, f"{space_id}_filtered_objects.xlsx")
    # df_filtered.to_excel(excel_path, index=False)
    # logging.info(f"Exported filtered objects to Excel for space {space_id}: {excel_path}")

# Function to validate spaces
def validate_spaces(spaces, all_spaces):
    valid_spaces = [space['id'] for space in all_spaces]
    invalid_spaces = [space for space in spaces if space not in valid_spaces] if spaces else []

    if invalid_spaces:
        logging.error("The following specified spaces do not exist: " + ", ".join(invalid_spaces))
        logging.error("Exiting due to invalid input.")
        exit(1)

# Main function
def main():
    parser = argparse.ArgumentParser(
        description="Export objects and details from specified spaces in Kibana, or all spaces if none are specified.",
        epilog="Example: export_kibana.py https://elastic.sys.dom:5601 /path/to/export --spaces space1 space2 --types dashboard visualization")
    parser.add_argument('kibana_url', nargs='?', help="Kibana URL, e.g., https://elastic.sys.dom:5601")
    parser.add_argument('export_dir', nargs='?', help="Directory to save the NDJSON files and space details")
    parser.add_argument('--types', nargs='+',
                        help="Specify types of objects to export, separated by spaces (e.g., dashboard visualization). If omitted, all types are exported.")
    parser.add_argument('--spaces', nargs='+',
                        help="Specify space IDs to export, separated by spaces (e.g., space1, space2). If omitted, all spaces are exported.")
    parser.add_argument('--api_key', help="API key for authentication")

    args = parser.parse_args()

    # Prompt for missing arguments
    kibana_url = args.kibana_url or input("Enter Kibana URL (default: https://elastic.sys.dom:5601): ") or DEFAULT_KIBANA_URL
    export_dir = args.export_dir or input("Enter export directory (default: ./export): ") or DEFAULT_EXPORT_DIR
    api_key = args.api_key or input("Enter API key: ")

    object_types = args.types if args.types else DEFAULT_OBJECT_TYPES
    spaces = args.spaces if args.spaces else DEFAULT_SPACES

    session = requests.Session()
    session.headers.update({'Authorization': f'ApiKey {api_key}', 'kbn-xsrf': 'true'})

    if not os.path.exists(export_dir):
        os.makedirs(export_dir)

    all_spaces = get_spaces(session, kibana_url)

    # Validate the specified spaces before proceeding
    validate_spaces(spaces, all_spaces)

    spaces_to_export = all_spaces if not spaces else [space for space in all_spaces if space['id'] in spaces]
    export_space_details(spaces_to_export, export_dir)
    for space in spaces_to_export:
        export_objects(session, kibana_url, export_dir, space, object_types)

if __name__ == "__main__":
    main()
