// Airtable Automation Script for Google Drive File Deletion
// Triggered when delete field is populated - deletes single file
// Uses Flask server endpoint to handle Google Drive API operations

const FLASK_SERVER_URL = 'https://api.officeours.co.il/api';
const FLASK_SERVER_TOKEN = input.secret('receipt_server_token');

// Get file_id from automation trigger
let config = input.config();
let fileId = config.fileId;

if (!fileId) {
    console.error("❌ No file ID provided");
    output.set("Result", "Error: No file ID");
    return;
}

console.log(`🗑️ Deleting file: ${fileId}`);

try {
    const response = await fetch(`${FLASK_SERVER_URL}/auto-delete-file`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${FLASK_SERVER_TOKEN}`
        },
        body: JSON.stringify({ file_id: fileId })
    });

    const result = await response.json();

    if (response.ok && result.success) {
        console.log(`✅ ${result.message}`);
        output.set("Result", `✅ Deleted: ${result.message}`);
    } else {
        const errorMsg = result.error || result.message || 'Unknown error';
        console.error(`❌ Delete failed: ${errorMsg}`);
        output.set("Result", `❌ Failed: ${errorMsg}`);
    }
} catch (error) {
    console.error(`❌ Error: ${error.message}`);
    output.set("Result", `❌ Error: ${error.message}`);
}
