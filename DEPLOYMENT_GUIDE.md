# Combined API Proxy Deployment Guide

## Overview
This combined PHP proxy routes requests to both Flask servers:
- **Drive-Airtable Flask Server** (localhost:5001)
- **Tranzila-Airtable Flask Server** (localhost:2000)

## Current Server Status
- ✅ **Tranzila Server**: Running on port 2000 (PRODUCTION_SERVER.py)
- ⏳ **Drive-Airtable Server**: Needs to be started on port 5001

## Deployment Steps

### 1. Upload Files to Server
```bash
# Upload the combined proxy
scp php_proxy.php myserver:/home/984109.cloudwaysapps.com/axwqyakume/public_html/api/index.php
scp .htaccess myserver:/home/984109.cloudwaysapps.com/axwqyakume/public_html/api/.htaccess
```

### 2. Create API Directory Structure
```bash
ssh myserver "mkdir -p /home/984109.cloudwaysapps.com/axwqyakume/public_html/api"
```

### 3. Start Drive-Airtable Flask Server
```bash
ssh myserver "cd /home/984109.cloudwaysapps.com/axwqyakume/public_html/drive-airtable && nohup python3 app.py > app.log 2>&1 &"
```

### 4. Test API Endpoints

#### Drive-Airtable Endpoints:
- `https://api.officeours.co.il/download-and-analyze-vision` (POST)
- `https://api.officeours.co.il/rename-file` (POST)
- `https://api.officeours.co.il/temp-files` (GET)
- `https://api.officeours.co.il/cleanup` (POST)

#### Tranzila Endpoints:
- `https://api.officeours.co.il/health` (GET)
- `https://api.officeours.co.il/test-auth` (GET)
- `https://api.officeours.co.il/create-payment-request` (POST)
- `https://api.officeours.co.il/process-direct-transaction` (POST)
- `https://api.officeours.co.il/webhook/payment-status` (POST)
- `https://api.officeours.co.il/webhook/transaction-update` (POST)

## Configuration Details

### Server Ports:
- **Port 2000**: Tranzila-Airtable Flask Server ✅ Running
- **Port 5001**: Drive-Airtable Flask Server ⏳ Needs starting

### Environment Variables:
Make sure both servers have their respective .env files configured:

**Drive-Airtable (.env):**
```
GOOGLE_CREDENTIALS_PATH=./google_credentials.json
AIRTABLE_API_KEY=your_airtable_api_key
AIRTABLE_BASE_ID=your_base_id
AIRTABLE_TABLE_NAME=Files
FLASK_SERVER_TOKEN=your_secure_bearer_token
```

**Tranzila (.env):**
```
TRANZILA_PUBLIC_KEY=your_tranzila_public_key
TRANZILA_PRIVATE_KEY=your_tranzila_private_key
PORT=2000
```

## Troubleshooting

### Check Server Status:
```bash
ssh myserver "ps aux | grep python"
ssh myserver "netstat -tlnp | grep -E '(2000|5001)'"
```

### Test Individual Servers:
```bash
# Test Tranzila server
ssh myserver "curl -s http://localhost:2000/health"

# Test Drive-Airtable server
ssh myserver "curl -s http://localhost:5001/health"
```

### Test Combined API:
```bash
curl -s https://api.officeours.co.il/health
```

## File Structure on Server:
```
/home/984109.cloudwaysapps.com/axwqyakume/public_html/
├── api/
│   ├── index.php          # Combined PHP proxy
│   └── .htaccess          # URL rewriting rules
├── drive-airtable/
│   ├── app.py            # Drive-Airtable Flask server
│   ├── .env              # Environment variables
│   └── ...
└── tranzila-api/
    ├── server.py         # Tranzila Flask server (or PRODUCTION_SERVER.py)
    ├── .env              # Environment variables
    └── ...
```