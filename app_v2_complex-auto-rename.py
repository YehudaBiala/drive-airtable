#!/usr/bin/env python3
"""
PRODUCTION SERVER - Drive-Airtable Vision Integration
===================================================
This is the DEFINITIVE production server version for Cloudways deployment.
Last Updated: 2025-07-03
Added: Security improvements, logging, request validation

Deploy this file to: ~/public_html/drive-airtable/
Run with: python3 app.py
"""

import os
import sys
import io
import base64
import requests
import tempfile
import datetime
import json
import hashlib
import hmac
import logging
from datetime import datetime as dt

# Add local lib directory to Python path for installed packages
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

# Import PyPDF2 after adding lib to path
import PyPDF2

from flask import Flask, request, jsonify, send_file
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_env():
    """Load environment variables from .env file"""
    env_file = '.env'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value.strip()
        logger.info("Environment variables loaded from .env file")

load_env()

app = Flask(__name__)

# Configuration
GOOGLE_CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH', 'google_credentials.json')
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME', 'Files')
TEMP_FILES_DIR = os.getenv('TEMP_FILES_DIR', './temp_files')
DEBUG_SAVE_FILES = os.getenv('DEBUG_SAVE_FILES', 'false').lower() == 'true'
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')  # Optional webhook validation
FLASK_SERVER_TOKEN = os.getenv('FLASK_SERVER_TOKEN')  # Bearer token for API authentication

# Ensure temp directory exists
os.makedirs(TEMP_FILES_DIR, exist_ok=True)

def validate_request_data(data, required_fields):
    """Validate that request contains required fields"""
    if not data:
        return False, "No data provided"
    
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
    
    return True, None

def validate_webhook_signature(request_data, signature_header):
    """Validate webhook signature if WEBHOOK_SECRET is set"""
    if not WEBHOOK_SECRET:
        return True  # Skip validation if no secret is configured
    
    if not signature_header:
        logger.warning("Webhook signature missing")
        return False
    
    # Generate expected signature
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        request_data,
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures
    provided_signature = signature_header.replace('sha256=', '')
    is_valid = hmac.compare_digest(expected_signature, provided_signature)
    
    if not is_valid:
        logger.warning("Invalid webhook signature")
    
    return is_valid

def validate_bearer_token(auth_header):
    """Validate Bearer token if FLASK_SERVER_TOKEN is set"""
    if not FLASK_SERVER_TOKEN:
        return True  # Skip validation if no token is configured
    
    if not auth_header:
        logger.warning("Authorization header missing")
        return False
    
    # Extract token from "Bearer <token>" format
    try:
        auth_type, token = auth_header.split(' ', 1)
        if auth_type.lower() != 'bearer':
            logger.warning(f"Invalid auth type: {auth_type}")
            return False
        
        is_valid = hmac.compare_digest(token, FLASK_SERVER_TOKEN)
        if not is_valid:
            logger.warning("Invalid bearer token")
        return is_valid
    except Exception as e:
        logger.warning(f"Bearer token validation error: {e}")
        return False

def get_drive_service():
    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH,
        scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=credentials)


def save_debug_file(file_content, file_name, file_id):
    """Save file to temp directory for debugging if enabled"""
    if not DEBUG_SAVE_FILES:
        return None
        
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in file_name if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        debug_filename = f"{timestamp}_{file_id}_{safe_name}"
        debug_path = os.path.join(TEMP_FILES_DIR, debug_filename)
        
        with open(debug_path, 'wb') as f:
            f.write(file_content)
        
        print(f"DEBUG: Saved file to {debug_path}")
        return debug_path
    except Exception as e:
        print(f"DEBUG: Failed to save file: {e}")
        return None

def cleanup_old_temp_files(max_age_hours=24):
    """Remove temp files older than max_age_hours"""
    try:
        current_time = datetime.datetime.now()
        
        # Clean up main temp directory
        for filename in os.listdir(TEMP_FILES_DIR):
            filepath = os.path.join(TEMP_FILES_DIR, filename)
            if os.path.isfile(filepath):
                file_time = datetime.datetime.fromtimestamp(os.path.getctime(filepath))
                if (current_time - file_time).total_seconds() > (max_age_hours * 3600):
                    os.remove(filepath)
                    print(f"Cleaned up old temp file: {filename}")
        
        # Clean up attachments directory (short retention - automation downloads immediately)
        attachments_dir = os.path.join(TEMP_FILES_DIR, 'attachments')
        if os.path.exists(attachments_dir):
            # Keep attachments for only 5 minutes - automation downloads immediately
            attachment_max_age_seconds = 5 * 60  # 5 minutes
            for filename in os.listdir(attachments_dir):
                filepath = os.path.join(attachments_dir, filename)
                if os.path.isfile(filepath):
                    file_time = datetime.datetime.fromtimestamp(os.path.getctime(filepath))
                    if (current_time - file_time).total_seconds() > attachment_max_age_seconds:
                        os.remove(filepath)
                        print(f"Cleaned up attachment file after 5 minutes: {filename}")
                        
    except Exception as e:
        print(f"Cleanup error: {e}")

def download_file_from_drive(file_id):
    """Download file content from Google Drive"""
    try:
        service = get_drive_service()
        
        # Get file metadata
        file_metadata = service.files().get(fileId=file_id).execute()
        file_name = file_metadata.get('name')
        mime_type = file_metadata.get('mimeType')
        
        logger.info(f"Google Drive filename: '{file_name}' (mime: {mime_type})")
        
        # Handle Google Workspace files (export as PDF)
        if mime_type.startswith('application/vnd.google-apps'):
            if 'document' in mime_type:
                request = service.files().export_media(fileId=file_id, mimeType='application/pdf')
                file_name = file_name.replace('.gdoc', '.pdf') if '.gdoc' in file_name else f"{file_name}.pdf"
            elif 'spreadsheet' in mime_type:
                request = service.files().export_media(fileId=file_id, mimeType='application/pdf')
                file_name = file_name.replace('.gsheet', '.pdf') if '.gsheet' in file_name else f"{file_name}.pdf"
            elif 'presentation' in mime_type:
                request = service.files().export_media(fileId=file_id, mimeType='application/pdf')
                file_name = file_name.replace('.gslides', '.pdf') if '.gslides' in file_name else f"{file_name}.pdf"
            else:
                return None, None, "Unsupported Google Workspace file type"
        else:
            # Regular file download
            request = service.files().get_media(fileId=file_id)
        
        # Download the file
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        
        file_content.seek(0)
        file_data = file_content.getvalue()
        
        # Optionally save for debugging
        save_debug_file(file_data, file_name, file_id)
        
        return file_data, file_name, None
        
    except Exception as e:
        return None, None, str(e)

def upload_to_airtable_attachment(file_content, file_name, record_id):
    """Upload file to Airtable as attachment"""
    try:
        # Convert file to base64
        file_base64 = base64.b64encode(file_content).decode('utf-8')
        
        # Create attachment object
        attachment = {
            "url": f"data:application/octet-stream;base64,{file_base64}",
            "filename": file_name
        }
        
        # Update Airtable record
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
        headers = {
            'Authorization': f'Bearer {AIRTABLE_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        data = {
            "fields": {
                "File for AI Analysis": [attachment]
            }
        }
        
        response = requests.patch(url, headers=headers, json=data)
        
        if response.status_code == 200:
            return True, "File uploaded successfully"
        else:
            return False, f"Airtable API error: {response.text}"
            
    except Exception as e:
        return False, str(e)

def rename_file_in_drive(file_id, new_name):
    """Rename file in Google Drive"""
    try:
        service = get_drive_service()
        
        body = {'name': new_name}
        updated_file = service.files().update(
            fileId=file_id,
            body=body
        ).execute()
        
        return True, f"File renamed to: {updated_file.get('name')}"
        
    except Exception as e:
        return False, str(e)


def extract_text_from_pdf(file_content):
    """Extract text from PDF using PyPDF2"""
    try:
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text = ""
        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            if page_text.strip():
                text += page_text + "\n"
        
        extracted_text = text.strip() if text.strip() else None
        
        return extracted_text
    except Exception as e:
        logger.error(f"PDF text extraction failed: {str(e)}")
        return None

def extract_text_with_easyocr(file_content, file_name):
    """Extract text using EasyOCR as fallback for difficult PDFs"""
    try:
        import easyocr
        from PIL import Image
        import fitz  # PyMuPDF
        
        logger.info(f"Using EasyOCR fallback for {file_name}")
        
        # Convert PDF to image using PyMuPDF
        if file_name.lower().endswith('.pdf'):
            pdf_document = fitz.open(stream=file_content, filetype="pdf")
            page = pdf_document[0]  # First page
            pix = page.get_pixmap()
            img_data = pix.tobytes("png")
            
            # Convert to PIL Image
            img = Image.open(io.BytesIO(img_data))
            
            pdf_document.close()
        else:
            # For regular images
            img = Image.open(io.BytesIO(file_content))
        
        # Initialize EasyOCR reader (English and Hebrew)
        reader = easyocr.Reader(['en', 'he'])
        
        # Extract text
        results = reader.readtext(img)
        
        # Combine all detected text
        extracted_text = ' '.join([result[1] for result in results if result[2] > 0.3])  # Confidence > 30%
        
        logger.info(f"EasyOCR extracted: '{extracted_text[:100]}...'")
        return extracted_text.strip() if extracted_text.strip() else None
        
    except ImportError as e:
        logger.warning(f"EasyOCR dependencies not available: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"EasyOCR processing failed: {str(e)}")
        return None


def get_airtable_record(record_id):
    """Get a specific record from Airtable"""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
        headers = {
            'Authorization': f'Bearer {AIRTABLE_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json().get('fields', {})
        else:
            logger.error(f"Airtable API error getting record {record_id}: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting Airtable record {record_id}: {str(e)}")
        return None

def update_airtable_field(record_id, field_name, field_value):
    """Update a specific field in an Airtable record"""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
        headers = {
            'Authorization': f'Bearer {AIRTABLE_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        data = {
            "fields": {
                field_name: field_value
            }
        }
        
        response = requests.patch(url, headers=headers, json=data)
        
        if response.status_code == 200:
            return True, "Field updated successfully"
        else:
            return False, f"Airtable API error: {response.text}"
            
    except Exception as e:
        return False, str(e)

def upload_file_to_airtable(file_content, file_name, mime_type):
    """Save file locally and return attachment object with public URL"""
    try:
        logger.info(f"Using original filename from Google Drive: {file_name}")
        
        # Create attachments directory if it doesn't exist
        attachments_dir = os.path.join(TEMP_FILES_DIR, 'attachments')
        os.makedirs(attachments_dir, exist_ok=True)
        
        # Generate unique filename to avoid conflicts
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        unique_filename = f"{unique_id}_{file_name}"
        
        # Save file to attachments directory
        file_path = os.path.join(attachments_dir, unique_filename)
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # Clean up old attachments immediately
        cleanup_old_temp_files()
        
        # Create public URL that Airtable can access
        public_url = f"https://api.officeours.co.il/api/attachments/{unique_filename}"
        
        logger.info(f"Saved {file_name} as {unique_filename}, public URL: {public_url}")
        
        # Return attachment object with public URL (Airtable can download this)
        return {
            'url': public_url,
            'filename': file_name,
            'size': len(file_content),
            'type': mime_type
        }
            
    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        return None

@app.route('/download-and-analyze', methods=['POST'])
def download_and_analyze():
    """Download file from Drive and upload to Airtable for AI analysis"""
    try:
        data = request.json
        file_id = data.get('file_id')
        record_id = data.get('record_id')
        drive_url = data.get('drive_url')
        
        # Extract file_id from drive_url if not provided
        if not file_id and drive_url:
            if '/d/' in drive_url:
                file_id = drive_url.split('/d/')[1].split('/')[0]
            else:
                return jsonify({"error": "Could not extract file_id from drive_url"}), 400
        
        if not file_id or not record_id:
            return jsonify({"error": "file_id and record_id are required"}), 400
        
        # Download from Google Drive
        file_content, file_name, error = download_file_from_drive(file_id)
        if error:
            return jsonify({"error": f"Download failed: {error}"}), 500
        
        # Upload to Airtable
        success, message = upload_to_airtable_attachment(file_content, file_name, record_id)
        if not success:
            return jsonify({"error": f"Upload failed: {message}"}), 500
        
        return jsonify({
            "success": True,
            "message": "File ready for AI analysis",
            "file_name": file_name,
            "file_id": file_id
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download-and-analyze-vision', methods=['POST'])
def download_and_analyze_vision():
    """Download file from Drive and upload to Airtable for AI processing"""
    try:
        # Validate Bearer token
        auth_header = request.headers.get('Authorization')
        if not validate_bearer_token(auth_header):
            logger.warning("Invalid bearer token for /download-and-analyze-vision")
            return jsonify({"error": "Unauthorized"}), 401
        
        # Validate webhook signature if configured
        if WEBHOOK_SECRET:
            signature = request.headers.get('X-Hub-Signature-256')
            if not validate_webhook_signature(request.get_data(), signature):
                logger.warning("Invalid webhook signature for /download-and-analyze-vision")
                return jsonify({"error": "Invalid signature"}), 401
        
        data = request.json
        logger.info(f"File processing request: file_id={data.get('file_id')}, record_id={data.get('record_id')}")
        
        # Validate required fields
        is_valid, error_msg = validate_request_data(data, ['record_id'])
        if not is_valid:
            logger.warning(f"Invalid request data: {error_msg}")
            return jsonify({"error": error_msg}), 400
        
        file_id = data.get('file_id')
        record_id = data.get('record_id')
        drive_url = data.get('drive_url')
        
        # Extract file_id from drive_url if not provided
        if not file_id and drive_url:
            if '/d/' in drive_url:
                file_id = drive_url.split('/d/')[1].split('/')[0]
                logger.info(f"Extracted file_id from URL: {file_id}")
            else:
                logger.error("Could not extract file_id from drive_url")
                return jsonify({"error": "Could not extract file_id from drive_url"}), 400
        
        if not file_id:
            logger.error("No file_id provided")
            return jsonify({"error": "file_id is required"}), 400
        
        # Download from Google Drive
        logger.info(f"Downloading file {file_id} from Google Drive")
        file_content, file_name, error = download_file_from_drive(file_id)
        if error:
            logger.error(f"Download failed for {file_id}: {error}")
            return jsonify({"error": f"Download failed: {error}"}), 500
        
        logger.info(f"Successfully downloaded {file_name} ({len(file_content)} bytes)")
        
        # Upload file to Airtable for AI processing
        mime_type = "application/pdf" if file_name.lower().endswith('.pdf') else "image/jpeg"
        file_attachment = upload_file_to_airtable(file_content, file_name, mime_type)
        
        if not file_attachment:
            logger.error(f"Failed to upload {file_name} to Airtable")
            return jsonify({"error": "Failed to upload file for AI processing"}), 500
        
        # Return file attachment for AI processing
        logger.info(f"Successfully uploaded {file_name} to Airtable for AI processing")
        
        return jsonify({
            "success": True,
            "message": "File uploaded to Airtable for AI processing",
            "file_name": file_name,
            "file_id": file_id,
            "file_attachment": file_attachment,  # AI can process this file directly
            "file_size": len(file_content),
            "mime_type": mime_type,
            "processing_status": "File uploaded - ready for AI analysis"
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in /download-and-analyze-vision: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/rename-file', methods=['POST'])
def rename_file():
    """Rename file in Google Drive after AI analysis"""
    try:
        # Validate Bearer token
        auth_header = request.headers.get('Authorization')
        if not validate_bearer_token(auth_header):
            logger.warning("Invalid bearer token for /rename-file")
            return jsonify({"error": "Unauthorized"}), 401
        
        # Validate webhook signature if configured
        if WEBHOOK_SECRET:
            signature = request.headers.get('X-Hub-Signature-256')
            if not validate_webhook_signature(request.get_data(), signature):
                logger.warning("Invalid webhook signature for /rename-file")
                return jsonify({"error": "Invalid signature"}), 401
        
        data = request.json
        logger.info(f"File rename request: file_id={data.get('file_id')}, new_name={data.get('new_name')}")
        
        # Validate required fields
        is_valid, error_msg = validate_request_data(data, ['file_id', 'new_name'])
        if not is_valid:
            logger.warning(f"Invalid rename request data: {error_msg}")
            return jsonify({"error": error_msg}), 400
        
        file_id = data.get('file_id')
        new_name = data.get('new_name')
        
        logger.info(f"Renaming file {file_id} to '{new_name}'")
        success, message = rename_file_in_drive(file_id, new_name)
        
        if success:
            logger.info(f"Successfully renamed file {file_id} to '{new_name}'")
            return jsonify({"success": True, "message": message})
        else:
            logger.error(f"Failed to rename file {file_id}: {message}")
            return jsonify({"error": message}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error in /rename-file: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/auto-rename-file', methods=['POST'])
def auto_rename_file():
    """Auto-rename file in Google Drive based on Airtable record with suggested name"""
    try:
        # Validate Bearer token
        auth_header = request.headers.get('Authorization')
        if not validate_bearer_token(auth_header):
            logger.warning("Invalid bearer token for /auto-rename-file")
            return jsonify({"error": "Unauthorized"}), 401
        
        # Validate webhook signature if configured
        if WEBHOOK_SECRET:
            signature = request.headers.get('X-Hub-Signature-256')
            if not validate_webhook_signature(request.get_data(), signature):
                logger.warning("Invalid webhook signature for /auto-rename-file")
                return jsonify({"error": "Invalid signature"}), 401
        
        data = request.json
        logger.info(f"Auto-rename request: record_id={data.get('record_id')}")
        
        # Validate required fields
        is_valid, error_msg = validate_request_data(data, ['record_id'])
        if not is_valid:
            logger.warning(f"Invalid auto-rename request data: {error_msg}")
            return jsonify({"error": error_msg}), 400
        
        record_id = data.get('record_id')
        
        # Get record details from Airtable
        record_data = get_airtable_record(record_id)
        if not record_data:
            logger.error(f"Failed to get record {record_id} from Airtable")
            return jsonify({"error": "Failed to get record from Airtable"}), 500
        
        # Extract file_id and suggested name from record
        file_id = record_data.get('Google Drive File ID')
        suggested_name = record_data.get('Suggested File Name')
        original_name = record_data.get('Original File Name')
        
        if not file_id:
            logger.error(f"No Google Drive File ID in record {record_id}")
            return jsonify({"error": "No Google Drive File ID in record"}), 400
        
        if not suggested_name:
            logger.warning(f"No suggested name in record {record_id}, skipping rename")
            return jsonify({"success": False, "message": "No suggested name available"}), 200
        
        # Skip if suggested name is same as original
        if suggested_name == original_name:
            logger.info(f"Suggested name '{suggested_name}' same as original, skipping rename")
            return jsonify({"success": False, "message": "Suggested name same as original"}), 200
        
        logger.info(f"Auto-renaming file {file_id} from '{original_name}' to '{suggested_name}'")
        success, message = rename_file_in_drive(file_id, suggested_name)
        
        if success:
            logger.info(f"Successfully auto-renamed file {file_id} to '{suggested_name}'")
            
            # Update Airtable record with rename status
            update_success, update_message = update_airtable_field(
                record_id, 
                "Rename Status", 
                f"✅ Renamed to: {suggested_name}"
            )
            
            if not update_success:
                logger.warning(f"Failed to update rename status: {update_message}")
            
            return jsonify({
                "success": True, 
                "message": f"Auto-renamed to: {suggested_name}",
                "original_name": original_name,
                "new_name": suggested_name
            })
        else:
            logger.error(f"Failed to auto-rename file {file_id}: {message}")
            
            # Update Airtable record with error status
            update_airtable_field(
                record_id, 
                "Rename Status", 
                f"❌ Rename failed: {message}"
            )
            
            return jsonify({"error": f"Auto-rename failed: {message}"}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error in /auto-rename-file: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Drive-Airtable Integration API',
        'version': 'PRODUCTION-2025-07-03',
        'timestamp': dt.utcnow().isoformat(),
        'features': {
            'drive_integration': True,
            'airtable_integration': True,
            'bearer_token_auth': bool(FLASK_SERVER_TOKEN),
            'webhook_signature': bool(WEBHOOK_SECRET),
            'auto_rename': True
        }
    })

@app.route('/attachments/<filename>', methods=['GET'])
def serve_attachment(filename):
    """Serve attachment files for Airtable"""
    try:
        # Security: Only allow files in the attachments directory
        attachments_dir = os.path.abspath(os.path.join(TEMP_FILES_DIR, 'attachments'))
        file_path = os.path.abspath(os.path.join(attachments_dir, filename))
        
        logger.info(f"Serving attachment: {filename}")
        logger.info(f"Attachments dir: {attachments_dir}")
        logger.info(f"File path: {file_path}")
        logger.info(f"File exists: {os.path.exists(file_path)}")
        
        # Ensure the file exists and is within the attachments directory
        if not os.path.exists(file_path) or not os.path.commonpath([attachments_dir, file_path]) == attachments_dir:
            logger.error(f"File not found or path issue: {file_path}")
            return jsonify({"error": "File not found"}), 404
        
        # Determine MIME type
        mime_type = 'application/octet-stream'
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            mime_type = f'image/{filename.split(".")[-1].lower()}'
        elif filename.lower().endswith('.pdf'):
            mime_type = 'application/pdf'
        elif filename.lower().endswith(('.txt', '.md')):
            mime_type = 'text/plain'
        
        # Send file
        return send_file(file_path, mimetype=mime_type, as_attachment=False)
        
    except Exception as e:
        logger.error(f"Error serving attachment {filename}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/temp-files', methods=['GET'])
def list_temp_files():
    """List files in temp directory and storage info"""
    try:
        files = []
        total_size = 0
        
        if os.path.exists(TEMP_FILES_DIR):
            for filename in os.listdir(TEMP_FILES_DIR):
                filepath = os.path.join(TEMP_FILES_DIR, filename)
                if os.path.isfile(filepath):
                    stat = os.stat(filepath)
                    files.append({
                        "name": filename,
                        "size": stat.st_size,
                        "created": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                    total_size += stat.st_size
        
        return jsonify({
            "temp_dir": TEMP_FILES_DIR,
            "debug_enabled": DEBUG_SAVE_FILES,
            "file_count": len(files),
            "total_size_bytes": total_size,
            "files": files
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/cleanup', methods=['POST'])
def cleanup_temp_files():
    """Manually trigger cleanup of old temp files"""
    try:
        cleanup_old_temp_files()
        return jsonify({"success": True, "message": "Cleanup completed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Load environment variables
    load_env()
    
    # Get port from environment or default
    port = int(os.environ.get('PORT', 5001))
    
    # Validate setup
    required_vars = ['AIRTABLE_API_KEY', 'AIRTABLE_BASE_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
        exit(1)
    
    if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        logger.error(f"Google credentials file not found: {GOOGLE_CREDENTIALS_PATH}")
        exit(1)
    
    # Clean up old temp files on startup
    cleanup_old_temp_files()
    
    # Log startup information
    logger.info(f"Starting PRODUCTION Drive-Airtable Vision Integration Server")
    logger.info(f"Version: 2025-07-03 (Security improvements added)")
    logger.info(f"Port: {port}")
    logger.info(f"Debug mode: {'enabled' if DEBUG_SAVE_FILES else 'disabled'}")
    logger.info(f"Bearer token auth: {'enabled' if FLASK_SERVER_TOKEN else 'disabled'}")
    logger.info(f"Webhook signature: {'enabled' if WEBHOOK_SECRET else 'disabled'}")
    logger.info(f"Temp files directory: {TEMP_FILES_DIR}")
    
    print("🚀 PRODUCTION Flask server starting...")
    print(f"📊 Health check: http://localhost:{port}/health")
    print(f"📁  File upload endpoint: POST http://localhost:{port}/download-and-analyze-vision")
    print(f"⬇️  Download endpoint: POST http://localhost:{port}/download-and-analyze")
    print(f"✏️  Rename endpoint: POST http://localhost:{port}/rename-file")
    print(f"🔄  Auto-rename endpoint: POST http://localhost:{port}/auto-rename-file")
    print(f"🔐 Security: {'Bearer token required' if FLASK_SERVER_TOKEN else 'No auth'} | {'Webhook signatures' if WEBHOOK_SECRET else 'No signatures'}")
    print(f"📁 Temp files: {TEMP_FILES_DIR} (debug: {'enabled' if DEBUG_SAVE_FILES else 'disabled'})")
    
    # Run the server in production mode
    app.run(debug=False, host='0.0.0.0', port=port)