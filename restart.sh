#!/bin/bash

# Restart script for Drive-Airtable Flask app

echo "🔄 Restarting Drive-Airtable Flask app..."

# Find and kill the existing process
PID=$(ps aux | grep "python3 app.py" | grep -v grep | awk '{print $2}')
if [ ! -z "$PID" ]; then
    echo "Stopping existing process (PID: $PID)..."
    kill $PID
    sleep 2
fi

# Start the new process
cd ~/public_html/drive-airtable
nohup python3 app.py > app.log 2>&1 &
NEW_PID=$!

echo "✅ App restarted with PID: $NEW_PID"
echo "📝 Check logs with: tail -f ~/public_html/drive-airtable/app.log"