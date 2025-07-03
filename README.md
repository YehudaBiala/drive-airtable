# Drive-Google Vision-Airtable Integration

Flask server that processes Google Drive files using Google Cloud Vision API and integrates with Airtable AI for intelligent file naming.

## Features

- Downloads files from Google Drive via API
- Processes files with Google Cloud Vision API (OCR, text detection, image analysis)
- Inserts Vision API results into Airtable for AI analysis
- Renames files in Google Drive based on Airtable AI-generated names

## Workflow

1. **File Detection**: Airtable detects new file in synced Google Drive
2. **Download & Vision**: Flask downloads file and processes with Google Cloud Vision
3. **Vision Results**: Vision API results inserted into Airtable field
4. **AI Analysis**: Airtable AI analyzes Vision results and suggests filename
5. **File Rename**: Second automation sends suggested name back to Flask to rename file

## Quick Start

### 1. Setup Google Cloud

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Enable Google Drive API
3. Create a service account and download JSON key
4. Share your Google Drive folder with the service account email

### 2. Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your Airtable credentials

# Run the server
python app.py
```

### 3. Deploy to Cloudways

#### Option A: Using deploy.sh script

```bash
# Make script executable
chmod +x deploy.sh

# Run deployment
./deploy.sh YOUR_SERVER_IP YOUR_SSH_USER

# Example:
./deploy.sh 123.45.67.89 master_abcdef
```

#### Option B: Manual deployment via SSH/SFTP

1. **Connect to your server:**
```bash
ssh your_user@your_server_ip
```

2. **Create application directory:**
```bash
mkdir -p ~/drive-airtable
```

3. **Upload files via SFTP:**
```bash
# From your local machine
sftp your_user@your_server_ip
cd drive-airtable
put app.py
put requirements.txt
put .env.example
put -r docs
exit
```

4. **Setup Python environment on server:**
```bash
cd ~/drive-airtable
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

5. **Upload credentials and configure:**
```bash
# From local machine
scp google_credentials.json your_user@your_server_ip:~/drive-airtable/

# On server
cp .env.example .env
nano .env  # Add your Airtable credentials
```

6. **Run with Gunicorn:**
```bash
gunicorn --workers 3 --bind 0.0.0.0:5000 app:app
```

### 4. Configure Airtable

#### Required Table Fields:
- **Google Drive File ID** (Single line text)
- **Google Drive URL** (URL field)
- **Vision API Results** (Long text) - Where Vision analysis goes
- **AI Analysis Results** (Long text) - Where Airtable AI puts analysis
- **Suggested File Name** (Single line text) - AI-generated filename
- **Original File Name** (Single line text) - Backup

#### Required Automations:

**Automation 1: Vision Processing**
- Trigger: When record created in Google Drive table
- Action: Run script (`airtable_webhook_vision.js`)
- Webhook: `http://159.203.191.40:5001/download-and-analyze-vision`

**Automation 2: File Renaming**
- Trigger: When "Suggested File Name" field updated
- Action: Run script (`airtable_rename_automation.js`)
- Webhook: `http://159.203.191.40:5001/rename-file`

## API Endpoints

- `GET /health` - Health check
- `POST /download-and-analyze-vision` - Download file, process with Vision API, update Airtable
- `POST /rename-file` - Rename file in Google Drive
- `GET /temp-files` - View temp storage info
- `POST /cleanup` - Clean temp files

## Troubleshooting

### Check service status:
```bash
curl http://localhost:5000/health
```

### View logs:
```bash
# If using systemd
sudo journalctl -u drive-airtable -f

# If running directly
# Check terminal output
```

### Common issues:
- **403 Forbidden**: Share Google Drive folder with service account email
- **Airtable errors**: Verify API key and field names match exactly
- **Connection refused**: Check firewall rules and port 5000

## Security Notes

- Never commit `google_credentials.json` or `.env` to Git
- Use HTTPS in production
- Consider implementing rate limiting
- Keep credentials secure on the server