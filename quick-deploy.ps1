# Quick Deploy Script - Uses your existing SSH setup
# Since you have 'ser' configured, this is a simpler approach

param(
    [Parameter(Mandatory=$true)]
    [string]$ServerIP,
    
    [Parameter(Mandatory=$true)]
    [string]$SSHUser
)

Write-Host "🚀 Quick Deploy to Cloudways" -ForegroundColor Green

# Upload all files at once
Write-Host "📤 Uploading files..." -ForegroundColor Yellow
scp app.py requirements.txt .env.example README.md "${SSHUser}@${ServerIP}:~/"
scp -r docs "${SSHUser}@${ServerIP}:~/"

Write-Host "✅ Files uploaded!" -ForegroundColor Green
Write-Host @"

Now connect to your server with 'ser' and run:

mkdir -p ~/drive-airtable
mv app.py requirements.txt .env.example README.md docs ~/drive-airtable/
cd ~/drive-airtable
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn

Then configure:
cp .env.example .env
nano .env  # Add your Airtable credentials

And test:
python app.py

"@ -ForegroundColor Cyan

Write-Host "💡 Don't forget to upload google_credentials.json separately!" -ForegroundColor Magenta