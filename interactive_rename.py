#!/usr/bin/env python3
"""
Interactive Google Drive File Renaming Script
============================================
User-friendly interactive script for renaming Google Drive files.

Usage:
    python interactive_rename.py
    
The script will guide you through the process step by step.
"""

import os
import sys
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
        print(f"❌ Error getting file info: {e}")
        return None

def rename_file(drive_service, file_id, new_name):
    """Rename a file in Google Drive"""
    try:
        # Update the file name
        body = {'name': new_name}
        updated_file = drive_service.files().update(
            fileId=file_id,
            body=body
        ).execute()
        
        return True, f"File renamed successfully to: {updated_file.get('name')}"
        
    except Exception as e:
        return False, f"Error renaming file: {str(e)}"

def get_file_input():
    """Get file ID from user input"""
    print("\\n📁 How would you like to specify the file?")
    print("1. Enter Google Drive file ID directly")
    print("2. Paste Google Drive URL")
    
    choice = input("\\nEnter your choice (1 or 2): ").strip()
    
    if choice == "1":
        file_id = input("\\nEnter the Google Drive file ID: ").strip()
        if not file_id:
            print("❌ File ID cannot be empty")
            return None
        return file_id
    
    elif choice == "2":
        url = input("\\nPaste the Google Drive URL: ").strip()
        if not url:
            print("❌ URL cannot be empty")
            return None
        
        file_id = extract_file_id_from_url(url)
        if not file_id:
            print("❌ Could not extract file ID from URL")
            print("Please make sure the URL is a valid Google Drive file URL")
            return None
        
        print(f"📎 Extracted file ID: {file_id}")
        return file_id
    
    else:
        print("❌ Invalid choice. Please enter 1 or 2")
        return None

def main():
    """Main interactive function"""
    print("🔄 Interactive Google Drive File Renaming Tool")
    print("=" * 50)
    
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
    
    print("✅ Google Drive service initialized successfully")
    
    while True:
        # Get file ID
        file_id = get_file_input()
        if not file_id:
            continue
        
        # Get current file info
        print(f"\\n🔍 Getting file information...")
        current_file = get_file_info(drive_service, file_id)
        if not current_file:
            print("❌ Failed to get file information")
            print("Please check the file ID and make sure the service account has access")
            continue
        
        # Display current file info
        current_name = current_file.get('name', 'Unknown')
        file_type = current_file.get('mimeType', 'Unknown')
        
        print(f"\\n📄 Current file information:")
        print(f"   Name: {current_name}")
        print(f"   Type: {file_type}")
        print(f"   ID: {file_id}")
        
        # Get new name
        new_name = input(f"\\n✏️  Enter new name for the file: ").strip()
        if not new_name:
            print("❌ New name cannot be empty")
            continue
        
        # Confirm the rename
        print(f"\\n🔄 Rename confirmation:")
        print(f"   From: '{current_name}'")
        print(f"   To: '{new_name}'")
        
        confirm = input("\\nProceed with rename? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ Rename cancelled")
            continue
        
        # Perform the rename
        print(f"\\n🔄 Renaming file...")
        success, message = rename_file(drive_service, file_id, new_name)
        
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        # Ask if user wants to rename another file
        another = input("\\nWould you like to rename another file? (y/n): ").strip().lower()
        if another not in ['y', 'yes']:
            break
    
    print("\\n👋 Thank you for using the Google Drive File Renaming Tool!")

if __name__ == "__main__":
    main()