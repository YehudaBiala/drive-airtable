import os
import io
import base64
import requests
import tempfile
import datetime
import json
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.cloud import vision
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configuration
GOOGLE_CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH', 'google_credentials.json')
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME', 'Files')
TEMP_FILES_DIR = os.getenv('TEMP_FILES_DIR', './temp_files')
DEBUG_SAVE_FILES = os.getenv('DEBUG_SAVE_FILES', 'false').lower() == 'true'

# Ensure temp directory exists
os.makedirs(TEMP_FILES_DIR, exist_ok=True)

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

def process_with_vision_api(file_content, file_name):
    """Process file content with Google Cloud Vision API"""
    try:
        client = get_vision_client()
        image = vision.Image(content=file_content)
        
        # Perform multiple types of detection
        results = {
            "file_name": file_name,
            "timestamp": datetime.datetime.now().isoformat(),
            "analysis": {}
        }
        
        # Text detection (OCR)
        response = client.text_detection(image=image)
        texts = response.text_annotations
        if texts:
            results["analysis"]["full_text"] = texts[0].description
            results["analysis"]["text_blocks"] = [
                {
                    "text": text.description,
                    "confidence": getattr(text, 'confidence', None)
                } for text in texts[1:11]  # First 10 text blocks
            ]
        
        # Label detection (what's in the image)
        response = client.label_detection(image=image)
        labels = response.label_annotations
        if labels:
            results["analysis"]["labels"] = [
                {
                    "description": label.description,
                    "score": label.score,
                    "topicality": label.topicality
                } for label in labels
            ]
        
        # Document text detection (better for documents)
        response = client.document_text_detection(image=image)
        if response.full_text_annotation:
            results["analysis"]["document_text"] = response.full_text_annotation.text
        
        # Object detection
        response = client.object_localization(image=image)
        objects = response.localized_object_annotations
        if objects:
            results["analysis"]["objects"] = [
                {
                    "name": obj.name,
                    "score": obj.score
                } for obj in objects
            ]
        
        # Safe search detection
        response = client.safe_search_detection(image=image)
        safe = response.safe_search_annotation
        results["analysis"]["safe_search"] = {
            "adult": safe.adult.name,
            "violence": safe.violence.name,
            "racy": safe.racy.name
        }
        
        # Image properties (dominant colors)
        response = client.image_properties(image=image)
        props = response.image_properties_annotation
        if props.dominant_colors:
            colors = props.dominant_colors.colors[:5]  # Top 5 colors
            results["analysis"]["dominant_colors"] = [
                {
                    "rgb": {
                        "red": int(color.color.red),
                        "green": int(color.color.green),
                        "blue": int(color.color.blue)
                    },
                    "score": color.score,
                    "pixel_fraction": color.pixel_fraction
                } for color in colors
            ]
        
        return json.dumps(results, indent=2), None
        
    except Exception as e:
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
        
        # Process with Vision API
        vision_results, vision_error = process_with_vision_api(file_content, file_name)
        if vision_error:
            return jsonify({"error": f"Vision API failed: {vision_error}"}), 500
        
        # Update Airtable with Vision API results
        success, message = update_airtable_field(record_id, "text", vision_results)
        if not success:
            return jsonify({"error": f"Airtable update failed: {message}"}), 500
        
        # Parse results for response
        results_data = json.loads(vision_results)
        
        return jsonify({
            "success": True,
            "message": "File processed with Vision API",
            "file_name": file_name,
            "file_id": file_id,
            "vision_summary": {
                "has_text": bool(results_data["analysis"].get("full_text")),
                "label_count": len(results_data["analysis"].get("labels", [])),
                "object_count": len(results_data["analysis"].get("objects", []))
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/rename-file', methods=['POST'])
def rename_file():
    """Rename file in Google Drive after AI analysis"""
    try:
        data = request.json
        file_id = data.get('file_id')
        new_name = data.get('new_name')
        
        if not file_id or not new_name:
            return jsonify({"error": "file_id and new_name are required"}), 400
        
        success, message = rename_file_in_drive(file_id, new_name)
        
        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"error": message}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"})

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
    # Validate setup
    required_vars = ['AIRTABLE_API_KEY', 'AIRTABLE_BASE_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Missing environment variables: {', '.join(missing_vars)}")
        exit(1)
    
    if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        print(f"Google credentials file not found: {GOOGLE_CREDENTIALS_PATH}")
        exit(1)
    
    # Clean up old temp files on startup
    cleanup_old_temp_files()
    
    print("🚀 Flask server starting...")
    print(f"📊 Health check: http://localhost:5001/health")
    print(f"👁️  Vision API endpoint: POST http://localhost:5001/download-and-analyze-vision")
    print(f"⬇️  Download endpoint: POST http://localhost:5001/download-and-analyze")
    print(f"✏️  Rename endpoint: POST http://localhost:5001/rename-file")
    print(f"📁 Temp files: {TEMP_FILES_DIR} (debug: {'enabled' if DEBUG_SAVE_FILES else 'disabled'})")
    print(f"🗂️  Temp files info: GET http://localhost:5001/temp-files")
    
    app.run(debug=True, host='0.0.0.0', port=5001)