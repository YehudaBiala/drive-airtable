# 🔄 CLAUDE SESSION HANDOFF - 2025-07-04

## 🎯 IMMEDIATE ISSUE TO SOLVE

**PROBLEM**: File attachment format issue
- Server returns `file_attachment` as array: `[{url: "data:...", filename: "...", size: ..., type: "..."}]`
- Airtable AI field expects actual attachment object, not array
- Current result: `file_attachment: null` in Airtable automation

## 🚨 CRITICAL NEXT STEPS

### 1. Fix File Attachment Format (PRIORITY 1)
**Current Issue**: 
```javascript
// What we're sending:
file_attachment: [{url: "data:application/pdf;base64,JVBERi0...", filename: "Receipt.pdf"}]

// What Airtable AI needs:
file_attachment: {url: "data:application/pdf;base64,JVBERi0...", filename: "Receipt.pdf"}
```

**Quick Fix**: Change `app.py:489` from returning array to single object

### 2. Add PDF Text Extraction Endpoint (PRIORITY 2)  
**Need**: Fast `/extract-pdf-text` endpoint for text-based PDFs
**Why**: Current Vision API processing is overkill for simple text PDFs

### 3. Test File Processing Chain
**Verify**: Airtable AI can actually process the data URL format

## 📋 CURRENT SYSTEM STATE

### Servers Running ✅
- Drive-Airtable Flask: `localhost:5001` 
- Tranzila Flask: `localhost:2000`
- Combined API: `https://api.officeours.co.il/api/`

### Last Test Result
**File**: `Receipt_202505_028475_821.Pdf`
**OCR**: ❌ Failed (expected - scanned PDF)  
**File Upload**: ❌ Format issue (`file_attachment: null`)

### Files Modified This Session
- `app.py` - Added file upload, fixed PyPDF2, needs versioning
- `airtable_webhook_vision.js` - Simplified, server handles upload
- `requirements.txt` - Added EasyOCR, PyMuPDF
- Created: `airtable_webhook_vision_v1_security-token.js` (backup)

## 🔧 QUICK DEBUG COMMANDS

```bash
# Check server status
ssh myserver "curl -s http://localhost:5001/health"

# View recent logs
ssh myserver "cd ~/public_html/drive-airtable && tail -20 app.log"

# Test API endpoint  
curl -s https://api.officeours.co.il/api/health

# Restart if needed
ssh myserver "cd ~/public_html/drive-airtable && ps aux | grep app.py | grep -v grep | awk '{print \$2}' | xargs kill && nohup python3 app.py > app.log 2>&1 &"
```

## 📁 DOCUMENTATION READY

- ✅ `NEXT_SESSION_TASKS.md` - Detailed technical tasks
- ✅ `PROJECT_STATUS.md` - Updated with current issues  
- ✅ `files.csv` - File tracking with versioning status
- ✅ All changes committed to git

## 🎯 SUCCESS DEFINITION

**DONE WHEN**: Airtable AI field receives actual PDF content and can process/analyze the document to suggest filename.

---
**Next Claude session is ready to continue immediately! 🚀**