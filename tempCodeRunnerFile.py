import os
import csv
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, url_for
from users import USERS
os.makedirs('data', exist_ok=True)  # Create folder if not exists
from io import BytesIO
import base64
import qrcode

app = Flask(__name__)
app.secret_key = 'nayan-top-secret'
CSV_FILE = os.path.join(os.path.dirname(__file__), 'data', 'leave_request.csv')

def get_hod_branches(name):
    if name == "HOD BTech/MBA":
        return ['BTECH CS', 'BTECH CE', 'BTECH AI-ML', 'BTECH IT', 'MBA TECH CE']
    elif name == "HOD BPharm/Textile":
        return ['B-PHARM', 'TEXTILE']
    return []

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    role = request.form['role']
    user_id = request.form['user_id']
    password = request.form['password']

    for key, user in USERS.items():
        if key.startswith(role) and user_id == user['id'] and password == user['password']:
            session['role'] = role
            session['user_id'] = user_id
            session['name'] = user.get('name', role.capitalize())
            return redirect(url_for(role))
    return "Invalid credentials. <a href='/'>Try again</a>"

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


@app.route('/student')
def student():
    if session.get('role') != 'student':
        return redirect('/')

    student_id = session.get('user_id')
    leaves = []
    qr_base64 = None

    print("🔍 Looking for student:", student_id)

    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['student_id'] == student_id:
                    print("📄 Row found:", row)
                    start = datetime.fromisoformat(row['start_date'])
                    end = datetime.fromisoformat(row['end_date'])
                    days = (end - start).days + 1
                    row['days'] = str(days)
                    leaves.append(row)

                    if row['status'] == 'Granted':
                        print("✅ Granted row found. Generating QR...")
                        qr_text = (
                            f"🎟️ Leave Gate Pass\n"
                            f"Name: {row['student_name']}\n"
                            f"ID: {row['student_id']}\n"
                            f"Branch: {row['branch']}\n"
                            f"Batch: {row['batch']}\n"
                            f"Dates: {row['start_date']} to {row['end_date']}\n"
                            f"Reason: {row['reason']}"
                        )
                        qr_img = qrcode.make(qr_text)
                        buffer = BytesIO()
                        qr_img.save(buffer, format="PNG")
                        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
                        break

    print("🖨️ Total leaves found:", len(leaves))
    return render_template('student.html', name=session['name'], student_id=session['user_id'], leaves=leaves, qr=qr_base64)


@app.route('/submit-leave', methods=['POST'])
def submit_leave():
    if session.get('role') != 'student':
        return redirect('/')

    form = request.form

    leave_request = {
        'student_name': form.get('student_name', '').strip(),
        'student_id': form.get('student_id', '').strip(),
        'year': form.get('year', '').strip(),
        'attendance': form.get('attendance', '').strip(),
        'email': form.get('email', '').strip(),
        'branch': form.get('branch', '').strip(),
        'batch': form.get('batch', '').strip(),
        'reason': form.get('reason', '').strip(),
        'start_date': form.get('start_date', '').strip(),
        'end_date': form.get('end_date', '').strip(),
        'mentor': form.get('mentor', '').strip(),
        'status': 'Pending',  # Default status
        'timestamp': datetime.now().isoformat()  # Current timestamp
    }

    # ✅ Make sure CSV folder exists
    os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)

    # ✅ Write to CSV with headers if not exists
    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, 'a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=leave_request.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(leave_request)

    print("✅ Saved to CSV:", leave_request)  # For your terminal logs

    return f"""
        <h3>Leave request submitted successfully! ✅</h3>
        <p><a href="/student">Go back</a></p>
    """


@app.route('/teacher')
def teacher():
    if session.get('role') != 'teacher':
        return redirect('/')
    
    teacher_name = session.get('name')

    # Read data from CSV
    leaves = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['status'] == 'Pending' and row['mentor'] == teacher_name:
                    leaves.append(row)

    return render_template('teacher.html', name=teacher_name, leaves=leaves)

@app.route('/teacher-action', methods=['POST'])
def teacher_action():
    if session.get('role') != 'teacher':
        return redirect('/')

    student_id = request.form['student_id']
    timestamp = request.form['timestamp']
    action = request.form['action']

    updated_rows = []

    with open(CSV_FILE, newline='') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['student_id'] == student_id and row['timestamp'] == timestamp:
                if action == 'approve':
                    row['status'] = 'Teacher Approved'
                elif action == 'reject':
                    row['status'] = 'Rejected'
            updated_rows.append(row)

    with open(CSV_FILE, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=updated_rows[0].keys())
        writer.writeheader()
        writer.writerows(updated_rows)

    return redirect('/teacher')


@app.route('/hod')
def hod():
    if session.get('role') != 'hod':
        return redirect('/')

    hod_name = session.get('name')
    leaves = []

    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['status'] == 'Teacher Approved' and row['branch'] in get_hod_branches(hod_name):
                    start = datetime.fromisoformat(row['start_date'])
                    end = datetime.fromisoformat(row['end_date'])
                    days = (end - start).days + 1
                    row['days'] = str(days)
                    leaves.append(row)

    return render_template('hod.html', name=hod_name, leaves=leaves)

@app.route('/hod-action', methods=['POST'])
def hod_action():
    if session.get('role') != 'hod':
        return redirect('/')

    student_id = request.form['student_id']
    timestamp = request.form['timestamp']
    action = request.form['action']
    days = int(request.form['days'])

    updated_rows = []
    with open(CSV_FILE, newline='') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['student_id'] == student_id and row['timestamp'] == timestamp:
                if action == 'approve':
                    if days > 3:
                        row['status'] = 'HOD Approved'
                    else:
                        row['status'] = 'Granted'
                elif action == 'reject':
                    row['status'] = 'Rejected'
            updated_rows.append(row)

    with open(CSV_FILE, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=updated_rows[0].keys())
        writer.writeheader()
        writer.writerows(updated_rows)

    return redirect('/hod')

@app.route('/dean')
def dean():
    if session.get('role') != 'dean':
        return redirect('/')

    leaves = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['status'] == 'HOD Approved':
                    start = datetime.fromisoformat(row['start_date'])
                    end = datetime.fromisoformat(row['end_date'])
                    days = (end - start).days + 1
                    row['days'] = str(days)
                    leaves.append(row)

    return render_template('dean.html', name=session.get('name'), leaves=leaves)

@app.route('/dean-action', methods=['POST'])
def dean_action():
    if session.get('role') != 'dean':
        return redirect('/')

    student_id = request.form['student_id']
    timestamp = request.form['timestamp']
    action = request.form['action']

    updated_rows = []
    with open(CSV_FILE, newline='') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['student_id'] == student_id and row['timestamp'] == timestamp:
                if action == 'approve':
                    row['status'] = 'Granted'
                elif action == 'reject':
                    row['status'] = 'Rejected'
            updated_rows.append(row)

    with open(CSV_FILE, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=updated_rows[0].keys())
        writer.writeheader()
        writer.writerows(updated_rows)

    return redirect('/dean')

# ✅ Flask app starts AFTER all routes are defined
import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)



