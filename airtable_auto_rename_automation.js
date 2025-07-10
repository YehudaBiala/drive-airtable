// Airtable Automation Script for Auto-Rename File
// This script triggers when "Suggested File Name" field is populated
// and automatically renames the file in Google Drive

// Configuration
const FLASK_SERVER_URL = 'https://api.officeours.co.il/api'; // Production server
const FLASK_SERVER_TOKEN = input.secret('receipt_server_token');
let config = input.config();
let recordId = config.recordId;
// Main automation function
async function autoRenameFile() {
    try {
        // Get current record
        const recordId = config.recordId;
        const record = await base.getTable(config.table).selectRecordAsync(recordId);
        
        if (!record) {
            console.log('❌ Record not found');
            return;
        }
        
        // Check if we have required fields
        const googleDriveFileId = config.fileId;
        const suggestedFileName = config.newName;
        
        // Skip if no file ID
        if (!googleDriveFileId) {
            console.log('⚠️ No Google Drive File ID found');
            return;
        }
        
        // Skip if no suggested name
        if (!suggestedFileName) {
            console.log('⚠️ No suggested file name found');
            return;
        }
        
        console.log(`🔄 Starting auto-rename for file: ${googleDriveFileId}`);
        console.log(`📝 New name: "${suggestedFileName}"`);
        
        // Prepare request data with file_id and new_name directly
        const requestData = {
            file_id: googleDriveFileId,
            new_name: suggestedFileName
        };
        
        // Debug: Log full URL
        const fullUrl = `${FLASK_SERVER_URL}/auto-rename-file`;
        console.log(`🔗 Full URL: ${fullUrl}`);
        console.log(`📦 Request data:`, JSON.stringify(requestData));
        console.log(`🔑 Token present: ${FLASK_SERVER_TOKEN ? 'Yes' : 'No'}`);
        
        // Make request to Flask server
        const response = await fetch(fullUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${FLASK_SERVER_TOKEN}`
            },
            body: JSON.stringify(requestData)
        });
        
        console.log(`📡 Response status: ${response.status}`);
        console.log(`📡 Response OK: ${response.ok}`);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error(`❌ Auto-rename failed: ${response.status} - ${errorText}`);
            console.error(`🌐 URL was: ${fullUrl}`);
            console.error(`📮 Method was: POST`);
            console.error(`📋 Headers were:`, {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${FLASK_SERVER_TOKEN ? '[HIDDEN]' : 'MISSING'}`
            });
            
            // Parse error for better user messaging
            let errorMessage = `HTTP ${response.status}`;
            try {
                const errorData = JSON.parse(errorText);
                if (errorData.error && errorData.error.includes('insufficient permissions')) {
                    errorMessage = '❌ Permission denied - service account needs access to this file';
                } else if (errorData.error) {
                    errorMessage = `❌ ${errorData.error}`;
                }
            } catch (e) {
                // Use default error message if parsing fails
                console.error('⚠️ Could not parse error response as JSON');
            }
            
            // Update record with descriptive error status
            await base.getTable(config.table).updateRecordAsync(recordId, {
                'Rename Status': errorMessage
            });
            
            return;
        }
        
        const result = await response.json();
        
        if (result.success) {
            console.log(`✅ Successfully auto-renamed file to: ${result.new_name}`);
            
            // Update record with success status
            await base.getTable(config.table).updateRecordAsync(recordId, {
                'Rename Status': `✅ Auto-renamed to: ${result.new_name}`,
                'Rename Date': new Date().toISOString()
            });
            
        } else {
            console.log(`⚠️ Auto-rename failed: ${result.message}`);
            
            // Update record with error status
            await base.getTable('Files').updateRecordAsync(recordId, {
                'Rename Status': `❌ Failed: ${result.message}`
            });
        }
        
    } catch (error) {
        console.error('❌ Auto-rename automation error:', error);
        console.error('🐛 Error type:', error.name);
        console.error('🐛 Error stack:', error.stack);
        console.error('🐛 Config values:', {
            recordId: config.recordId,
            fileId: config.fileId,
            newName: config.newName,
            table: config.table
        });
        
        // Update record with error status
        try {
            const recordId = config.recordId;
            const errorMessage = error.message || 'Unknown automation error';
            await base.getTable(config.table || 'Files').updateRecordAsync(recordId, {
                'Rename Status': `❌ Automation error: ${errorMessage}`
            });
        } catch (updateError) {
            console.error('❌ Failed to update error status:', updateError);
            // Log more details about the update error
            console.error('Update error details:', {
                recordId: config.recordId,
                originalError: error.message,
                updateError: updateError.message,
                tableName: config.table || 'Files'
            });
        }
    }
}

// Run the automation
autoRenameFile();