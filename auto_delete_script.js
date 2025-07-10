// Airtable Automation Script for Auto-Delete File
// This script triggers when a delete confirmation field is populated
// and automatically deletes the file from Google Drive

// Configuration
const FLASK_SERVER_URL = 'https://api.officeours.co.il/api'; // Production server
const FLASK_SERVER_TOKEN = input.secret('receipt_server_token');
let config = input.config();
let recordId = config.recordId;

// Main automation function
async function autoDeleteFile() {
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
        const deleteConfirmation = config.deleteConfirm; // New field for delete confirmation
        
        // Skip if no file ID
        if (!googleDriveFileId) {
            console.log('⚠️ No Google Drive File ID found');
            return;
        }
        
        // Skip if no delete confirmation
        if (!deleteConfirmation) {
            console.log('⚠️ No delete confirmation found');
            return;
        }
        
        console.log(`🗑️ Starting auto-delete for file: ${googleDriveFileId}`);
        console.log(`✅ Delete confirmation: "${deleteConfirmation}"`);
        
        // Prepare request data with file_id for deletion
        const requestData = {
            file_id: googleDriveFileId
        };
        
        // Debug: Log full URL
        const fullUrl = `${FLASK_SERVER_URL}/auto-delete-file`;
        console.log(`🔗 Full URL: ${fullUrl}`);
        console.log(`📦 Request data:`, JSON.stringify(requestData));
        console.log(`🔑 Token present: ${FLASK_SERVER_TOKEN ? 'Yes' : 'No'}`);
        
        // Make request to Flask server
        const response = await fetch(fullUrl, {
            method: 'DELETE',
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
            console.error(`❌ Auto-delete failed: ${response.status} - ${errorText}`);
            console.error(`🌐 URL was: ${fullUrl}`);
            console.error(`📮 Method was: DELETE`);
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
                } else if (errorData.error && errorData.error.includes('not found')) {
                    errorMessage = '❌ File not found - may have already been deleted';
                } else if (errorData.error) {
                    errorMessage = `❌ ${errorData.error}`;
                }
            } catch (e) {
                // Use default error message if parsing fails
                console.error('⚠️ Could not parse error response as JSON');
            }
            
            // Update record with descriptive error status
            await base.getTable(config.table).updateRecordAsync(recordId, {
                'Delete Status': errorMessage
            });
            
            return;
        }
        
        const result = await response.json();
        
        if (result.success) {
            console.log(`✅ Successfully auto-deleted file: ${googleDriveFileId}`);
            
            // Update record with success status and clear file reference
            await base.getTable(config.table).updateRecordAsync(recordId, {
                'Delete Status': `✅ File successfully deleted`,
                'Delete Date': new Date().toISOString(),
                'Google Drive File ID': null // Clear the file ID since it's deleted
            });
            
        } else {
            console.log(`⚠️ Auto-delete failed: ${result.message}`);
            
            // Update record with error status
            await base.getTable(config.table).updateRecordAsync(recordId, {
                'Delete Status': `❌ Failed: ${result.message}`
            });
        }
        
    } catch (error) {
        console.error('❌ Auto-delete automation error:', error);
        console.error('🐛 Error type:', error.name);
        console.error('🐛 Error stack:', error.stack);
        console.error('🐛 Config values:', {
            recordId: config.recordId,
            fileId: config.fileId,
            deleteConfirm: config.deleteConfirm,
            table: config.table
        });
        
        // Update record with error status
        try {
            const recordId = config.recordId;
            const errorMessage = error.message || 'Unknown automation error';
            await base.getTable(config.table || 'Files').updateRecordAsync(recordId, {
                'Delete Status': `❌ Automation error: ${errorMessage}`
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
autoDeleteFile();