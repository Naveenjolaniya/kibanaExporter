# =======================
# Script 1: export_kibana_data.py
# =======================

import os
import requests
import argparse
import logging
from pathlib import Path
import json
import pandas as pd
from datetime import datetime

def setup_logger(log_file):
    logger = logging.getLogger("kibana_export")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    fh = logging.FileHandler(log_file)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger

def get_or_input(prompt, default):
    try:
        value = input(f"{prompt} [Default: {default}]: ").strip()
        return value if value else default
    except EOFError:
        return default

def fetch_saved_objects(space, base_url, headers):
    url = f"{base_url}/s/{space}/api/saved_objects/_export"
    payload = {"type": ["dashboard", "visualization", "index-pattern", "rule", "search"], "includeReferencesDeep": True}
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.text

def parse_saved_objects(ndjson_text):
    objects = [json.loads(line) for line in ndjson_text.splitlines() if line.strip()]
    return objects

def extract_summary(objects, object_type):
    rows = []
    for obj in objects:
        if obj.get('type') == object_type:
            attr = obj.get('attributes', {})
            meta = obj.get('meta', {})
            row = {
                "id": obj.get('id'),
                "title": attr.get('title') or attr.get('name'),
                "created_by": attr.get('created_by', 'unknown'),
                "last_used_at": attr.get('last_used_at', ''),
                "description": attr.get('description', ''),
            }
            if object_type == 'dashboard':
                row["visualization_count"] = str(ndjson_text).count('visualization')
            rows.append(row)
    return pd.DataFrame(rows)

def save_outputs(space, ndjson_text, output_path, logger):
    space_path = Path(output_path) / space
    ndjson_path = space_path / "ndjson"
    excel_path = space_path / "excel"
    client_path = space_path / "client_summary"
    for path in [ndjson_path, excel_path, client_path]:
        path.mkdir(parents=True, exist_ok=True)

    # Save NDJSON
    with open(ndjson_path / f"{space}.ndjson", 'w') as f:
        f.write(ndjson_text)

    # Parse and summarize
    objects = parse_saved_objects(ndjson_text)
    for obj_type in ["dashboard", "rule", "index-pattern"]:
        df = extract_summary(objects, obj_type)
        if not df.empty:
            df.to_excel(excel_path / f"{obj_type}s.xlsx", index=False)
            df.to_excel(client_path / f"client_{obj_type}s.xlsx", index=False)

    logger.info(f"Exported and summarized space: {space}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', help='Kibana base URL')
    parser.add_argument('--api-key', help='Kibana API Key')
    parser.add_argument('--output', help='Output directory')
    args = parser.parse_args()

    base_url = args.url or get_or_input("Enter Kibana URL", "http://localhost:5601")
    api_key = args.api_key or get_or_input("Enter Kibana API Key", "your-api-key")
    output_dir = args.output or get_or_input("Enter output directory", "./output")

    logger = setup_logger(Path(output_dir) / "export.log")

    headers = {
        "kbn-xsrf": "true",
        "Authorization": f"ApiKey {api_key}"
    }

    try:
        spaces_resp = requests.get(f"{base_url}/api/spaces/space", headers=headers)
        spaces_resp.raise_for_status()
        spaces = spaces_resp.json()
        for space in spaces:
            space_id = space['id']
            ndjson_text = fetch_saved_objects(space_id, base_url, headers)
            save_outputs(space_id, ndjson_text, output_dir, logger)
    except Exception as e:
        logger.exception("Failed to export Kibana data")

if __name__ == '__main__':
    main()


