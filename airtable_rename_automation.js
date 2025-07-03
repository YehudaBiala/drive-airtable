// Airtable Automation Script for File Renaming
// Trigger: When "Suggested File Name" field is updated by Airtable AI
// Action: Run Script
//
// This automation runs AFTER Airtable AI has analyzed the Vision API results
// and populated the "Suggested File Name" field

// Configuration
const RENAME_WEBHOOK_URL = 'http://159.203.191.40:5001/rename-file';

// Get the record that triggered the automation
let inputConfig = input.config();
let record = inputConfig.record;

// Extract required data
let recordId = record.id;
let googleDriveFileId = record.getCellValue('Google Drive File ID');
let suggestedFileName = record.getCellValue('Suggested File Name'); // AI-generated name
let originalFileName = record.getCellValue('Original File Name'); // Backup

// Validation
if (!googleDriveFileId) {
    console.error('No Google Drive File ID found');
    return;
}

if (!suggestedFileName || suggestedFileName.trim() === '') {
    console.error('No suggested file name provided');
    return;
}

// Check if already renamed (avoid duplicate renames)
let renameStatus = record.getCellValue('Rename Status'); // Optional status field
if (renameStatus === 'Renamed') {
    console.log(`File ${recordId} already renamed, skipping...`);
    return;
}

console.log(`Renaming file: ${originalFileName} -> ${suggestedFileName}`);
console.log(`Google Drive File ID: ${googleDriveFileId}`);

// Prepare rename webhook payload
let renameData = {
    file_id: googleDriveFileId,
    new_name: suggestedFileName.trim()
};

console.log('Sending rename data:', JSON.stringify(renameData, null, 2));

// Send rename request to Flask server
try {
    let response = await fetch(RENAME_WEBHOOK_URL, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(renameData)
    });
    
    if (response.ok) {
        let result = await response.json();
        console.log('File renamed successfully:', result);
        
        // Update status fields (optional)
        // await table.updateRecordAsync(recordId, {
        //     'Rename Status': 'Renamed',
        //     'Final File Name': suggestedFileName,
        //     'Rename Timestamp': new Date().toISOString()
        // });
        
    } else {
        let errorText = await response.text();
        console.error('Rename failed:', response.status, errorText);
        
        // Update error status (optional)
        // await table.updateRecordAsync(recordId, {
        //     'Rename Status': `Error: ${response.status} - ${errorText}`
        // });
    }
} catch (error) {
    console.error('Rename request failed:', error);
    
    // Update error status (optional)
    // await table.updateRecordAsync(recordId, {
    //     'Rename Status': `Connection error: ${error.message}`
    // });
}