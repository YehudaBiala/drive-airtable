#!/usr/bin/env python3
"""
Batch Google Drive File Renaming Script
======================================
Advanced script to rename multiple files in Google Drive.

Usage:
    python batch_rename_drive_files.py --file <file_id> <new_name>
    python batch_rename_drive_files.py --url <drive_url> <new_name>
    python batch_rename_drive_files.py --csv <csv_file>
    python batch_rename_drive_files.py --json <json_file>
    
Examples:
    # Single file by ID
    python batch_rename_drive_files.py --file 1ABC123def456 "New Name.pdf"
    
    # Single file by URL
    python batch_rename_drive_files.py --url "https://drive.google.com/file/d/1ABC123def456/view" "New Name.pdf"
    
    # Batch from CSV file (columns: file_id, new_name)
    python batch_rename_drive_files.py --csv rename_list.csv
    
    # Batch from JSON file
    python batch_rename_drive_files.py --json rename_list.json

CSV Format:
    file_id,new_name
    1ABC123def456,New Name 1.pdf
    1XYZ789ghi012,New Name 2.pdf

JSON Format:
    [
        {"file_id": "1ABC123def456", "new_name": "New Name 1.pdf"},
        {"file_id": "1XYZ789ghi012", "new_name": "New Name 2.pdf"}
    ]
"""

import sys
import os
import argparse
import csv
import json
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configuration
GOOGLE_CREDENTIALS_PATH = 'google_credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """Initialize Google Drive service"""
    try:
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_PATH,
            scopes=SCOPES
        )
        return build('drive', 'v3', credentials=credentials)
    except Exception as e:
        print(f"❌ Error initializing Google Drive service: {e}")
        return None

def extract_file_id_from_url(url):
    """Extract file ID from Google Drive URL"""
    patterns = [
        r'/d/([a-zA-Z0-9-_]+)',  # Standard share URL
        r'id=([a-zA-Z0-9-_]+)',   # Alternative format
        r'file/d/([a-zA-Z0-9-_]+)',  # Another format
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def get_file_info(drive_service, file_id):
    """Get current file information"""
    try:
        file_info = drive_service.files().get(fileId=file_id).execute()
        return file_info
    except Exception as e:
        print(f"❌ Error getting file info for {file_id}: {e}")
        return None

def rename_file(drive_service, file_id, new_name):
    """Rename a file in Google Drive"""
    try:
        # Get current file info first
        current_file = get_file_info(drive_service, file_id)
        if not current_file:
            return False, "Could not retrieve current file information"
        
        current_name = current_file.get('name', 'Unknown')
        print(f"  Current: '{current_name}'")
        print(f"  New: '{new_name}'")
        
        # Update the file name
        body = {'name': new_name}
        updated_file = drive_service.files().update(
            fileId=file_id,
            body=body
        ).execute()
        
        return True, f"Renamed to: {updated_file.get('name')}"
        
    except Exception as e:
        return False, f"Error renaming file: {str(e)}"

def process_single_file(drive_service, file_id, new_name):
    """Process a single file rename"""
    print(f"\n📁 Processing file ID: {file_id}")
    success, message = rename_file(drive_service, file_id, new_name)
    
    if success:
        print(f"✅ SUCCESS: {message}")
    else:
        print(f"❌ ERROR: {message}")
    
    return success

def process_csv_file(drive_service, csv_file):
    """Process CSV file with file_id,new_name format"""
    if not os.path.exists(csv_file):
        print(f"❌ CSV file not found: {csv_file}")
        return False
    
    success_count = 0
    total_count = 0
    
    try:
        with open(csv_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                total_count += 1
                file_id = row.get('file_id', '').strip()
                new_name = row.get('new_name', '').strip()
                
                if not file_id or not new_name:
                    print(f"❌ Skipping row {total_count}: Missing file_id or new_name")
                    continue
                
                if process_single_file(drive_service, file_id, new_name):
                    success_count += 1
    
    except Exception as e:
        print(f"❌ Error processing CSV file: {e}")
        return False
    
    print(f"\n📊 Results: {success_count}/{total_count} files renamed successfully")
    return success_count > 0

def process_json_file(drive_service, json_file):
    """Process JSON file with array of {file_id, new_name} objects"""
    if not os.path.exists(json_file):
        print(f"❌ JSON file not found: {json_file}")
        return False
    
    success_count = 0
    total_count = 0
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            print(f"❌ JSON file must contain an array of objects")
            return False
        
        for item in data:
            total_count += 1
            
            if not isinstance(item, dict):
                print(f"❌ Skipping item {total_count}: Not a valid object")
                continue
            
            file_id = item.get('file_id', '').strip()
            new_name = item.get('new_name', '').strip()
            
            if not file_id or not new_name:
                print(f"❌ Skipping item {total_count}: Missing file_id or new_name")
                continue
            
            if process_single_file(drive_service, file_id, new_name):
                success_count += 1
    
    except Exception as e:
        print(f"❌ Error processing JSON file: {e}")
        return False
    
    print(f"\n📊 Results: {success_count}/{total_count} files renamed successfully")
    return success_count > 0

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Batch rename Google Drive files')
    group = parser.add_mutually_exclusive_group(required=True)
    
    group.add_argument('--file', nargs=2, metavar=('FILE_ID', 'NEW_NAME'),
                      help='Rename single file by ID')
    group.add_argument('--url', nargs=2, metavar=('DRIVE_URL', 'NEW_NAME'),
                      help='Rename single file by URL')
    group.add_argument('--csv', metavar='CSV_FILE',
                      help='Batch rename from CSV file')
    group.add_argument('--json', metavar='JSON_FILE',
                      help='Batch rename from JSON file')
    
    args = parser.parse_args()
    
    # Check if credentials file exists
    if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        print(f"❌ Error: {GOOGLE_CREDENTIALS_PATH} not found")
        print("Please ensure the Google service account credentials file is in the same directory")
        sys.exit(1)
    
    # Initialize Google Drive service
    print("🔧 Initializing Google Drive service...")
    drive_service = get_drive_service()
    if not drive_service:
        print("❌ Failed to initialize Google Drive service")
        sys.exit(1)
    
    # Process based on arguments
    success = False
    
    if args.file:
        file_id, new_name = args.file
        success = process_single_file(drive_service, file_id, new_name)
    
    elif args.url:
        drive_url, new_name = args.url
        file_id = extract_file_id_from_url(drive_url)
        if not file_id:
            print(f"❌ Could not extract file ID from URL: {drive_url}")
            sys.exit(1)
        print(f"📎 Extracted file ID: {file_id}")
        success = process_single_file(drive_service, file_id, new_name)
    
    elif args.csv:
        print(f"📄 Processing CSV file: {args.csv}")
        success = process_csv_file(drive_service, args.csv)
    
    elif args.json:
        print(f"📄 Processing JSON file: {args.json}")
        success = process_json_file(drive_service, args.json)
    
    if not success:
        print(f"\n❌ Operation failed")
        sys.exit(1)
    
    print(f"\n✅ Operation completed successfully")

if __name__ == "__main__":
    main()