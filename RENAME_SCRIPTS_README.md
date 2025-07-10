# Google Drive File Renaming Scripts

This directory contains three Python scripts for renaming files in Google Drive using the service account credentials.

## Scripts Overview

### 1. `rename_drive_file.py` - Simple Single File Rename
**Purpose**: Rename a single file with command-line arguments
**Best for**: Quick, simple renames

```bash
python rename_drive_file.py <file_id> <new_name>
```

**Example:**
```bash
python rename_drive_file.py 1ABC123def456 "New File Name.pdf"
```

### 2. `batch_rename_drive_files.py` - Advanced Batch Rename
**Purpose**: Handle multiple files and different input formats
**Best for**: Batch operations, automation, flexibility

```bash
# Single file by ID
python batch_rename_drive_files.py --file 1ABC123def456 "New Name.pdf"

# Single file by URL
python batch_rename_drive_files.py --url "https://drive.google.com/file/d/1ABC123def456/view" "New Name.pdf"

# Batch from CSV
python batch_rename_drive_files.py --csv rename_list.csv

# Batch from JSON
python batch_rename_drive_files.py --json rename_list.json
```

### 3. `interactive_rename.py` - User-Friendly Interactive
**Purpose**: Step-by-step interactive interface
**Best for**: Non-technical users, learning, one-off renames

```bash
python interactive_rename.py
```

## Prerequisites

1. **Google Service Account Credentials**
   - Ensure `google_credentials.json` is in the same directory
   - Service account must have access to the Google Drive files/folders

2. **Python Dependencies**
   ```bash
   pip install google-api-python-client google-auth google-auth-oauthlib
   ```

3. **File Access**
   - The Google Drive files must be shared with the service account email
   - Service account email: `drive-airtable@drive-airtable-464711.iam.gserviceaccount.com`

## File Formats for Batch Operations

### CSV Format (`rename_list.csv`)
```csv
file_id,new_name
1ABC123def456,New Name 1.pdf
1XYZ789ghi012,New Name 2.pdf
1DEF345jkl678,New Name 3.docx
```

### JSON Format (`rename_list.json`)
```json
[
    {"file_id": "1ABC123def456", "new_name": "New Name 1.pdf"},
    {"file_id": "1XYZ789ghi012", "new_name": "New Name 2.pdf"},
    {"file_id": "1DEF345jkl678", "new_name": "New Name 3.docx"}
]
```

## Usage Examples

### Quick Single File Rename
```bash
# If you have the file ID
python rename_drive_file.py 1ABC123def456 "Invoice_2025_001.pdf"

# If you have the URL
python batch_rename_drive_files.py --url "https://drive.google.com/file/d/1ABC123def456/view" "Invoice_2025_001.pdf"
```

### Interactive Mode (Recommended for beginners)
```bash
python interactive_rename.py
```
Then follow the prompts:
1. Choose to enter file ID or URL
2. Enter the file identifier
3. Review current file information
4. Enter new name
5. Confirm the rename

### Batch Processing
```bash
# Create CSV file with your renames
echo "file_id,new_name" > my_renames.csv
echo "1ABC123def456,Document 1.pdf" >> my_renames.csv
echo "1XYZ789ghi012,Document 2.pdf" >> my_renames.csv

# Process the batch
python batch_rename_drive_files.py --csv my_renames.csv
```

## Error Handling

All scripts include comprehensive error handling:
- ✅ Validates file IDs and URLs
- ✅ Checks for missing credentials
- ✅ Verifies file access permissions
- ✅ Provides clear error messages
- ✅ Shows current vs new names before renaming

## Security Notes

- Keep `google_credentials.json` secure and never commit to version control
- The service account has limited permissions (only to shared folders)
- All operations are logged for audit purposes
- Scripts validate input to prevent common errors

## Integration with Main Flask App

These scripts use the same Google Drive service configuration as the main Flask application (`app.py`). They can be used:
- As standalone tools for manual file management
- As part of automated workflows
- For testing and debugging file operations
- For bulk operations outside of the Airtable integration

## Troubleshooting

### Common Issues:
1. **403 Forbidden**: Service account doesn't have access to the file
   - Share the file/folder with `drive-airtable@drive-airtable-464711.iam.gserviceaccount.com`

2. **File not found**: Invalid file ID
   - Double-check the file ID or URL
   - Ensure the file exists and is accessible

3. **Credentials error**: Missing or invalid credentials file
   - Ensure `google_credentials.json` exists in the script directory
   - Verify the credentials file is valid

### Debug Tips:
- Use the interactive script to test individual files first
- Check file permissions in Google Drive
- Verify the service account email has appropriate access
- Use `--help` flag with batch script for detailed usage information

## License
These scripts are part of the drive-airtable integration project and follow the same license terms.