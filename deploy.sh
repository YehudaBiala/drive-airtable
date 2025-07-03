#!/bin/bash

# Cloudways Deployment Script for Drive-Airtable Integration
# Usage: ./deploy.sh <cloudways-server-ip> <ssh-user>

SERVER_IP=$1
SSH_USER=$2
APP_DIR="/home/$SSH_USER/drive-airtable"

if [ -z "$SERVER_IP" ] || [ -z "$SSH_USER" ]; then
    echo "Usage: ./deploy.sh <cloudways-server-ip> <ssh-user>"
    echo "Example: ./deploy.sh 123.45.67.89 master_abcdef"
    exit 1
fi

echo "🚀 Deploying to Cloudways server: $SERVER_IP"

# Create deployment directory on server
echo "📁 Creating application directory..."
ssh $SSH_USER@$SERVER_IP "mkdir -p $APP_DIR"

# Copy files to server (excluding sensitive files)
echo "📤 Uploading application files..."
rsync -avz --exclude='.git' \
    --exclude='google_credentials.json' \
    --exclude='.env' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='venv' \
    --exclude='env' \
    ./ $SSH_USER@$SERVER_IP:$APP_DIR/

# Setup on server
echo "🔧 Setting up application on server..."
ssh $SSH_USER@$SERVER_IP << 'ENDSSH'
cd ~/drive-airtable

# Install Python 3.9+ if not available
python3 --version || { echo "Python 3 not found!"; exit 1; }

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment and install dependencies
echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# Create systemd service file
echo "Creating systemd service..."
sudo tee /etc/systemd/system/drive-airtable.service > /dev/null << 'EOF'
[Unit]
Description=Drive-Airtable Integration Flask App
After=network.target

[Service]
User=$USER
Group=$USER
WorkingDirectory=/home/$USER/drive-airtable
Environment="PATH=/home/$USER/drive-airtable/venv/bin"
ExecStart=/home/$USER/drive-airtable/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

echo "✅ Deployment files uploaded!"
ENDSSH

echo ""
echo "⚠️  IMPORTANT: Manual steps required:"
echo ""
echo "1. Upload your credentials:"
echo "   scp google_credentials.json $SSH_USER@$SERVER_IP:$APP_DIR/"
echo ""
echo "2. Create .env file on server:"
echo "   ssh $SSH_USER@$SERVER_IP"
echo "   cd $APP_DIR"
echo "   cp .env.example .env"
echo "   nano .env  # Add your Airtable credentials"
echo ""
echo "3. Start the service:"
echo "   sudo systemctl enable drive-airtable"
echo "   sudo systemctl start drive-airtable"
echo ""
echo "4. Configure Nginx (if using Cloudways application):"
echo "   - Proxy pass to localhost:5000"
echo "   - Or use the Cloudways control panel to set up the application"
echo ""
echo "5. Check service status:"
echo "   sudo systemctl status drive-airtable"
echo "   curl http://localhost:5000/health"
echo ""
echo "📝 For logs: sudo journalctl -u drive-airtable -f"