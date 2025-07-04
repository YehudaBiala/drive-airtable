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

from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.cloud import vision
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

def get_vision_client():
    """Initialize Google Cloud Vision API client"""
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GOOGLE_CREDENTIALS_PATH
    return vision.ImageAnnotatorClient()

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
        for filename in os.listdir(TEMP_FILES_DIR):
            filepath = os.path.join(TEMP_FILES_DIR, filename)
            if os.path.isfile(filepath):
                file_time = datetime.datetime.fromtimestamp(os.path.getctime(filepath))
                if (current_time - file_time).total_seconds() > (max_age_hours * 3600):
                    os.remove(filepath)
                    print(f"Cleaned up old temp file: {filename}")
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

def fix_hebrew_text_direction(text):
    """Fix Hebrew text that may be reversed/mirrored"""
    import re
    
    # Check if text contains Hebrew characters
    hebrew_pattern = re.compile(r'[\u0590-\u05FF]')
    if not hebrew_pattern.search(text):
        return text  # Not Hebrew, return as-is
    
    logger.info("Detected Hebrew text, attempting to fix direction")
    
    # Split into lines and process each line
    lines = text.split('\n')
    fixed_lines = []
    
    for line in lines:
        if hebrew_pattern.search(line):
            # For lines with Hebrew, try reversing if it looks mirrored
            # Look for patterns that indicate reversed text
            if any(pattern in line for pattern in ['ךמס', 'ךאראת', 'רובסל', 'יק יק']):
                # These are common Hebrew words that appear reversed in the OCR
                # Reverse the entire line
                fixed_line = line[::-1]
                logger.info(f"Reversed Hebrew line: '{line[:50]}...' -> '{fixed_line[:50]}...'")
                fixed_lines.append(fixed_line)
            else:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

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
        
        # Fix Hebrew text direction if needed
        if extracted_text:
            extracted_text = fix_hebrew_text_direction(extracted_text)
        
        return extracted_text
    except Exception as e:
        logger.error(f"PDF text extraction failed: {str(e)}")
        return None

def process_with_vision_api(file_content, file_name):
    """Process file content with Google Cloud Vision API and return extracted text"""
    try:
        extracted_text = ""
        
        # Check if it's a PDF file
        if file_name.lower().endswith('.pdf'):
            logger.info(f"Processing PDF file: {file_name}")
            
            # First try to extract text directly from PDF (for text-based PDFs)
            pdf_text = extract_text_from_pdf(file_content)
            if pdf_text:
                logger.info(f"Successfully extracted {len(pdf_text)} characters from PDF text layer")
                return pdf_text, None
            else:
                logger.info("PDF has no extractable text layer, treating as image-based PDF")
                # Fall through to Vision API processing for image-based PDFs
        
        # Process with Vision API (for images or image-based PDFs)
        client = get_vision_client()
        image = vision.Image(content=file_content)
        
        # Try document text detection first (better for documents)
        logger.info(f"Trying document text detection for {file_name}")
        response = client.document_text_detection(image=image)
        if response.full_text_annotation and response.full_text_annotation.text.strip():
            extracted_text = response.full_text_annotation.text.strip()
            logger.info(f"Document text detection found {len(extracted_text)} characters")
        else:
            logger.info("Document text detection found no text, trying regular OCR")
            # Fall back to regular text detection (OCR)
            response = client.text_detection(image=image)
            texts = response.text_annotations
            if texts and texts[0].description.strip():
                extracted_text = texts[0].description.strip()
                logger.info(f"OCR found {len(extracted_text)} characters")
            else:
                logger.info("OCR found no text, trying object detection")
        
        # If no text found, try object detection to describe what's in the image
        if not extracted_text:
            response = client.object_localization(image=image)
            objects = response.localized_object_annotations
            if objects:
                object_names = [obj.name for obj in objects[:5]]  # Top 5 objects
                extracted_text = f"Objects detected: {', '.join(object_names)}"
                logger.info(f"Object detection found: {object_names}")
            else:
                logger.info("Object detection found nothing, trying label detection")
                # Last resort: use label detection
                response = client.label_detection(image=image)
                labels = response.label_annotations
                if labels:
                    label_names = [label.description for label in labels[:5]]  # Top 5 labels
                    extracted_text = f"Image contains: {', '.join(label_names)}"
                    logger.info(f"Label detection found: {label_names}")
                else:
                    extracted_text = f"No text or recognizable content found in {file_name}"
                    logger.warning(f"All Vision API methods failed to extract content from {file_name}")
        
        logger.info(f"Final extracted text preview: '{extracted_text[:100]}...'")
        return extracted_text, None
        
    except Exception as e:
        logger.error(f"Vision API processing error for {file_name}: {str(e)}")
        return None, f"Vision API error: {str(e)}"

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
    """Download file from Drive, process with Vision API, and update Airtable"""
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
        logger.info(f"Vision processing request: file_id={data.get('file_id')}, record_id={data.get('record_id')}")
        
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
        
        # Process with Vision API
        logger.info(f"Processing {file_name} with Vision API")
        extracted_text, vision_error = process_with_vision_api(file_content, file_name)
        if vision_error:
            logger.error(f"Vision API failed for {file_name}: {vision_error}")
            return jsonify({"error": f"Vision API failed: {vision_error}"}), 500
        
        logger.info(f"Vision API extracted {len(extracted_text)} characters from {file_name}")
        
        # Update Airtable with extracted text
        logger.info(f"Updating Airtable record {record_id} with extracted text")
        success, message = update_airtable_field(record_id, "Text", extracted_text)
        if not success:
            logger.error(f"Airtable update failed for {record_id}: {message}")
            return jsonify({"error": f"Airtable update failed: {message}"}), 500
        
        logger.info(f"Successfully processed {file_name} and updated Airtable record {record_id}")
        
        return jsonify({
            "success": True,
            "message": "File processed with Vision API",
            "file_name": file_name,
            "file_id": file_id,
            "extracted_text_length": len(extracted_text),
            "text_preview": extracted_text[:100] + "..." if len(extracted_text) > 100 else extracted_text
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

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Drive-Airtable Vision Integration API',
        'version': 'PRODUCTION-2025-07-03',
        'timestamp': dt.utcnow().isoformat(),
        'features': {
            'vision_api': True,
            'drive_integration': True,
            'airtable_integration': True,
            'bearer_token_auth': bool(FLASK_SERVER_TOKEN),
            'webhook_signature': bool(WEBHOOK_SECRET)
        }
    })

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
    print(f"👁️  Vision API endpoint: POST http://localhost:{port}/download-and-analyze-vision")
    print(f"⬇️  Download endpoint: POST http://localhost:{port}/download-and-analyze")
    print(f"✏️  Rename endpoint: POST http://localhost:{port}/rename-file")
    print(f"🔐 Security: {'Bearer token required' if FLASK_SERVER_TOKEN else 'No auth'} | {'Webhook signatures' if WEBHOOK_SECRET else 'No signatures'}")
    print(f"📁 Temp files: {TEMP_FILES_DIR} (debug: {'enabled' if DEBUG_SAVE_FILES else 'disabled'})")
    
    # Run the server in production mode
    app.run(debug=False, host='0.0.0.0', port=port)