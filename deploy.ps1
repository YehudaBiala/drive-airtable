# PowerShell Deployment Script for Drive-Airtable Integration
# Usage: .\deploy.ps1 -ServerIP "YOUR_IP" -SSHUser "YOUR_USER"

param(
    [Parameter(Mandatory=$true)]
    [string]$ServerIP,
    
    [Parameter(Mandatory=$true)]
    [string]$SSHUser
)

Write-Host "🚀 Deploying Drive-Airtable Integration to Cloudways" -ForegroundColor Green
Write-Host "Server: $ServerIP" -ForegroundColor Cyan
Write-Host "User: $SSHUser" -ForegroundColor Cyan

# Check if files exist
$requiredFiles = @("app.py", "requirements.txt", ".env.example", "README.md")
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        Write-Host "❌ Missing required file: $file" -ForegroundColor Red
        exit 1
    }
}

Write-Host "`n📤 Uploading files to server..." -ForegroundColor Yellow

# Create a temporary deployment package (excluding sensitive files)
$excludeFiles = @(".git", ".env", "google_credentials.json", "__pycache__", "*.pyc", "venv", "env")

# Upload main files
Write-Host "Uploading application files..."
scp app.py requirements.txt .env.example README.md "${SSHUser}@${ServerIP}:~/"

# Upload deploy.sh for server-side execution
scp deploy.sh "${SSHUser}@${ServerIP}:~/"

# Upload docs directory
Write-Host "Uploading documentation..."
scp -r docs "${SSHUser}@${ServerIP}:~/"

# Create and upload setup script
$setupScript = @'
#!/bin/bash
echo "🔧 Setting up Drive-Airtable Integration..."

# Create application directory
mkdir -p ~/drive-airtable

# Move files to application directory
mv ~/app.py ~/requirements.txt ~/.env.example ~/README.md ~/drive-airtable/
mv ~/docs ~/drive-airtable/
mv ~/deploy.sh ~/drive-airtable/

cd ~/drive-airtable

# Check Python version
python3 --version || { echo "❌ Python 3 not found!"; exit 1; }

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate and install dependencies
echo "📚 Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# Create systemd service file
echo "⚙️ Creating systemd service..."
cat > drive-airtable.service << 'EOF'
[Unit]
Description=Drive-Airtable Integration Flask App
After=network.target

[Service]
User=$USER
Group=$USER
WorkingDirectory=$HOME/drive-airtable
Environment="PATH=$HOME/drive-airtable/venv/bin"
ExecStart=$HOME/drive-airtable/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Server setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Upload google_credentials.json to ~/drive-airtable/"
echo "2. Configure .env file with your Airtable credentials"
echo "3. Install systemd service: sudo cp drive-airtable.service /etc/systemd/system/"
echo "4. Start service: sudo systemctl start drive-airtable"
echo "5. Enable on boot: sudo systemctl enable drive-airtable"
'@

# Save setup script temporarily
$setupScript | Out-File -FilePath "setup_server.sh" -Encoding UTF8

# Upload and execute setup script
Write-Host "`n🔧 Running server setup..." -ForegroundColor Yellow
scp setup_server.sh "${SSHUser}@${ServerIP}:~/"
ssh "${SSHUser}@${ServerIP}" "chmod +x ~/setup_server.sh && ~/setup_server.sh"

# Clean up local temp file
Remove-Item "setup_server.sh"

Write-Host "`n✅ Deployment complete!" -ForegroundColor Green
Write-Host "`n⚠️  IMPORTANT - Manual steps required:" -ForegroundColor Yellow

Write-Host @"

1. Upload your credentials:
   scp google_credentials.json ${SSHUser}@${ServerIP}:~/drive-airtable/

2. Connect to server and configure:
   ssh ${SSHUser}@${ServerIP}
   cd ~/drive-airtable
   cp .env.example .env
   nano .env  # Add your Airtable API key and base ID

3. Install and start the service:
   sudo cp drive-airtable.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl start drive-airtable
   sudo systemctl enable drive-airtable

4. Check status:
   sudo systemctl status drive-airtable
   curl http://localhost:5000/health

5. View logs:
   sudo journalctl -u drive-airtable -f

"@ -ForegroundColor Cyan

Write-Host "💡 Tip: If you have 'ser' configured, just type 'ser' to connect!" -ForegroundColor Magenta