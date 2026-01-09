from flask import Flask, render_template, jsonify, request, session, redirect, url_for
import gspread 
from urllib.parse import unquote
import functools
import os
import json
import requests
import datetime
import traceback
from dotenv import load_dotenv
import auth

load_dotenv() 

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'vB9$fG^kL@7pQzR3sY!wX4cH&m2dEaT5uI') 

SPREADSHEET_TITLE = 'Donz Hockey Main'

# --- GOOGLE SHEETS SETUP ---
try:
    google_auth_json_string = os.environ.get('GOOGLE_AUTH')
    if google_auth_json_string:
        CREDENTIALS_CONFIG = json.loads(google_auth_json_string)
        if 'private_key' in CREDENTIALS_CONFIG:
            CREDENTIALS_CONFIG['private_key'] = CREDENTIALS_CONFIG['private_key'].replace('\\n', '\n')
    else:
        CREDENTIALS_CONFIG = {} 
except Exception as e:
    print(f"Error loading credentials: {e}")
    CREDENTIALS_CONFIG = {}

def get_sheet(worksheet_name):
    if not CREDENTIALS_CONFIG:
        raise Exception("Google Credentials not configured.")
    client = gspread.service_account_from_dict(CREDENTIALS_CONFIG)
    sheet = client.open(SPREADSHEET_TITLE)
    return sheet.worksheet(worksheet_name)

# --- DECORATORS ---

def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            return jsonify({"success": False, "message": "Admin login required"}), 403
        return f(*args, **kwargs)
    return decorated_function

# --- WHATSAPP AUTOMATION ---

def send_donz_announcement(message):
    """Sends message via Wabot API"""
    url = "https://app.wabot.my/api/send_group"
    
    # --- LIVE GROUP ID (DONZ HOCKEY) ---
    group_id = "120363334408919344@g.us"
    # -----------------------------------
    
    instance_id = "696103D4D811C"
    access_token = "6935797c735a5"
    
    payload = {
        "group_id": group_id,
        "type": "text",
        "message": message,
        "instance_id": instance_id,
        "access_token": access_token
    }

    try:
        response = requests.post(url, json=payload, timeout=20)
        data = response.json()
        if response.status_code == 200 and data
