#!/usr/bin/env python3
"""
Google Drive File Renaming Script
================================
Standalone script to rename files in Google Drive using the service account.

Usage:
    python rename_drive_file.py <file_id> <new_name>
    
Example:
    python rename_drive_file.py 1ABC123def456 "New File Name.pdf"
    
Requirements:
    - google_credentials.json file in the same directory
    - Google API Client library installed
"""

import sys
import os
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
        print(f"Error initializing Google Drive service: {e}")
        return None

def get_file_info(drive_service, file_id):
    """Get current file information"""
    try:
        file_info = drive_service.files().get(fileId=file_id).execute()
        return file_info
    except Exception as e:
        print(f"Error getting file info: {e}")
        return None

def rename_file(drive_service, file_id, new_name):
    """Rename a file in Google Drive"""
    try:
        # Get current file info first
        current_file = get_file_info(drive_service, file_id)
        if not current_file:
            return False, "Could not retrieve current file information"
        
        print(f"Current file name: '{current_file.get('name')}'")
        print(f"New file name: '{new_name}'")
        
        # Update the file name
        body = {'name': new_name}
        updated_file = drive_service.files().update(
            fileId=file_id,
            body=body
        ).execute()
        
        return True, f"File renamed successfully to: {updated_file.get('name')}"
        
    except Exception as e:
        return False, f"Error renaming file: {str(e)}"

def main():
    """Main function"""
    # Check arguments
    if len(sys.argv) != 3:
        print("Usage: python rename_drive_file.py <file_id> <new_name>")
        print("Example: python rename_drive_file.py 1ABC123def456 'New File Name.pdf'")
        sys.exit(1)
    
    file_id = sys.argv[1]
    new_name = sys.argv[2]
    
    # Check if credentials file exists
    if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        print(f"Error: {GOOGLE_CREDENTIALS_PATH} not found")
        print("Please ensure the Google service account credentials file is in the same directory")
        sys.exit(1)
    
    # Initialize Google Drive service
    print("Initializing Google Drive service...")
    drive_service = get_drive_service()
    if not drive_service:
        print("Failed to initialize Google Drive service")
        sys.exit(1)
    
    # Get current file info
    print(f"Getting file information for ID: {file_id}")
    current_file = get_file_info(drive_service, file_id)
    if not current_file:
        print("Failed to get file information")
        sys.exit(1)
    
    # Rename the file
    print(f"Renaming file...")
    success, message = rename_file(drive_service, file_id, new_name)
    
    if success:
        print(f"✅ SUCCESS: {message}")
    else:
        print(f"❌ ERROR: {message}")
        sys.exit(1)

if __name__ == "__main__":
    main()