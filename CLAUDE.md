# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This Flask server processes Google Drive files using Google Cloud Vision API and integrates with Airtable AI for intelligent file naming by:
1. Downloading files from Google Drive via API
2. Processing files with Google Cloud Vision API (OCR, text detection, image analysis)
3. Inserting Vision API results into Airtable field for AI analysis
4. Renaming the original files in Google Drive based on Airtable AI-generated suggestions

**Project Details:**
- Project ID: `drive-airtable-464711`
- Service Account: `drive-airtable@drive-airtable-464711.iam.gserviceaccount.com`
- Technology Stack: Python Flask, Google Drive API, Google Cloud Vision API, Airtable API
- Deployment: Cloudways server at `159.203.191.40:5001`

## Development Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Environment Configuration
Create a `.env` file with:
```env
GOOGLE_CREDENTIALS_PATH=./google_credentials.json
AIRTABLE_API_KEY=your_airtable_api_key
AIRTABLE_BASE_ID=your_base_id
AIRTABLE_TABLE_NAME=Files
```

### 3. Run the Application
```bash
python app.py
```

### 4. Test the Server
```bash
# Health check
curl http://localhost:5000/health

# Test endpoints require Airtable webhook setup
```

## Architecture

### File Structure
```
/drive-airtable/
├── app.py                    # Main Flask application
├── google_credentials.json   # Service account credentials (DO NOT COMMIT)
├── .env                     # Environment variables (DO NOT COMMIT)
├── .env.example             # Example environment file
├── requirements.txt         # Python dependencies
├── .gitignore              # Git ignore rules
├── CLAUDE.md               # This file
└── docs/
    └── Core/               # Project documentation
        ├── PROJECT_STATUS.md
        └── files.csv
```

### API Endpoints
1. **GET /health** - Health check endpoint (✅ DEPLOYED)
2. **POST /download-and-analyze-vision** - Download file, process with Vision API, update Airtable
   - Params: `file_id`, `record_id`, `drive_url`
   - ⏳ **TO IMPLEMENT**: Vision API integration
3. **POST /rename-file** - Rename file in Google Drive (✅ DEPLOYED)
   - Params: `file_id`, `new_name`
4. **GET /temp-files** - View temp storage info (✅ DEPLOYED)
5. **POST /cleanup** - Clean temp files (✅ DEPLOYED)

### Workflow
```
New File in Google Drive 
    ↓
Airtable Sync detects new record
    ↓
Automation 1: Webhook to /download-and-analyze-vision
    ↓
Flask downloads file and processes with Google Cloud Vision API
    ↓
Vision API results inserted into "Vision API Results" field
    ↓
Airtable AI analyzes the Vision results
    ↓
AI populates "AI Analysis Results" and "Suggested File Name"
    ↓
Automation 2: Webhook to /rename-file
    ↓
Flask renames original file in Google Drive
```

## Airtable Requirements

### Required Table Fields:
1. **Google Drive File ID** (Single line text)
2. **Google Drive URL** (URL field)
3. **text** (Long text) - Where Vision API OCR results go
4. **AI Analysis Results** (Long text) - Where Airtable AI analyzes Vision results
5. **Suggested File Name** (Single line text) - AI-generated filename
6. **Original File Name** (Single line text) - Backup

### Required Automations:
1. **Vision Processing** → Webhook to `/download-and-analyze-vision`
   - Script: `airtable_webhook_vision.js`
2. **File Renaming** → Webhook to `/rename-file` 
   - Script: `airtable_rename_automation.js`

## Common Development Tasks

### Run Tests
```bash
# No tests implemented yet
# TODO: Add pytest tests for API endpoints
```

### Lint Code
```bash
# TODO: Add flake8 or black for Python linting
```

### Deploy
```bash
# For production deployment:
# 1. Use gunicorn instead of Flask dev server
# 2. Set up proper environment variables
# 3. Consider using Docker for containerization
```

## Security Considerations

- **NEVER commit `google_credentials.json` to version control**
- **NEVER commit `.env` file**
- Service account has limited permissions (only to shared folders)
- Use environment variables for all sensitive configuration
- Consider rate limiting for production deployment
- Implement proper error handling for API failures

## Troubleshooting

### Common Issues:
1. **403 Forbidden:** Service account doesn't have access to Google Drive folder
   - Solution: Share folder with service account email
2. **File not found:** Incorrect file ID extraction from URL
   - Check URL format and file ID parsing logic
3. **Airtable upload fails:** Check API key and base ID
   - Verify field names match exactly
4. **Large files timeout:** Google Drive has size limits
   - Consider implementing chunked downloads

### Debug Steps:
1. Check `/health` endpoint responds
2. Verify Google Drive folder is shared with service account
3. Test with known file ID using curl
4. Check Airtable API permissions

## Deployment to Cloudways

### Quick Deploy
```bash
# Use the automated deployment script
./deploy.sh YOUR_SERVER_IP YOUR_SSH_USER
```

### Manual Deploy via SSH/SFTP
1. **Upload files**: Use SFTP or rsync to copy project files
2. **Setup Python**: Create virtual environment and install dependencies
3. **Configure**: Upload credentials and create .env file
4. **Run**: Use gunicorn for production deployment

### Cloudways-Specific Configuration
- Default Python path: `/usr/bin/python3`
- Application directory: `/home/master_xxxxx/drive-airtable`
- Use systemd service or supervisor for process management
- Configure Nginx proxy if needed (port 5000)

### Deployment Commands
```bash
# Initial setup on server
cd ~/drive-airtable
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn

# Run production server
gunicorn --workers 3 --bind 0.0.0.0:5000 app:app

# Or use systemd service (see deploy.sh for service file)
sudo systemctl start drive-airtable
sudo systemctl enable drive-airtable
```

## Next Steps for Enhancement

- Add comprehensive error logging
- Implement retry logic for failed operations
- Add file size limits and validation
- Support batch processing for multiple files
- Add unit and integration tests
- Implement proper production deployment setup