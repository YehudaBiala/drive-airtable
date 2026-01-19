// Airtable Automation Script for Google Drive File Deletion
// This script PERMANENTLY DELETES files from Google Drive via API
// Uses Flask server endpoint to handle Google Drive API operations

// Configuration
const FLASK_SERVER_URL = 'https://api.officeours.co.il/api'; // Production server
const FLASK_SERVER_TOKEN = input.secret('receipt_server_token');
let config = input.config();
let tableR = config.table;
let field = config.field;
let table = base.getTable(tableR); 
let fieldName = field; 

// Main deletion function
async function deleteFilesFromDrive() {
    try {
        console.log(`🔍 Searching for records with ${fieldName} field populated...`);
        
        let query = await table.selectRecordsAsync({
            sorts: [{field: "Created", direction: "asc"}],
            fields: ["Created", fieldName, "File ID"]
        });
        
        let filesToDelete = [];
        
        // Loop through each record to find files marked for deletion
        for (let record of query.records) {
            let deleteMarker = record.getCellValue(fieldName);
            let fileId = record.getCellValue("File ID");
            
            if (deleteMarker !== null && fileId !== null) {
                filesToDelete.push({
                    record: record,
                    fileId: fileId,
                    recordId: record.id
                });
            }
        }
        
        // Check if any files were found for deletion
        if (filesToDelete.length === 0) {
            console.log("ℹ️ No files found to delete.");
            output.set("Result", "No files marked for deletion found.");
            return;
        }
        
        console.log(`🗑️ Found ${filesToDelete.length} files to PERMANENTLY DELETE from Google Drive`);
        
        // TEST MODE: Only process first 3 files for quick testing
        const TEST_MODE = true;
        const MAX_TEST_FILES = 3;
        
        if (TEST_MODE) {
            filesToDelete = filesToDelete.slice(0, MAX_TEST_FILES);
            console.log(`🧪 TEST MODE: Processing only ${filesToDelete.length} files`);
        }
        
        let successCount = 0;
        let failCount = 0;
        let noAccessCount = 0;
        let notFoundCount = 0;
        let results = [];
        
        // Process each file deletion
        for (let fileToDelete of filesToDelete) {
            try {
                console.log(`🔄 Processing deletion for File ID: ${fileToDelete.fileId}`);
                
                // Prepare request data
                const requestData = {
                    file_id: fileToDelete.fileId
                };
                
                // Make request to Flask server
                const response = await fetch(`${FLASK_SERVER_URL}/auto-delete-file`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${FLASK_SERVER_TOKEN}`
                    },
                    body: JSON.stringify(requestData)
                });
                
                console.log(`📡 Response status for ${fileToDelete.fileId}: ${response.status}`);
                
                if (!response.ok) {
                    const errorText = await response.text();
                    console.error(`❌ Delete failed for ${fileToDelete.fileId}: ${response.status} - ${errorText}`);
                    
                    // Parse error for better user messaging
                    let errorMessage = `HTTP ${response.status}`;
                    let isPermissionError = false;
                    
                    try {
                        const errorData = JSON.parse(errorText);
                        if (errorData.error) {
                            const errorStr = errorData.error.toString();
                            
                            // Check for specific error types
                            if (errorStr.includes('insufficient permissions') ||
                                errorStr.includes('insufficientFilePermissions') ||
                                errorStr.includes('Cannot delete')) {
                                errorMessage = `❌ No permission to delete - need Manager/Owner access`;
                                isPermissionError = true;
                            } else if (errorStr.includes('not found') || errorStr.includes('notFound')) {
                                errorMessage = `ℹ️ File not found - may have already been deleted`;
                            } else {
                                errorMessage = errorData.error;
                            }
                        }
                    } catch (e) {
                        // Use default error message if parsing fails
                    }
                    
                    // Note: Cannot update synced table records, only log the error
                    
                    failCount++;
                    if (isPermissionError) {
                        noAccessCount++;
                        results.push(`🚫 ${fileToDelete.fileId}: ${errorMessage}`);
                    } else if (errorMessage.includes('not found')) {
                        notFoundCount++;
                        results.push(`ℹ️ ${fileToDelete.fileId}: Already deleted`);
                    } else {
                        results.push(`❌ ${fileToDelete.fileId}: ${errorMessage}`);
                    }
                    continue;
                }
                
                const result = await response.json();

                if (result.success) {
                    console.log(`✅ Successfully deleted file: ${fileToDelete.fileId}`);
                    successCount++;
                    results.push(`✅ ${fileToDelete.fileId}: ${result.message || 'Deleted'}`);
                } else {
                    console.log(`❌ Delete failed for ${fileToDelete.fileId}: ${result.message}`);
                    failCount++;
                    results.push(`❌ ${fileToDelete.fileId}: ${result.message}`);
                }
                
            } catch (error) {
                console.error(`❌ Error processing ${fileToDelete.fileId}:`, error);
                
                failCount++;
                results.push(`❌ ${fileToDelete.fileId}: ${error.message}`);
            }
        }
        
        // Output summary with categorized results
        const summary = `Google Drive file deletion completed:
✅ Deleted: ${successCount}
❌ Failed: ${failCount} total
  🚫 No permission: ${noAccessCount}
  ℹ️ Already deleted: ${notFoundCount}

💡 Fix permission errors: Give service account Manager/Owner access
   Service account: drive-airtable@drive-airtable-464711.iam.gserviceaccount.com

Details:
${results.slice(0, 10).join('\n')}${results.length > 10 ? `\n... and ${results.length - 10} more` : ''}`;
        
        console.log(summary);
        output.set("Summary", summary);
        
    } catch (error) {
        console.error('❌ Main deletion automation error:', error);
        const errorMessage = `Automation failed: ${error.message}`;
        console.error(errorMessage);
        output.set("Error", errorMessage);
    }
}

// Run the deletion automation
deleteFilesFromDrive();