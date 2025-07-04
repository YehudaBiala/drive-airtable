# NEXT CLAUDE SESSION - PRIORITY TASKS

## 🚨 IMMEDIATE FIXES NEEDED

### 1. Fix File Attachment Format Issue
**Current Problem**: 
- Server returns `file_attachment` as array but Airtable gets array, not actual attachment
- Data URL format may not be working correctly for Airtable AI field

**Debug Steps**:
1. Check Flask server logs: `ssh myserver "cd ~/public_html/drive-airtable && tail -20 app.log"`
2. Test data URL format in Airtable manually
3. Research proper Airtable attachment field format

**Files to Check**:
- `app.py:489` - `upload_file_to_airtable()` function
- `airtable_webhook_vision.js:86` - attachment handling

### 2. Add PDF Text Extraction Level/Endpoint
**Requirement**: 
- Dedicated endpoint for PDF text extraction only
- Separate from Vision API processing
- Should work with text-based PDFs efficiently

**Implementation**:
- Create `/extract-pdf-text` endpoint
- Use only PyPDF2 for fast text extraction
- Return plain text without Vision API processing

## 🔧 CURRENT SYSTEM STATE

### Server Status (as of 2025-07-04)
- **Drive-Airtable Flask**: ✅ Running on port 5001
- **Tranzila Flask**: ✅ Running on port 2000  
- **Combined API Proxy**: ✅ Working at api.officeours.co.il
- **OCR Chain**: PyPDF2 → Google Vision → EasyOCR (partially working)

### Recent Test Results
**File**: `Receipt_202505_028475_821.Pdf`
**Result**: 
```json
{
  "extracted_text": "PDF file: Receipt_202505_028475_821.Pdf - This appears to be a scanned or image-based PDF. Multiple OCR methods were attempted but no readable text was found.",
  "file_attachment": null,  // ← THIS IS THE PROBLEM
  "file_id": "1oq3BFmSOQ897NNBUj_ZrSGYTaRDpgNZs",
  "file_name": "Receipt_202505_028475_821.Pdf",
  "file_size": 150472
}
```

## 📋 TECHNICAL ISSUES TO RESOLVE

### Issue 1: EasyOCR Installation
**Problem**: `No module named 'easyocr'` despite installation
**Solution**: Reinstall or remove EasyOCR dependency (it's very large)

### Issue 2: PyPDF2 Version Conflicts  
**Problem**: `module 'PyPDF2' has no attribute 'PdfReader'`
**Status**: ✅ FIXED - Reinstalled PyPDF2==3.0.1

### Issue 3: Airtable File Upload API
**Problem**: 404 error on `/v0/appAttachments` endpoint
**Status**: ✅ FIXED - Using data URLs instead

## 🔄 VERSIONING STATUS

### Files with Proper Versioning:
- `airtable_webhook_vision_v1_security-token.js` (archived)
- `airtable_webhook_vision.js` (current - server-side upload)

### Files Needing Versioning:
- `app.py` (multiple changes, no versions created)

## 🎯 SUCCESS CRITERIA FOR NEXT SESSION

1. **File attachment works**: Airtable AI receives actual PDF content
2. **PDF text endpoint**: Fast text extraction for text-based PDFs  
3. **Clean OCR chain**: All methods working or properly disabled
4. **Proper versioning**: Create v2 versions of modified files

## 📝 QUICK START COMMANDS

```bash
# Check server status
ssh myserver "cd ~/public_html/drive-airtable && curl -s http://localhost:5001/health"

# View recent logs  
ssh myserver "cd ~/public_html/drive-airtable && tail -20 app.log"

# Test external API
curl -s https://api.officeours.co.il/api/health

# Restart Flask server
ssh myserver "cd ~/public_html/drive-airtable && ps aux | grep app.py | grep -v grep | awk '{print \$2}' | xargs kill && nohup python3 app.py > app.log 2>&1 &"
```

## 🔍 DEBUGGING FOCUS

The core issue is that Airtable AI needs the **actual file content**, not just error messages. The current approach:

1. ✅ OCR attempts (working)
2. ❌ File upload to Airtable (format issue)  
3. ❌ AI field processing (not receiving file)

**Next session should prioritize getting the PDF file into Airtable AI field correctly.**