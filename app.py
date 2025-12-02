from flask import Flask, render_template, jsonify, request, session, redirect, url_for
import gspread 
from urllib.parse import unquote
import functools
import os
import json

import auth

app = Flask(__name__)
app.secret_key = os.environ.get('APP_SECRET_KEY', 'a_strong_fallback_secret_for_local_dev_only') 

SPREADSHEET_TITLE = 'Donz Hockey Main'

HARDCODED_SERVICE_ACCOUNT_JSON = '''
{
  "type": "service_account",
  "project_id": "donz-hockey-app",
  "private_key_id": "572edd9f7cf2ce34406b96174a605ebd8ab04ebf",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCz1Nx6EAJFg0YK\nSAvfgsHolHMzWT1O2q0HWVG6cA/pboR3Odn02w/rTjCP/szF7L+SWSXJ7tqEpzHD\nJv91pCxh32QjjuavkbPMU6hiPTGPsQw+XKKhWFyKgdlTkaksUeZTUveRK6eiTIsq\nFrWQIWwvYEjuLIYQD+o38/HCIPs6CdrZaUbfNlkkt6aRrqUFbHdqQuL0SvGMZZk/\n0ztLOqX5Eysy2lcykBCdGHgrhiHkbK2aFQ8Qd2N55zcSdQqqNZ4d4YeM2TT3RNCE\nAzH06y/25p2IfTSboBBBtT/kmS03EozMmNBlIkucHSEslY3l2W9GGbq0zy/b8DTt\n/Hku9eZFAgMBAAECggEAE21jhCxGkovj/ShbYAIYQLAI4fs6DFLDbo/PrHx+u5Ec\n7mRpj3I6/gisZmH4bUluSLkow+/x23LUhWipIGRkBw7DGrRNZ5ot/lzvS+2gdQ2D\nbRlE2HlbRftRJx4NUKRoZYgJBr3Ylkf+oMVjR/bUYSndtx1IPmP5waGw9G/rtBE9\n4C5N0+iPOl7OgZRSoe8K5x9lGqn1gWtonHOK2Qt9BXsepdsfYxV2sRABu97TMVBz\nshFernFEljIE26U10QSvQN7pRQnedB+uii0fi7AYWLw1lslEuXIWETKmkioMBVTd\nHl1mxX+BGasI0C+FLwNxmo8Xko2nPiltftCxdr13AQKBgQDt3tgQAQuzYy+/WS4m\nb7KciRGHU5DoqoTApVhAd0hVV4XynvXUSWwrnta3yozhndjkwxwqINu1K3bwu12A\nBVS3CVBfQgusfLyQ5kDatIAHe6M8lxlwBd3mI8aqujuhXZaFNeA3pnhJcFdLAeNs\nKymPeUQgy7cI6AALDRZgZuowqQKBgQDBiZpA6YGaXmJEWapJIj+cLKW077rleENp\nh9E0ze6f2tI0yC+H5KA26Jvmtf9cCkc8vn2j26aQPgA39hz8GabAHi3cpq0CVP7A\nRbCiJF9xDp+3CSabHzPdDbUG9kZ4fcFdYkXcngoYZuw4HIJ/gRm5HFt0PxtE5gd2\nPF9J+iCePQKBgFicsWSU3yT+iCUCNdz/s0v5I7QD/3GNRFL3xX6OcRXJuw59BRsG\nFxPQ4jApdn397XSa8n0HLJG7FV3sjpJIahydjaFO20ZwWVapT/OpViBzgIXrzAAd\nT2KSZUnogppEYPRS86oHi7vf68T3eR8snRjjleuZuB/LPWjggTt8WzWxAoGBALWZ\nHgpGkHt+kIo98FCLOFCcfCgYwa/LdsWw0RbRHFUWiCNKq37BgavD+3Ux1JhSdKGE\nxHNaCSJTavUXk/7hOtwN9U6TfscvZZKYUbLymjOFW0vt5DGtx4Zl9DTCJUGuDiBH\ns/HcwPBAsum7pp9pTe+psg6ToEy34syIvYi2kKCpAoGABDlhlG0/HR5O0xW2YZHm\nf6FEaqOM47uwdzFw7XokYZG9xa5WdZhgct0kAkHlptqWXtCv9N6zc5IpX8tmTtY8\noyw84ixuMsGM9s/Kbw/Viq3sOrIRdMKPfYH05vsgw9AKBDTQuE8qr+UdwPvVAgAb\nU1WEVsrJXE0W9MvnkaOxo3g=\n-----END PRIVATE KEY-----\n",
  "client_email": "donz-hockey-app@donz-hockey-app.iam.gserviceaccount.com",
  "client_id": "101304973236799054348",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/donz-hockey-app%40donz-hockey-app.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}
'''

def get_sheet(worksheet_name):
    
    service_account_json_string = HARDCODED_SERVICE_ACCOUNT_JSON.strip()

    if not service_account_json_string:
        raise ValueError("Service account JSON is missing or still set to the placeholder.")

    try:
        credentials_info = json.loads(service_account_json_string)
    except json.JSONDecodeError:
        raise ValueError("Failed to parse hardcoded JSON string. Ensure it is copied correctly.")

    try:
        client = gspread.service_account_info(credentials_info)
    except Exception as e:
        raise RuntimeError(f"gspread authorization failed. Check your JSON format: {e}")

    sheet = client.open(SPREADSHEET_TITLE)
    return sheet.worksheet(worksheet_name)

def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if auth.verify_user(username, password):
            session['user'] = username
            session['role'] = auth.get_role(username)
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid Credentials")
            
    return render_template('login.html')

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
                is_paid = (str(row[col_idx]).upper() == 'TRUE') if col_idx < len(row) else False
                payment_status[month] = is_paid
            players.append({"id": row[0], "name": row[1], "position": row[2] if len(row)>2 else "", "payments": payment_status})
        return jsonify({"months": months, "players": players})
    except Exception as e: 
        print(f"Error fetching payment data: {e}")
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
        ws.update_cell(cell.row, col_index, data['status'])
        return jsonify({"success": True})
    except Exception as e: 
        print(f"Error updating payment: {e}")
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
        print(f"Error fetching roster: {e}")
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
            if status.upper() == 'P':
                present_players.append(names_column[i])
        return jsonify(present_players)
    except Exception as e: 
        print(f"Error fetching attendance for date: {e}")
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
        return jsonify({"success": True, "message": f"Saved {date_str}"})

    except Exception as e: 
        print(f"Error submitting attendance: {e}")
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
            if not row: continue
            name = row[0]
            row_data = row[1:]
            while len(row_data) < len(dates): row_data.append("")
            total_present = row_data.count('P')
            records.append({"name": name, "history": row_data, "total": total_present})
        return jsonify({"dates": dates, "records": records})
    except Exception as e: 
        print(f"Error fetching history: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/player-details', methods=['GET'])
@login_required
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
        print(f"Error fetching player details: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run()