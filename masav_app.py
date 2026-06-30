#!/usr/bin/env python3
"""
MASAV File Generator - Standalone Flask Server
================================================
Receives invoice data as JSON from Airtable, generates a MASAV (מס"ב)
direct debit file per the official spec, and uploads it to Google Drive.

Runs independently on its own port (default: 5003).

Usage:
    python3 masav_app.py
"""

import requests as _requests
import os
import sys
import io
import logging
import hmac
from datetime import datetime as dt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_env():
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value.strip()
        logger.info("Environment variables loaded from .env file")


load_env()

app = Flask(__name__)

# Configuration
GOOGLE_CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH', 'google_credentials.json')
FLASK_SERVER_TOKEN = os.getenv('FLASK_SERVER_TOKEN')
MASAV_GDRIVE_FOLDER_ID = os.getenv('MASAV_GDRIVE_FOLDER_ID', '')
MASAV_INSTITUTION_CODE = os.getenv('MASAV_INSTITUTION_CODE', '')   # 8 digits
MASAV_SENDER_CODE = os.getenv('MASAV_SENDER_CODE', '')             # 5 digits
MASAV_INSTITUTION_NAME = os.getenv('MASAV_INSTITUTION_NAME', '')   # up to 30 chars


def validate_bearer_token(auth_header):
    if not FLASK_SERVER_TOKEN:
        return True
    if not auth_header:
        return False
    try:
        auth_type, token = auth_header.split(' ', 1)
        if auth_type.lower() != 'bearer':
            return False
        return hmac.compare_digest(token, FLASK_SERVER_TOKEN)
    except Exception:
        return False


def get_drive_service():
    creds_path = os.path.join(os.path.dirname(__file__), GOOGLE_CREDENTIALS_PATH)
    credentials = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=credentials)


def upload_to_drive(file_content, file_name, folder_id, mime_type='application/octet-stream'):
    service = get_drive_service()
    file_metadata = {'name': file_name}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype=mime_type, resumable=True)
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, name, webViewLink',
        supportsAllDrives=True
    ).execute()

    return file.get('id'), file.get('webViewLink')


# ---------------------------------------------------------------------------
# MASAV file generation
# ---------------------------------------------------------------------------

def encode_hebrew(text, length):
    """Encode text to Windows-1255, pad/truncate to exact byte length.
    X-type fields: right-aligned (pad with spaces on the left)."""
    encoded = text.encode('windows-1255', errors='replace')
    if len(encoded) > length:
        encoded = encoded[:length]
    return encoded.ljust(length, b' ')


def num_field(value, length):
    """Format a numeric field: left-padded with zeros to exact length."""
    if value == '' or value is None:
        raise ValueError(f"Numeric field requires a value, got empty string")
    return str(int(value)).zfill(length).encode('ascii')[:length]


def alpha_field(text, length):
    """Format an alphanumeric (X) field: right-padded with spaces."""
    encoded = text.encode('windows-1255', errors='replace')
    if len(encoded) > length:
        encoded = encoded[:length]
    return encoded.ljust(length, b' ')


def validate_reference(ref):
    """Validate reference/אסמכתא per MASAV Note 1:
    - 20 chars, right-aligned with leading zeros
    - Last 6 chars must be numeric with at least one non-zero."""
    if len(ref) > 20:
        return False, "Reference exceeds 20 characters"
    padded = ref.zfill(20)
    last6 = padded[-6:]
    if not last6.isdigit():
        return False, "Last 6 characters of reference must be numeric"
    if last6 == '000000':
        return False, "Last 6 characters of reference must have at least one non-zero"
    return True, padded


def build_header(institution_code, charge_date, creation_date, sender_code, institution_name):
    """Build the 128-byte header record (K)."""
    rec = bytearray(128)
    pos = 0

    # 1. Record type (pos 1, len 1) = 'K'
    rec[0:1] = b'K'
    # 2. Institution code (pos 2-9, len 8, N)
    rec[1:9] = num_field(institution_code, 8)
    # 3. Currency (pos 10-11, len 2, N) = '00'
    rec[9:11] = b'00'
    # 4. Charge date (pos 12-17, len 6, N) YYMMDD
    rec[11:17] = charge_date.encode('ascii')[:6]
    # 5. Filler (pos 18, len 1, N) = '0'
    rec[17:18] = b'0'
    # 6. Serial number (pos 19-21, len 3, N) = '001'
    rec[18:21] = b'001'
    # 7. Filler (pos 22, len 1, N) = '0'
    rec[21:22] = b'0'
    # 8. Creation date (pos 23-28, len 6, N) YYMMDD
    rec[22:28] = creation_date.encode('ascii')[:6]
    # 9. Sender code (pos 29-33, len 5, N)
    rec[28:33] = num_field(sender_code, 5)
    # 10. Filler (pos 34-39, len 6, N) = zeros
    rec[33:39] = b'000000'
    # 11. Institution name (pos 40-69, len 30, X) right-aligned for Hebrew
    rec[39:69] = encode_hebrew(institution_name, 30)
    # 12. Filler (pos 70-125, len 56, X) = spaces
    rec[69:125] = b' ' * 56
    # 13. Header ID (pos 126-128, len 3, X) = 'KOT'
    rec[125:128] = b'KOT'

    assert len(rec) == 128
    return bytes(rec)


def build_transaction(institution_code, bank_code, branch, account_number,
                      customer_id, customer_name, amount_agorot, reference,
                      charge_period):
    """Build a 128-byte transaction record (1)."""
    rec = bytearray(128)

    # 1. Record type (pos 1) = '1'
    rec[0:1] = b'1'
    # 2. Institution code (pos 2-9, 8N)
    rec[1:9] = num_field(institution_code, 8)
    # 3. Currency (pos 10-11, 2N) = '00'
    rec[9:11] = b'00'
    # 4. Filler (pos 12-17, 6N) = '000000'
    rec[11:17] = b'000000'
    # 5. Bank code (pos 18-19, 2N)
    rec[17:19] = num_field(bank_code, 2)
    # 6. Branch number (pos 20-22, 3N)
    rec[19:22] = num_field(branch, 3)
    # 7. Account type (pos 23-26, 4N) = '0000'
    rec[22:26] = b'0000'
    # 8. Account number (pos 27-35, 9N)
    rec[26:35] = num_field(account_number, 9)
    # 9. Filler (pos 36, 1N) = '0'
    rec[35:36] = b'0'
    # 10. Customer ID (pos 37-45, 9N)
    rec[36:45] = num_field(customer_id, 9)
    # 11. Customer name (pos 46-61, 16X)
    rec[45:61] = encode_hebrew(customer_name, 16)
    # 12. Amount (pos 62-74, 13N) — 11 shekels + 2 agorot
    rec[61:74] = num_field(amount_agorot, 13)
    # 13. Reference / אסמכתא (pos 75-94, 20X)
    rec[74:94] = reference.encode('ascii')[:20].rjust(20, b'0')
    # 14. Charge period (pos 95-102, 8N)
    rec[94:102] = num_field(charge_period, 8)
    # 15. Text code (pos 103-105, 3N) = '000'
    rec[102:105] = b'000'
    # 16. Transaction type (pos 106-108, 3N) = '006'
    rec[105:108] = b'006'
    # 17. Filler (pos 109-126, 18N) = zeros
    rec[108:126] = b'0' * 18
    # 18. Filler (pos 127-128, 2X) = spaces
    rec[126:128] = b'  '

    assert len(rec) == 128
    return bytes(rec)


def build_total(institution_code, charge_date, total_amount_agorot, record_count):
    """Build the 128-byte total record (5)."""
    rec = bytearray(128)

    # 1. Record type (pos 1) = '5'
    rec[0:1] = b'5'
    # 2. Institution code (pos 2-9, 8N)
    rec[1:9] = num_field(institution_code, 8)
    # 3. Currency (pos 10-11, 2N) = '00'
    rec[9:11] = b'00'
    # 4. Charge date (pos 12-17, 6N)
    rec[11:17] = charge_date.encode('ascii')[:6]
    # 5. Filler (pos 18, 1N) = '0'
    rec[17:18] = b'0'
    # 6. Serial number (pos 19-21, 3N) = '001'
    rec[18:21] = b'001'
    # 7. Total amount (pos 22-36, 15N) — 13 shekel digits + 2 agorot digits
    rec[21:36] = num_field(total_amount_agorot, 15)
    # 8. Filler (pos 37-51, 15N) = zeros
    rec[36:51] = b'0' * 15
    # 9. Transaction count (pos 52-58, 7N)
    rec[51:58] = num_field(record_count, 7)
    # 10. Filler (pos 59-65, 7N) = zeros
    rec[58:65] = b'0' * 7
    # 11. Filler (pos 66-128, 63X) = spaces
    rec[65:128] = b' ' * 63

    assert len(rec) == 128
    return bytes(rec)


def build_nines_record():
    """Build the trailing 128-byte nines record."""
    return b'9' * 128


CRLF = b'\r\n'


def generate_masav_file(charge_date, records, institution_code, sender_code, institution_name):
    """Generate a complete MASAV charge file from a list of record dicts.
    Returns (file_bytes, record_count, total_amount_agorot)."""

    creation_date = dt.now().strftime('%y%m%d')
    lines = []

    # Header
    lines.append(build_header(
        institution_code, charge_date, creation_date,
        sender_code, institution_name
    ))

    total_agorot = 0
    for rec in records:
        amount = rec['amount']
        amount_agorot = round(amount * 100)
        if amount_agorot <= 0:
            raise ValueError(f"Amount must be > 0, got {amount}")

        valid, ref_or_err = validate_reference(rec.get('reference', ''))
        if not valid:
            raise ValueError(f"Invalid reference: {ref_or_err}")

        lines.append(build_transaction(
            institution_code=institution_code,
            bank_code=rec['bank_code'],
            branch=rec['branch'],
            account_number=rec['account_number'],
            customer_id=rec['customer_id'],
            customer_name=rec.get('customer_name', ''),
            amount_agorot=amount_agorot,
            reference=ref_or_err,
            charge_period=rec.get('charge_period', '00000000')
        ))
        total_agorot += amount_agorot

    # Total record
    lines.append(build_total(
        institution_code, charge_date, total_agorot, len(records)
    ))

    # Nines record
    lines.append(build_nines_record())

    # Join with CRLF
    file_content = CRLF.join(lines) + CRLF

    return file_content, len(records), total_agorot


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.route('/masav/generate', methods=['POST'])
def masav_generate():
    """Receive invoice data as JSON, generate MASAV file, upload to Google Drive."""
    try:
        auth_header = request.headers.get('Authorization')
        if not validate_bearer_token(auth_header):
            return jsonify({"error": "Unauthorized"}), 401

        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        charge_date = data.get('charge_date')
        records = data.get('records')

        # Institution config: request body overrides env vars
        institution_code = data.get('institution_code') or MASAV_INSTITUTION_CODE
        sender_code = data.get('sender_code') or MASAV_SENDER_CODE
        institution_name = data.get('institution_name') or MASAV_INSTITUTION_NAME
        gdrive_folder_id = data.get('gdrive_folder_id') or MASAV_GDRIVE_FOLDER_ID
        # Strip any query params that may be appended to the folder ID (e.g. ?zx=...)
        if gdrive_folder_id and '?' in gdrive_folder_id:
            gdrive_folder_id = gdrive_folder_id.split('?')[0]

        if not charge_date or not records:
            return jsonify({"error": "charge_date and records are required"}), 400

        if len(charge_date) != 6 or not charge_date.isdigit():
            return jsonify({"error": "charge_date must be YYMMDD format"}), 400

        if not isinstance(records, list) or len(records) == 0:
            return jsonify({"error": "records must be a non-empty array"}), 400

        if not institution_code or not sender_code:
            return jsonify({"error": "institution_code and sender_code are required"}), 400

        if not gdrive_folder_id:
            return jsonify({"error": "gdrive_folder_id is required"}), 400

        # Validate each record has required fields (also reject empty strings)
        required_fields = ['bank_code', 'branch', 'account_number', 'customer_id', 'amount', 'reference']
        for i, rec in enumerate(records):
            missing = [f for f in required_fields if not rec.get(f) and rec.get(f) != 0]
            if missing:
                return jsonify({"error": f"Record {i}: missing or empty fields: {', '.join(missing)}"}), 400

        # Generate the file
        logger.info(f"Generating MASAV file: charge_date={charge_date}, records={len(records)}")
        file_content, record_count, total_agorot = generate_masav_file(
            charge_date, records, institution_code, sender_code, institution_name
        )

        filename = f"masav_charges_{charge_date}.msv"
        logger.info(f"MASAV file generated: {filename}, {len(file_content)} bytes, "
                     f"{record_count} records, total {total_agorot} agorot")

        # Upload to Google Drive
        file_id, file_url = upload_to_drive(file_content, filename, gdrive_folder_id)
        logger.info(f"MASAV file uploaded to Drive: {file_id}")

        return jsonify({
            "success": True,
            "file_id": file_id,
            "file_url": file_url,
            "filename": filename,
            "record_count": record_count,
            "total_amount": total_agorot / 100,
            "file_size": len(file_content)
        })

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error generating MASAV file: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
@app.route('/masav/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'MASAV File Generator',
        'timestamp': dt.utcnow().isoformat(),
        'config': {
            'institution_code': bool(MASAV_INSTITUTION_CODE),
            'sender_code': bool(MASAV_SENDER_CODE),
            'gdrive_folder': bool(MASAV_GDRIVE_FOLDER_ID),
        }
    })




@app.route("/boi-rate", methods=["GET"])
def boi_rate():
    date = request.args.get("date", "")
    if not date or len(date) != 8 or not date.isdigit():
        return jsonify({"error": "date parameter required in YYYYMMDD format"}), 400

    url = f"https://www.boi.org.il/currency.xml?rdate={date}"
    try:
        resp = _requests.get(url, timeout=15)
        resp.raise_for_status()
    except _requests.RequestException as e:
        logger.error(f"BOI rate fetch failed: {e}")
        return jsonify({"error": f"Failed to fetch from BOI: {e}"}), 502

    if not resp.content or not resp.content.strip():
        return jsonify({"error": "Empty response from BOI"}), 502

    from flask import Response
    return Response(
        resp.content,
        status=200,
        content_type=resp.headers.get("Content-Type", "application/xml"),
        headers={"Access-Control-Allow-Origin": "*"},
    )

if __name__ == '__main__':
    port = int(os.environ.get('MASAV_PORT', 5003))

    if not MASAV_INSTITUTION_CODE or not MASAV_SENDER_CODE:
        logger.warning("MASAV_INSTITUTION_CODE / MASAV_SENDER_CODE not set — "
                        "set them in .env before sending requests")

    logger.info(f"Starting MASAV File Generator on port {port}")
    print(f"MASAV server: http://localhost:{port}/health")
    print(f"Generate endpoint: POST http://localhost:{port}/masav/generate")

    app.run(debug=False, host='0.0.0.0', port=port)
