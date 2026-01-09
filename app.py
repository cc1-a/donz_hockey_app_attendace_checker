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
        if response.status_code == 200 and data.get("status") == "success":
            print(f"WhatsApp Sent! Queue ID: {data.get('details', {}).get('queue_id')}")
            return True
        else:
            print(f"WhatsApp Failed: {data}")
            return False
    except Exception as e:
        print(f"WhatsApp Connection Error: {e}")
        return False

# --- REPORT GENERATORS ---

def generate_payment_report():
    print("Generating Payment Report...")
    try:
        ws = get_sheet('PAYMENTS2026')
        all_data = ws.get_all_values()
        if not all_data: return False
        
        headers = all_data[0]
        current_month = datetime.datetime.now().strftime("%B")
        
        if current_month not in headers:
            print(f"Month {current_month} missing.")
            return False

        col_index = headers.index(current_month)
        paid = []
        not_paid = []
        
        for row in all_data[1:]:
            if len(row) < 2 or not row[0]: continue
            name = row[1]
            status = row[col_index] if len(row) > col_index else "FALSE"
            
            if str(status).upper() == 'TRUE':
                paid.append(name)
            else:
                not_paid.append(name)
        
        msg = f"📢 *DONZ HOCKEY PAYMENT UPDATE*\n"
        msg += f"🗓️ Month: *{current_month}*\n\n"
        msg += "✅ *PAID:*\n" + ("\n".join([f"- {p}" for p in paid]) if paid else "- None yet") + "\n\n"
        msg += "❌ *NOT PAID:*\n" + ("\n".join([f"- {p}" for p in not_paid]) if not_paid else "- Everyone paid!") + "\n"
        msg += "\n_Please settle dues immediately._"
        
        return send_donz_announcement(msg)
        
    except Exception as e:
        print(f"Error: {e}")
        return False

def generate_attendance_report(date_str):
    print(f"Generating Attendance Report for {date_str}...")
    try:
        ws = get_sheet('ATTENDANCE 2026')
        all_data = ws.get_all_values()
        if not all_data: return "SHEET_EMPTY"

        headers = all_data[0]
        if date_str not in headers:
            return "DATE_NOT_FOUND" 

        col_index = headers.index(date_str)
        present_list = []

        for row in all_data[1:]:
            if len(row) <= col_index: continue
            name = row[0]
            status = row[col_index]
            if name and status.upper() == 'P':
                present_list.append(name)
        
        try:
            date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            nice_date = date_obj.strftime("%d %b %Y")
        except:
            nice_date = date_str

        count = len(present_list)
        
        msg = f"🏑 *DONZ HOCKEY ATTENDANCE*\n"
        msg += f"📅 Date: *{nice_date}*\n\n"
        msg += f"✅ *Present ({count}):*\n"
        
        if present_list:
            for p in present_list:
                msg += f"- {p}\n"
        else:
            msg += "- No attendance recorded.\n"
            
        result = send_donz_announcement(msg)
        return "SUCCESS" if result else "WHATSAPP_ERROR"

    except Exception as e:
        traceback.print_exc()
        return str(e)

# --- VERCEL CRON JOB ROUTE (Runs Daily at 10 AM UTC) ---
@app.route('/api/cron/daily-check', methods=['GET'])
def vercel_cron_job():
    day = datetime.datetime.now().day
    if day in [10, 20, 30]:
        print(f"Cron triggered on the {day}th. Sending Report...")
        success = generate_payment_report()
        return jsonify({"status": "Report Sent", "success": success})
    else:
        return jsonify({"status": "Skipped", "reason": f"Today is {day}, not 10/20/30."})

# --- ROUTES ---

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    referrer = request.referrer or url_for('index')
    
    if auth.verify_user(username, password):
        session['user'] = username
        session['role'] = auth.get_role(username)
        return redirect(referrer)
    else:
        sep = '&' if '?' in referrer else '?'
        return redirect(f"{referrer}{sep}login_error=1")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/')
def index():
    is_admin = session.get('role') == 'admin'
    return render_template('index.html', is_admin=is_admin)

@app.route('/attendance')
def attendance_page():
    is_admin = session.get('role') == 'admin'
    return render_template('attendance.html', is_admin=is_admin)

@app.route('/records')
def records_page():
    return render_template('records.html')

@app.route('/player/<path:name>')
def player_profile(name):
    decoded_name = unquote(name)
    return render_template('player.html', player_name=decoded_name)

# --- API ROUTES ---

@app.route('/api/data', methods=['GET'])
def get_payment_data():
    try:
        ws = get_sheet('PAYMENTS2026')
        all_data = ws.get_all_values()
        if not all_data: return jsonify({"error": "Sheet empty"}), 400
        
        headers = all_data[0]
        months = headers[3:]
        rows = all_data[1:]
        players = []
        for row in rows:
            if len(row) < 2 or not row[0]: continue
            payment_status = {}
            for i, month in enumerate(months):
                col_idx = 3 + i
                is_paid = (str(row[col_idx]).upper() == 'TRUE') if col_idx < len(row) else False
                payment_status[month] = is_paid
            players.append({"id": row[0], "name": row[1], "position": row[2] if len(row)>2 else "", "payments": payment_status})
        return jsonify({"months": months, "players": players})
    except Exception as e: 
        return jsonify({"error": str(e)}), 500

@app.route('/api/update', methods=['POST'])
@admin_required
def update_payment():
    data = request.json
    try:
        ws = get_sheet('PAYMENTS2026')
        headers = ws.row_values(1)
        col_index = headers.index(data['month']) + 1
        cell = ws.find(str(data['id']), in_column=1)
        if not cell: return jsonify({"success": False, "message": "ID not found"}), 404
        ws.update_cell(cell.row, col_index, data['status'])
        return jsonify({"success": True})
    except Exception as e: 
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/send-payment-report', methods=['POST'])
@admin_required
def manual_send_report():
    success = generate_payment_report()
    if success: return jsonify({"success": True, "message": "Payment Report Sent!"})
    else: return jsonify({"success": False, "message": "Failed. Check logs."}), 500

@app.route('/api/send-attendance-report', methods=['POST'])
@admin_required
def manual_send_attendance():
    try:
        data = request.json
        date_str = data.get('date')
        if not date_str: return jsonify({"success": False, "message": "No date provided"}), 400
        
        result_code = generate_attendance_report(date_str)
        
        if result_code == "SUCCESS":
            return jsonify({"success": True, "message": f"Report Sent for {date_str}!"})
        elif result_code == "DATE_NOT_FOUND":
            return jsonify({"success": False, "message": "Date not found in Sheet. Did you SAVE first?"}), 404
        elif result_code == "WHATSAPP_ERROR":
            return jsonify({"success": False, "message": "Wabot API Error (Check Quota/Connection)."}), 502
        else:
            return jsonify({"success": False, "message": f"Internal Error: {result_code}"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Server Crash: {str(e)}"}), 500

@app.route('/api/attendance-roster', methods=['GET'])
def get_attendance_roster():
    try:
        ws = get_sheet('ATTENDANCE 2026')
        names_column = ws.col_values(1)
        players = [{"id": name, "name": name} for name in names_column[1:] if name.strip()]
        return jsonify(players)
    except Exception as e: 
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-attendance-for-date', methods=['GET'])
def get_attendance_for_date():
    date_str = request.args.get('date')
    if not date_str: return jsonify([])
    try:
        ws = get_sheet('ATTENDANCE 2026')
        headers = ws.row_values(1)
        if date_str not in headers: return jsonify([]) 
        col_index = headers.index(date_str) + 1
        col_values = ws.col_values(col_index)
        names_column = ws.col_values(1)
        present_players = []
        for i in range(1, len(names_column)):
            status = col_values[i] if i < len(col_values) else ""
            if status.upper() == 'P':
                present_players.append(names_column[i])
        return jsonify(present_players)
    except Exception as e: 
        return jsonify({"error": str(e)}), 500

@app.route('/api/submit-attendance', methods=['POST'])
@admin_required
def submit_attendance():
    data = request.json
    date_str = data.get('date')
    present_names = data.get('ids', [])

    if not date_str: return jsonify({"success": False, "message": "No date provided"}), 400

    try:
        ws = get_sheet('ATTENDANCE 2026')
        headers = ws.row_values(1)
        
        if date_str in headers:
            col_index = headers.index(date_str) + 1
        else:
            col_index = len(headers) + 1
            ws.update_cell(1, col_index, date_str)
        
        sheet_names = ws.col_values(1)
        updates = []
        for i, sheet_name in enumerate(sheet_names):
            if i == 0: continue 
            row_num = i + 1
            new_val = 'P' if sheet_name in present_names else ''
            updates.append({
                'range': gspread.utils.rowcol_to_a1(row_num, col_index),
                'values': [[new_val]]
            })
        
        if updates: ws.batch_update(updates)
        return jsonify({"success": True, "message": f"Saved {date_str}"})

    except Exception as e: 
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/attendance-history', methods=['GET'])
def get_attendance_history():
    try:
        ws = get_sheet('ATTENDANCE 2026')
        all_data = ws.get_all_values()
        if not all_data: return jsonify({"dates": [], "records": []})

        headers = all_data[0]
        dates = headers[1:] 
        records = []
        for row in all_data[1:]:
            if not row: continue
            name = row[0]
            row_data = row[1:]
            while len(row_data) < len(dates): row_data.append("")
            total_present = row_data.count('P')
            records.append({"name": name, "history": row_data, "total": total_present})
        return jsonify({"dates": dates, "records": records})
    except Exception as e: 
        return jsonify({"error": str(e)}), 500

@app.route('/api/player-details', methods=['GET'])
def get_player_details():
    name = request.args.get('name')
    if not name: return jsonify({"error": "No name provided"})
    try:
        ws = get_sheet('ATTENDANCE 2026')
        try: cell = ws.find(name, in_column=1)
        except: return jsonify({"error": "Player not found"}), 404
        headers = ws.row_values(1)
        player_data = ws.row_values(cell.row)
        attended_dates = []
        for i in range(1, len(headers)):
            date = headers[i]
            status = player_data[i] if i < len(player_data) else ""
            if status.upper() == 'P': attended_dates.append(date)
        attended_dates.sort(reverse=True)
        return jsonify({"name": name, "total": len(attended_dates), "dates": attended_dates})
    except Exception as e: 
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
