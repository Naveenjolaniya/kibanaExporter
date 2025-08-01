#!/usr/bin/env python3

import argparse
import requests
import logging
import os
import json
import pandas as pd
import getpass
import base64

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
def export_objects(session, url, export_dir, space, object_types, all_summaries):
    logging.info(f"object_types: {object_types}")
    space_id = space['id']
    export_url = f"{url}/s/{space_id}/api/saved_objects/_export"
    params = {"type": object_types}
    logging.info(f"Requesting URL: {export_url} with params: {json.dumps(params)}")
    try:
        response = session.post(export_url, json=params, verify=False)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to export objects for space {space_id}: {e}")
        return

    # Create subdirectories for NDJSON and Excel files
    ndjson_dir = os.path.join(export_dir, space_id, 'ndjson')
    excel_dir = os.path.join(export_dir, space_id, 'excel')
    os.makedirs(ndjson_dir, exist_ok=True)
    os.makedirs(excel_dir, exist_ok=True)

    # Save NDJSON file
    ndjson_path = os.path.join(ndjson_dir, f"{space_id}.ndjson")
    with open(ndjson_path, 'wb') as file:
        file.write(response.content)
    logging.info(f"Export successful for space {space_id}: {ndjson_path}")

    # Export objects to Excel
    export_objects_to_excel(response.content, excel_dir, space_id, all_summaries)

# Function to export objects to Excel with sheets and collect summary
def export_objects_to_excel(ndjson_content, excel_dir, space_id, all_summaries):
    try:
        objects = [json.loads(line) for line in ndjson_content.decode('utf-8').splitlines()]
        df_all = pd.DataFrame(objects)

        dashboards = [obj for obj in objects if obj.get("type") == "dashboard"]
        rules = [obj for obj in objects if obj.get("type") == "rule"]
        searches = [obj for obj in objects if obj.get("type") == "search"]

        df_dashboards = pd.DataFrame(dashboards)
        df_rules = pd.DataFrame(rules)
        df_searches = pd.DataFrame(searches)

        summary_data = {
            "space_id": space_id,
            "dashboard_count": len(dashboards),
            "rule_count": len(rules),
            "search_count": len(searches),
            "total_count": len(objects)
        }
        df_summary = pd.DataFrame([summary_data])
        all_summaries.append(summary_data)

        excel_path = os.path.join(excel_dir, f"{space_id}_objects.xlsx")
        with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
            df_all.to_excel(writer, index=False, sheet_name="all_objects")
            df_dashboards.to_excel(writer, index=False, sheet_name="dashboards")
            df_rules.to_excel(writer, index=False, sheet_name="rules")
            df_searches.to_excel(writer, index=False, sheet_name="searches")
            df_summary.to_excel(writer, index=False, sheet_name="client_summary")

        logging.info(f"Exported objects to Excel with sheets for space {space_id}: {excel_path}")
    except Exception as e:
        logging.error(f"Failed to export to Excel for space {space_id}: {e}")

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
    parser.add_argument('--types', nargs='+', help="Specify types of objects to export, separated by spaces. If omitted, all types are exported.")
    parser.add_argument('--spaces', nargs='+', help="Specify space IDs to export. If omitted, all spaces are exported.")

    args = parser.parse_args()

    kibana_url = args.kibana_url or input("Enter Kibana URL (default: https://elastic.sys.dom:5601): ") or DEFAULT_KIBANA_URL
    export_dir = args.export_dir or input("Enter export directory (default: ./export): ") or DEFAULT_EXPORT_DIR

    # Prompt for auth method
    print("Select authentication method:")
    print("1. API Key")
    print("2. Username & Password")
    choice = input("Enter choice (1 or 2): ").strip()

    session = requests.Session()
    session.headers.update({'kbn-xsrf': 'true'})

    if choice == "1":
        api_key = input("Enter API key: ")
        session.headers.update({'Authorization': f'ApiKey {api_key}'})
    elif choice == "2":
        username = input("Enter username: ")
        password = getpass.getpass("Enter password: ")
        auth_string = f"{username}:{password}"
        b64_auth = base64.b64encode(auth_string.encode()).decode()
        session.headers.update({'Authorization': f'Basic {b64_auth}'})
    else:
        logging.error("Invalid choice. Exiting.")
        return

    object_types = args.types if args.types else DEFAULT_OBJECT_TYPES
    spaces = args.spaces if args.spaces else DEFAULT_SPACES

    if not os.path.exists(export_dir):
        os.makedirs(export_dir)

    try:
        all_spaces = get_spaces(session, kibana_url)
        validate_spaces(spaces, all_spaces)
        spaces_to_export = all_spaces if not spaces else [space for space in all_spaces if space['id'] in spaces]

        export_space_details(spaces_to_export, export_dir)

        all_summaries = []
        for space in spaces_to_export:
            export_objects(session, kibana_url, export_dir, space, object_types, all_summaries)

        # Save global client summary
        if all_summaries:
            df_all_summary = pd.DataFrame(all_summaries)
            summary_path = os.path.join(export_dir, "client_summary.xlsx")
            df_all_summary.to_excel(summary_path, index=False)
            logging.info(f"Global client summary saved: {summary_path}")

    except Exception as e:
        logging.error(f"An error occurred during export: {e}")

if __name__ == "__main__":
    main()
