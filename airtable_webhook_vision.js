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
const FLASK_SERVER_TOKEN = input.secret("receipt_server_token"); // Security token for Flask server

// Get the record that triggered the automation
let inputConfig = input.config();
let recordId = inputConfig.record_id;
let googleDriveFileId = inputConfig.file_id;
let googleDriveUrl = inputConfig.drive_url;
let logId = inputConfig.log_id;
let textId = inputConfig.text_id;
let fileId = inputConfig.file_id;
const WEBHOOK_URL = inputConfig.webhook_url;
console.log(googleDriveFileId)

// Check if already processed (avoid re-processing)
let visionResults = inputConfig.text; // Field where Vision results go
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
    drive_url: googleDriveUrl,
    log_id: logId,
    text_id: textId,
    file_id: fileId
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
        
        if (result.success && result.extracted_text) {
            console.log('Extracted text length:', result.extracted_text_length);
            console.log('Text preview:', result.text_preview);
            
            // Use output.set() to return the extracted text and file to the automation
            output.set('extracted_text', result.extracted_text);
            output.set('file_name', result.file_name);
            output.set('file_id', result.file_id);
            output.set('text_length', result.extracted_text_length);
            output.set('file_content_base64', result.file_content_base64);
            output.set('file_size', result.file_size);
            output.set('processing_status', 'Vision API processing complete');
            
            console.log('Text extraction completed successfully - use outputs in next automation step');
        } else {
            console.error('Unexpected response format:', result);
            output.set('error', 'Invalid response from Vision API');
            output.set('processing_status', 'Error: Invalid response format');
        }
        
    } else {
        let errorText = await response.text();
        console.error('Vision webhook failed:', response.status, errorText);
        
        // Set error outputs
        output.set('error', `Vision API Error: ${response.status} - ${errorText}`);
        output.set('processing_status', `Vision API Error: ${response.status}`);
    }
} catch (error) {
    console.error('Vision webhook request failed:', error);
    console.error('Error details:', {
        message: error.message,
        name: error.name,
        stack: error.stack,
        url: WEBHOOK_URL
    });
    
    // Common connection issues
    if (error.name === 'FetchError' || error.name === 'a') {
        console.error('Connection error - Flask server may be offline or port may be blocked');
        console.error('Please check:');
        console.error('1. Flask server is running on', WEBHOOK_URL);
        console.error('2. Port 5001 is open in firewall');
        console.error('3. Server is accessible from Airtable');
    }
    
    // Set error outputs
    output.set('error', `Connection error: ${error.message}`);
    output.set('processing_status', 'Connection error');
}