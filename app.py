from flask import Flask, render_template, jsonify, request, session, redirect, url_for
import gspread
from urllib.parse import unquote
import functools
import os
import json
import auth

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_temporary_fallback_key')

SPREADSHEET_TITLE = 'Donz Hockey Main'
GLOBAL_GSHEET_CLIENT = None

google_auth_json_string = os.environ.get('GOOGLE_AUTH')

try:
    if not google_auth_json_string:
        CREDENTIALS_CONFIG = {}
    else:
        CREDENTIALS_CONFIG = json.loads(google_auth_json_string)

    if CREDENTIALS_CONFIG:
        GLOBAL_GSHEET_CLIENT = gspread.service_account_from_dict(CREDENTIALS_CONFIG)

except json.JSONDecodeError as e:
    CREDENTIALS_CONFIG = {}
except Exception as e:
    GLOBAL_GSHEET_CLIENT = None


def get_sheet(worksheet_name):
    if not GLOBAL_GSHEET_CLIENT:
        raise ConnectionError("gspread client is not initialized due to credential error.")

    sheet = GLOBAL_GSHEET_CLIENT.open(SPREADSHEET_TITLE)
    return sheet.worksheet(worksheet_name)

def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next') or url_for('index')
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if auth.verify_user(username, password):
            session['user'] = username
            session['role'] = auth.get_role(username)
            return redirect(next_url)
        else:
            return render_template('login.html', error="Invalid Credentials")

    return render_template('login.html', next_url=next_url)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    is_admin = session.get('role') == 'admin'
    return render_template('index.html', is_admin=is_admin)

@app.route('/attendance')
@login_required
def attendance_page():
    is_admin = session.get('role') == 'admin'
    return render_template('attendance.html', is_admin=is_admin)

@app.route('/records')
@login_required
def records_page():
    return render_template('records.html')

@app.route('/player/<path:name>')
@login_required
def player_profile(name):
    decoded_name = unquote(name)
    return render_template('player.html', player_name=decoded_name)

@app.route('/api/data', methods=['GET'])
@login_required
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
                is_paid = (str(row[col_idx]).strip().upper() == 'TRUE') if col_idx < len(row) else False
                payment_status[month] = is_paid
            players.append({
                "id": row[0],
                "name": row[1],
                "position": row[2] if len(row) > 2 else "",
                "payments": payment_status
            })
        return jsonify({"months": months, "players": players})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/update', methods=['POST'])
@login_required
def update_payment():
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    data = request.json
    try:
        ws = get_sheet('PAYMENTS2026')
        headers = ws.row_values(1)
        col_index = headers.index(data['month']) + 1
        cell = ws.find(str(data['id']), in_column=1)
        if not cell: return jsonify({"success": False, "message": "ID not found"}), 404
        
        status_value = 'TRUE' if data['status'] else 'FALSE'
        ws.update_cell(cell.row, col_index, status_value)
        return jsonify({"success": True})
    except ValueError:
        return jsonify({"success": False, "message": f"Month '{data.get('month')}' not found in headers."}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/attendance-roster', methods=['GET'])
@login_required
def get_attendance_roster():
    try:
        ws = get_sheet('ATTENDANCE 2026')
        names_column = ws.col_values(1)
        players = []
        for name in names_column[1:]:
            if name.strip():
                players.append({"id": name, "name": name})
        return jsonify(players)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-attendance-for-date', methods=['GET'])
@login_required
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
            if names_column[i].strip() and status.strip().upper() == 'P':
                present_players.append(names_column[i])
                
        return jsonify(present_players)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/submit-attendance', methods=['POST'])
@login_required
def submit_attendance():
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 403

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
        return jsonify({"success": True, "message": f"Attendance saved for {date_str}"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/attendance-history', methods=['GET'])
@login_required
def get_attendance_history():
    try:
        ws = get_sheet('ATTENDANCE 2026')
        all_data = ws.get_all_values()
        if not all_data: return jsonify({"dates": [], "records": []})

        headers = all_data[0]
        dates = headers[1:]
        records = []
        
        for row in all_data[1:]:
            if not row or not row[0].strip(): continue
            name = row[0]
            row_data = row[1:]
            
            while len(row_data) < len(dates): row_data.append("")
            
            total_present = row_data.count('P')
            records.append({"name": name, "history": row_data, "total": total_present})
            
        return jsonify({"dates": dates, "records": records})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/player-details', methods=['GET'])
@login_required
def get_player_details():
    name = request.args.get('name')
    if not name: return jsonify({"error": "No name provided"}), 400
    try:
        ws = get_sheet('ATTENDANCE 2026')
        
        try: cell = ws.find(name, in_column=1)
        except gspread.exceptions.CellNotFound: return jsonify({"error": "Player not found"}), 404
            
        headers = ws.row_values(1)
        player_data = ws.row_values(cell.row)
        
        attended_dates = []
        for i in range(1, len(headers)):
            date = headers[i]
            status = player_data[i] if i < len(player_data) else ""
            if status.strip().upper() == 'P': attended_dates.append(date)
            
        attended_dates.sort(reverse=True)
        return jsonify({"name": name, "total": len(attended_dates), "dates": attended_dates})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
