// Airtable Automation Script for Drive-Google Vision-Airtable Integration
// Trigger: When a record is created or updated in Google Drive synced table
// Action: Run Script
// 
// WORKFLOW:
// 1. Download file from Google Drive to Flask server
// 2. Process file with Google Cloud Vision API
// 3. Insert Vision API results into Airtable field
// 4. Airtable AI analyzes the Vision results
// 5. Second automation sends suggested filename back to Flask to rename file

// Configuration
const WEBHOOK_URL = 'http://159.203.191.40:5001/download-and-analyze-vision';
const FLASK_SERVER_TOKEN = input.secret; // Security token for Flask server

// Get the record that triggered the automation
let inputConfig = input.config();
let record = inputConfig.record;

// Extract required data from the record
let recordId = record.id;
let googleDriveUrl = record.getCellValue('Google Drive URL'); // Adjust field name as needed
let googleDriveFileId = record.getCellValue('Google Drive File ID'); // If you have this field

// Check if already processed (avoid re-processing)
let visionResults = record.getCellValue('Vision API Results'); // Field where Vision results go
if (visionResults && visionResults.length > 0) {
    console.log(`Record ${recordId} already has Vision results, skipping...`);
    return;
}

// Log the trigger
console.log(`Processing record: ${recordId}`);
console.log(`Google Drive URL: ${googleDriveUrl}`);

// Prepare webhook payload
let webhookData = {
    record_id: recordId,
    drive_url: googleDriveUrl
};

// Add file_id if available (optional - URL will work too)
if (googleDriveFileId) {
    webhookData.file_id = googleDriveFileId;
}

console.log('Sending webhook data:', JSON.stringify(webhookData, null, 2));

// Send webhook to Flask server for Vision processing
try {
    let response = await fetch(WEBHOOK_URL, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${FLASK_SERVER_TOKEN}`
        },
        body: JSON.stringify(webhookData)
    });
    
    if (response.ok) {
        let result = await response.json();
        console.log('Vision processing webhook sent successfully:', result);
        
        // Update processing status (optional)
        // await table.updateRecordAsync(recordId, {
        //     'Processing Status': 'Vision API processing complete'
        // });
        
    } else {
        let errorText = await response.text();
        console.error('Vision webhook failed:', response.status, errorText);
        
        // Update error status (optional)
        // await table.updateRecordAsync(recordId, {
        //     'Processing Status': `Vision API Error: ${response.status} - ${errorText}`
        // });
    }
} catch (error) {
    console.error('Vision webhook request failed:', error);
    
    // Update error status (optional)
    // await table.updateRecordAsync(recordId, {
    //     'Processing Status': `Connection error: ${error.message}`
    // });
}