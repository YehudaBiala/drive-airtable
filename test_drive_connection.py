#!/usr/bin/env python3
"""
Google Drive Connection Test Script
==================================
Test script to verify Google Drive service account credentials and connection.

Usage:
    python test_drive_connection.py
"""

import os
import sys
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configuration
GOOGLE_CREDENTIALS_PATH = 'google_credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive']

def test_drive_connection():
    """Test Google Drive connection and list accessible files"""
    print("🔧 Testing Google Drive Connection")
    print("=" * 40)
    
    # Check if credentials file exists
    if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        print(f"❌ Error: {GOOGLE_CREDENTIALS_PATH} not found")
        print("Please ensure the Google service account credentials file is in the same directory")
        return False
    
    print(f"✅ Credentials file found: {GOOGLE_CREDENTIALS_PATH}")
    
    # Initialize Google Drive service
    try:
        print("🔧 Initializing Google Drive service...")
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_PATH,
            scopes=SCOPES
        )
        drive_service = build('drive', 'v3', credentials=credentials)
        print("✅ Google Drive service initialized successfully")
        
        # Get service account info
        print(f"📧 Service account email: {credentials.service_account_email}")
        
    except Exception as e:
        print(f"❌ Error initializing Google Drive service: {e}")
        return False
    
    # Test API access by listing files
    try:
        print("\\n🔍 Testing API access (listing first 10 files)...")
        
        # Query for files the service account has access to
        results = drive_service.files().list(
            pageSize=10,
            fields="nextPageToken, files(id, name, mimeType, owners)"
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            print("⚠️  No files found. This could mean:")
            print("   - No files are shared with the service account")
            print("   - The service account has no access to any files")
            print("   - You need to share files/folders with the service account")
            print(f"   - Service account email: {credentials.service_account_email}")
        else:
            print(f"✅ Found {len(files)} accessible files:")
            print("\\n📁 Accessible files:")
            for i, file in enumerate(files, 1):
                name = file.get('name', 'No name')
                file_id = file.get('id', 'No ID')
                mime_type = file.get('mimeType', 'Unknown type')
                owners = file.get('owners', [])
                owner_names = [owner.get('displayName', 'Unknown') for owner in owners]
                
                print(f"   {i}. {name}")
                print(f"      ID: {file_id}")
                print(f"      Type: {mime_type}")
                print(f"      Owners: {', '.join(owner_names)}")
                print()
        
    except Exception as e:
        print(f"❌ Error testing API access: {e}")
        return False
    
    # Test file operations (try to get info about a specific file if available)
    if files:
        test_file = files[0]
        file_id = test_file.get('id')
        
        try:
            print(f"🔍 Testing file metadata retrieval for: {test_file.get('name')}")
            file_info = drive_service.files().get(fileId=file_id).execute()
            print("✅ File metadata retrieval successful")
            
            # Show some file details
            print(f"   Name: {file_info.get('name')}")
            print(f"   Size: {file_info.get('size', 'Unknown')} bytes")
            print(f"   Modified: {file_info.get('modifiedTime', 'Unknown')}")
            print(f"   Created: {file_info.get('createdTime', 'Unknown')}")
            
        except Exception as e:
            print(f"❌ Error getting file metadata: {e}")
            return False
    
    print("\\n✅ All tests passed! Google Drive connection is working correctly.")
    print("\\n📋 Summary:")
    print(f"   - Credentials: ✅ Valid")
    print(f"   - API Access: ✅ Working")
    print(f"   - Files Found: {len(files)}")
    print(f"   - Service Account: {credentials.service_account_email}")
    
    if len(files) == 0:
        print("\\n💡 To use the rename scripts:")
        print("   1. Share your Google Drive files/folders with the service account")
        print(f"   2. Use this email: {credentials.service_account_email}")
        print("   3. Give 'Editor' permissions to allow renaming")
    
    return True

def main():
    """Main function"""
    success = test_drive_connection()
    
    if not success:
        print("\\n❌ Connection test failed")
        sys.exit(1)
    
    print("\\n🎉 Connection test completed successfully!")
    print("\\nYou can now use the rename scripts:")
    print("   - python rename_drive_file.py <file_id> <new_name>")
    print("   - python batch_rename_drive_files.py --help")
    print("   - python interactive_rename.py")

if __name__ == "__main__":
    main()