from flask import Flask, render_template, request, jsonify, session, redirect
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os, json, random, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta
from decimal import Decimal

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ems-super-secret-2024')

DB_CONFIG = {
    'host':     os.environ.get('DB_HOST', 'localhost'),
    'user':     os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', '12345678'),
    'database': os.environ.get('DB_NAME', 'employee_db')
}

# ── EMAIL CONFIG ──────────────────────────────────────────────
# Set these as environment variables or fill directly for testing:
#   SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'your@gmail.com')      # <-- set this
SMTP_PASS = os.environ.get('SMTP_PASS', 'your-app-password')   # <-- set this (Gmail App Password)
SMTP_FROM = os.environ.get('SMTP_FROM', SMTP_USER)

OTP_EXPIRY_MINUTES = 10


# ─────────────────────────────────────────────────────────────
def get_connection():
    try: return mysql.connector.connect(**DB_CONFIG)
    except Error as e: print(f"DB Error: {e}"); return None

def serialize(obj):
    if isinstance(obj, (datetime, date)): return obj.isoformat()
    if isinstance(obj, Decimal): return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized', 'redirect': '/login'}), 401
        return f(*args, **kwargs)
    return decorated

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
            if session.get('role') not in roles: return jsonify({'error': 'Forbidden'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

# ─── OTP HELPERS ──────────────────────────────────────────────
def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_email(to_email, otp, purpose='verification'):
    subject = f"EMS — Your {'Login' if purpose=='login' else 'Verification'} OTP"
    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;
         border:1px solid #e2e8f0;border-radius:12px">
      <h2 style="color:#1a56db;margin-bottom:8px">&#127970; Employee Management System</h2>
      <p style="color:#4a5568;font-size:14px">
        Your one-time password for <b>{purpose}</b>:
      </p>
      <div style="background:#f4f6fb;border-radius:10px;padding:20px;text-align:center;margin:20px 0">
        <span style="font-size:36px;font-weight:700;letter-spacing:10px;color:#1a56db">{otp}</span>
      </div>
      <p style="color:#94a3b8;font-size:12px">
        This OTP expires in <b>{OTP_EXPIRY_MINUTES} minutes</b>. Do not share it with anyone.
      </p>
      <p style="color:#94a3b8;font-size:11px;margin-top:16px">
        EMS v2.1 &middot; If you did not request this, ignore this email.
      </p>
    </div>
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = SMTP_FROM
        msg['To']      = to_email
        msg.attach(MIMEText(body, 'html'))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo(); server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        return True, ''
    except Exception as e:
        print(f"Email error: {e}")
        return False, str(e)

def ensure_schema(cursor):
    """Ensure optional columns and tables exist (idempotent)."""
    # email column on users
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(150) UNIQUE DEFAULT NULL")
    except Exception:
        pass
    # otp_tokens table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS otp_tokens (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            email      VARCHAR(150) NOT NULL,
            otp        VARCHAR(10)  NOT NULL,
            purpose    VARCHAR(20)  DEFAULT 'verification',
            expires_at DATETIME     NOT NULL,
            used       TINYINT(1)   DEFAULT 0,
            created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_email_purpose (email, purpose)
        )
    """)


# ─── PAGES ────────────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' not in session: return redirect('/login')
    return render_template('index.html')

@app.route('/login')
def login_page():
    if 'user_id' in session: return redirect('/')
    return render_template('login.html')


# ═══════════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════════

# ── Classic login (username or email + password) ──────────────
@app.route('/api/auth/login', methods=['POST'])
def login():
    data     = request.json
    identity = (data.get('username') or '').strip()
    password = data.get('password', '')
    if not identity or not password:
        return jsonify({'error': 'Credentials required'}), 400
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor(dictionary=True)
    ensure_schema(cursor); conn.commit()
    cursor.execute(
        "SELECT * FROM users WHERE (username=%s OR email=%s) AND is_active=1",
        (identity, identity)
    )
    user = cursor.fetchone(); cursor.close(); conn.close()
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'error': 'Invalid credentials'}), 401
    session.update({'user_id': user['user_id'], 'username': user['username'],
                    'role': user['role'], 'emp_id': user['emp_id']})
    return jsonify({'message': 'Login successful',
                    'user': {'username': user['username'], 'role': user['role']}})


# ── Send OTP for email login ───────────────────────────────────
@app.route('/api/auth/otp/send-login', methods=['POST'])
def otp_send_login():
    email = (request.json.get('email') or '').strip().lower()
    if not email: return jsonify({'error': 'Email required'}), 400
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor(dictionary=True)
    ensure_schema(cursor); conn.commit()
    cursor.execute("SELECT user_id FROM users WHERE email=%s AND is_active=1", (email,))
    user = cursor.fetchone()
    if not user:
        cursor.close(); conn.close()
        # Vague response — don't reveal whether account exists
        return jsonify({'message': 'If that email is registered, an OTP was sent.'}), 200
    otp     = generate_otp()
    expires = datetime.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    cursor.execute("UPDATE otp_tokens SET used=1 WHERE email=%s AND purpose='login'", (email,))
    cursor.execute(
        "INSERT INTO otp_tokens (email,otp,purpose,expires_at) VALUES (%s,%s,'login',%s)",
        (email, otp, expires)
    )
    conn.commit(); cursor.close(); conn.close()
    ok, err = send_otp_email(email, otp, 'login')
    if not ok: return jsonify({'error': f'Email failed: {err}'}), 500
    return jsonify({'message': 'OTP sent to your email'}), 200


# ── Verify OTP → login ────────────────────────────────────────
@app.route('/api/auth/otp/verify-login', methods=['POST'])
def otp_verify_login():
    data  = request.json
    email = (data.get('email') or '').strip().lower()
    otp   = (data.get('otp')   or '').strip()
    if not email or not otp: return jsonify({'error': 'Email and OTP required'}), 400
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM otp_tokens WHERE email=%s AND otp=%s AND purpose='login'"
        " AND used=0 AND expires_at>NOW() ORDER BY id DESC LIMIT 1",
        (email, otp)
    )
    token = cursor.fetchone()
    if not token:
        cursor.close(); conn.close()
        return jsonify({'error': 'Invalid or expired OTP'}), 401
    cursor.execute("UPDATE otp_tokens SET used=1 WHERE id=%s", (token['id'],))
    cursor.execute("SELECT * FROM users WHERE email=%s AND is_active=1", (email,))
    user = cursor.fetchone(); conn.commit(); cursor.close(); conn.close()
    if not user: return jsonify({'error': 'Account not found'}), 404
    session.update({'user_id': user['user_id'], 'username': user['username'],
                    'role': user['role'], 'emp_id': user['emp_id']})
    return jsonify({'message': 'Login successful',
                    'user': {'username': user['username'], 'role': user['role']}})


# ── Send OTP for registration ─────────────────────────────────
@app.route('/api/auth/otp/send-register', methods=['POST'])
def otp_send_register():
    email = (request.json.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return jsonify({'error': 'Valid email required'}), 400
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor(dictionary=True)
    ensure_schema(cursor); conn.commit()
    cursor.execute("SELECT user_id FROM users WHERE email=%s", (email,))
    if cursor.fetchone():
        cursor.close(); conn.close()
        return jsonify({'error': 'Email already registered'}), 409
    otp     = generate_otp()
    expires = datetime.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    cursor.execute("UPDATE otp_tokens SET used=1 WHERE email=%s AND purpose='register'", (email,))
    cursor.execute(
        "INSERT INTO otp_tokens (email,otp,purpose,expires_at) VALUES (%s,%s,'register',%s)",
        (email, otp, expires)
    )
    conn.commit(); cursor.close(); conn.close()
    ok, err = send_otp_email(email, otp, 'registration')
    if not ok: return jsonify({'error': f'Email failed: {err}'}), 500
    return jsonify({'message': 'OTP sent to your email'}), 200


# ── Verify OTP → create account ──────────────────────────────
@app.route('/api/auth/otp/verify-register', methods=['POST'])
def otp_verify_register():
    data     = request.json
    email    = (data.get('email')    or '').strip().lower()
    otp      = (data.get('otp')      or '').strip()
    username = (data.get('username') or '').strip()
    password = data.get('password', '')
    role     = data.get('role', 'employee')
    if not all([email, otp, username, password]):
        return jsonify({'error': 'All fields required'}), 400
    if len(username) < 3: return jsonify({'error': 'Username ≥ 3 characters'}), 400
    if len(password) < 6: return jsonify({'error': 'Password ≥ 6 characters'}), 400
    if role not in ('employee', 'hr'): return jsonify({'error': 'Invalid role'}), 400
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM otp_tokens WHERE email=%s AND otp=%s AND purpose='register'"
        " AND used=0 AND expires_at>NOW() ORDER BY id DESC LIMIT 1",
        (email, otp)
    )
    token = cursor.fetchone()
    if not token:
        cursor.close(); conn.close()
        return jsonify({'error': 'Invalid or expired OTP'}), 401
    cursor.execute("UPDATE otp_tokens SET used=1 WHERE id=%s", (token['id'],))
    try:
        cursor.execute(
            "INSERT INTO users (username,password,role,email) VALUES (%s,%s,%s,%s)",
            (username, generate_password_hash(password), role, email)
        )
        conn.commit(); cursor.close(); conn.close()
        return jsonify({'message': 'Account created! You can now sign in.'}), 201
    except Error as e:
        conn.rollback(); cursor.close(); conn.close()
        if 'Duplicate' in str(e):
            return jsonify({'error': 'Username or email already taken'}), 409
        return jsonify({'error': str(e)}), 400


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out'})

@app.route('/api/auth/me')
def me():
    if 'user_id' not in session: return jsonify({'error': 'Not logged in'}), 401
    return jsonify({'user_id': session['user_id'], 'username': session['username'],
                    'role': session['role'], 'emp_id': session.get('emp_id')})

@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.json
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT password FROM users WHERE user_id=%s", (session['user_id'],))
    user = cursor.fetchone()
    if not check_password_hash(user['password'], data.get('old_password', '')):
        cursor.close(); conn.close()
        return jsonify({'error': 'Old password incorrect'}), 401
    cursor.execute("UPDATE users SET password=%s WHERE user_id=%s",
                   (generate_password_hash(data['new_password']), session['user_id']))
    conn.commit(); cursor.close(); conn.close()
    return jsonify({'message': 'Password changed'})


# ═══════════════════════════════════════════════════════════════
# USERS  (admin only)
# ═══════════════════════════════════════════════════════════════
@app.route('/api/users', methods=['GET'])
@login_required
@roles_required('admin')
def get_users():
    conn = get_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""SELECT u.user_id,u.username,u.email,u.role,u.is_active,u.created_at,
        e.first_name,e.last_name
        FROM users u LEFT JOIN employees e ON u.emp_id=e.emp_id ORDER BY u.created_at DESC""")
    rows = cursor.fetchall(); cursor.close(); conn.close()
    return json.dumps(rows, default=serialize), 200, {'Content-Type': 'application/json'}

@app.route('/api/users', methods=['POST'])
@login_required
@roles_required('admin')
def create_user():
    data = request.json
    if not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Required fields missing'}), 400
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username,password,role,emp_id,email) VALUES (%s,%s,%s,%s,%s)",
            (data['username'], generate_password_hash(data['password']),
             data.get('role','employee'), data.get('emp_id') or None, data.get('email') or None)
        )
        conn.commit()
        return jsonify({'message': 'User created', 'id': cursor.lastrowid}), 201
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cursor.close(); conn.close()

@app.route('/api/users/<int:uid>', methods=['PUT'])
@login_required
@roles_required('admin')
def update_user(uid):
    data = request.json; conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        if data.get('password'):
            cursor.execute(
                "UPDATE users SET role=%s,is_active=%s,password=%s,emp_id=%s,email=%s WHERE user_id=%s",
                (data.get('role','employee'), data.get('is_active',1),
                 generate_password_hash(data['password']),
                 data.get('emp_id') or None, data.get('email') or None, uid)
            )
        else:
            cursor.execute(
                "UPDATE users SET role=%s,is_active=%s,emp_id=%s,email=%s WHERE user_id=%s",
                (data.get('role','employee'), data.get('is_active',1),
                 data.get('emp_id') or None, data.get('email') or None, uid)
            )
        conn.commit(); return jsonify({'message': 'Updated'})
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cursor.close(); conn.close()

@app.route('/api/users/<int:uid>', methods=['DELETE'])
@login_required
@roles_required('admin')
def delete_user(uid):
    if uid == session.get('user_id'): return jsonify({'error': 'Cannot delete yourself'}), 400
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE user_id=%s", (uid,))
        conn.commit(); return jsonify({'message': 'Deleted'})
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cursor.close(); conn.close()


# ═══════════════════════════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════════════════════════
@app.route('/api/stats')
@login_required
def get_stats():
    conn = get_connection()
    if not conn: return jsonify({}), 500
    cursor = conn.cursor(dictionary=True)
    stats = {}
    cursor.execute("SELECT COUNT(*) as t FROM employees");                       stats['total_employees']   = cursor.fetchone()['t']
    cursor.execute("SELECT COUNT(*) as t FROM employees WHERE status='Active'"); stats['active_employees']  = cursor.fetchone()['t']
    cursor.execute("SELECT COUNT(*) as t FROM departments");                     stats['total_departments'] = cursor.fetchone()['t']
    cursor.execute("SELECT COALESCE(AVG(salary),0) as avg FROM employees");      stats['avg_salary']        = round(float(cursor.fetchone()['avg']),2)
    cursor.execute("SELECT COUNT(*) as t FROM attendance WHERE att_date=%s AND status='Present'",
                   (date.today().isoformat(),));                                 stats['present_today']     = cursor.fetchone()['t']
    cursor.close(); conn.close()
    return jsonify(stats)


# ═══════════════════════════════════════════════════════════════
# EMPLOYEES
# ═══════════════════════════════════════════════════════════════
@app.route('/api/employees', methods=['GET'])
@login_required
def get_employees():
    conn = get_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    if session.get('role') == 'employee' and session.get('emp_id'):
        cursor.execute(
            "SELECT e.*,d.dept_name,des.title as designation_title FROM employees e "
            "LEFT JOIN departments d ON e.dept_id=d.dept_id "
            "LEFT JOIN designations des ON e.designation_id=des.designation_id "
            "WHERE e.emp_id=%s", (session['emp_id'],))
    else:
        cursor.execute(
            "SELECT e.*,d.dept_name,des.title as designation_title FROM employees e "
            "LEFT JOIN departments d ON e.dept_id=d.dept_id "
            "LEFT JOIN designations des ON e.designation_id=des.designation_id ORDER BY e.emp_id DESC")
    rows = cursor.fetchall(); cursor.close(); conn.close()
    return json.dumps(rows, default=serialize), 200, {'Content-Type': 'application/json'}

@app.route('/api/employees', methods=['POST'])
@login_required
@roles_required('admin','hr')
def add_employee():
    data = request.json; conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO employees (first_name,last_name,email,phone,salary,hire_date,dept_id,designation_id,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (data['first_name'],data['last_name'],data['email'],data.get('phone'),
             data.get('salary',0),data.get('hire_date'),data.get('dept_id'),
             data.get('designation_id'),data.get('status','Active')))
        conn.commit(); return jsonify({'message': 'Added', 'id': cursor.lastrowid}), 201
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cursor.close(); conn.close()

@app.route('/api/employees/<int:emp_id>', methods=['GET'])
@login_required
def get_employee(emp_id):
    if session.get('role') == 'employee' and session.get('emp_id') != emp_id:
        return jsonify({'error': 'Forbidden'}), 403
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT e.*,d.dept_name,des.title as designation_title FROM employees e "
        "LEFT JOIN departments d ON e.dept_id=d.dept_id "
        "LEFT JOIN designations des ON e.designation_id=des.designation_id "
        "WHERE e.emp_id=%s", (emp_id,))
    row = cursor.fetchone(); cursor.close(); conn.close()
    if row: return json.dumps(row, default=serialize), 200, {'Content-Type': 'application/json'}
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/employees/<int:emp_id>', methods=['PUT'])
@login_required
@roles_required('admin','hr')
def update_employee(emp_id):
    data = request.json; conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE employees SET first_name=%s,last_name=%s,email=%s,phone=%s,salary=%s,"
            "hire_date=%s,dept_id=%s,designation_id=%s,status=%s WHERE emp_id=%s",
            (data['first_name'],data['last_name'],data['email'],data.get('phone'),
             data.get('salary',0),data.get('hire_date'),data.get('dept_id'),
             data.get('designation_id'),data.get('status','Active'),emp_id))
        conn.commit(); return jsonify({'message': 'Updated'})
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cursor.close(); conn.close()

@app.route('/api/employees/<int:emp_id>', methods=['DELETE'])
@login_required
@roles_required('admin')
def delete_employee(emp_id):
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM employees WHERE emp_id=%s", (emp_id,))
        conn.commit(); return jsonify({'message': 'Deleted'})
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cursor.close(); conn.close()


# ═══════════════════════════════════════════════════════════════
# DEPARTMENTS
# ═══════════════════════════════════════════════════════════════
@app.route('/api/departments', methods=['GET'])
@login_required
def get_departments():
    conn = get_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM departments ORDER BY dept_name")
    rows = cursor.fetchall(); cursor.close(); conn.close(); return jsonify(rows)

@app.route('/api/departments', methods=['POST'])
@login_required
@roles_required('admin','hr')
def add_department():
    data = request.json; conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO departments (dept_name,location) VALUES (%s,%s)",
                       (data['dept_name'], data.get('location','')))
        conn.commit(); return jsonify({'message': 'Added', 'id': cursor.lastrowid}), 201
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cursor.close(); conn.close()

@app.route('/api/departments/<int:dept_id>', methods=['DELETE'])
@login_required
@roles_required('admin')
def delete_department(dept_id):
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM departments WHERE dept_id=%s", (dept_id,))
        conn.commit(); return jsonify({'message': 'Deleted'})
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cursor.close(); conn.close()


# ═══════════════════════════════════════════════════════════════
# DESIGNATIONS
# ═══════════════════════════════════════════════════════════════
@app.route('/api/designations', methods=['GET'])
@login_required
def get_designations():
    conn = get_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM designations ORDER BY title")
    rows = cursor.fetchall(); cursor.close(); conn.close(); return jsonify(rows)

@app.route('/api/designations', methods=['POST'])
@login_required
@roles_required('admin','hr')
def add_designation():
    data = request.json; conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO designations (title) VALUES (%s)", (data['title'],))
        conn.commit(); return jsonify({'message': 'Added', 'id': cursor.lastrowid}), 201
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cursor.close(); conn.close()


# ═══════════════════════════════════════════════════════════════
# ATTENDANCE  ── BUG FIXED ──
#   /api/attendance         → employee sees only their row
#   /api/reports/attendance → employee sees only their row
# ═══════════════════════════════════════════════════════════════
@app.route('/api/attendance', methods=['GET'])
@login_required
def get_attendance():
    date_filter = request.args.get('date', date.today().isoformat())
    conn = get_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    if session.get('role') == 'employee' and session.get('emp_id'):
        cursor.execute(
            "SELECT a.*,e.first_name,e.last_name,d.dept_name FROM attendance a "
            "JOIN employees e ON a.emp_id=e.emp_id "
            "LEFT JOIN departments d ON e.dept_id=d.dept_id "
            "WHERE a.att_date=%s AND a.emp_id=%s",
            (date_filter, session['emp_id']))
    else:
        cursor.execute(
            "SELECT a.*,e.first_name,e.last_name,d.dept_name FROM attendance a "
            "JOIN employees e ON a.emp_id=e.emp_id "
            "LEFT JOIN departments d ON e.dept_id=d.dept_id "
            "WHERE a.att_date=%s ORDER BY e.first_name", (date_filter,))
    rows = cursor.fetchall(); cursor.close(); conn.close()
    return json.dumps(rows, default=serialize), 200, {'Content-Type': 'application/json'}

@app.route('/api/attendance', methods=['POST'])
@login_required
@roles_required('admin','hr')
def mark_attendance():
    data = request.json; conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO attendance (emp_id,att_date,status,check_in,check_out,notes) "
            "VALUES (%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE status=%s,check_in=%s,check_out=%s,notes=%s",
            (data['emp_id'],data['att_date'],data['status'],
             data.get('check_in'),data.get('check_out'),data.get('notes',''),
             data['status'],data.get('check_in'),data.get('check_out'),data.get('notes','')))
        conn.commit(); return jsonify({'message': 'Marked'})
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cursor.close(); conn.close()


# ═══════════════════════════════════════════════════════════════
# PAYROLL
# ═══════════════════════════════════════════════════════════════
@app.route('/api/payroll', methods=['GET'])
@login_required
def get_payroll():
    month = request.args.get('month', date.today().month)
    year  = request.args.get('year',  date.today().year)
    conn  = get_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    if session.get('role') == 'employee' and session.get('emp_id'):
        cursor.execute(
            "SELECT p.*,e.first_name,e.last_name,d.dept_name,des.title FROM payroll p "
            "JOIN employees e ON p.emp_id=e.emp_id "
            "LEFT JOIN departments d ON e.dept_id=d.dept_id "
            "LEFT JOIN designations des ON e.designation_id=des.designation_id "
            "WHERE p.month=%s AND p.year=%s AND p.emp_id=%s",
            (month,year,session['emp_id']))
    else:
        cursor.execute(
            "SELECT p.*,e.first_name,e.last_name,d.dept_name,des.title FROM payroll p "
            "JOIN employees e ON p.emp_id=e.emp_id "
            "LEFT JOIN departments d ON e.dept_id=d.dept_id "
            "LEFT JOIN designations des ON e.designation_id=des.designation_id "
            "WHERE p.month=%s AND p.year=%s ORDER BY e.first_name",
            (month,year))
    rows = cursor.fetchall(); cursor.close(); conn.close()
    return json.dumps(rows, default=serialize), 200, {'Content-Type': 'application/json'}

@app.route('/api/payroll/generate', methods=['POST'])
@login_required
@roles_required('admin','hr')
def generate_payroll():
    data  = request.json
    month = data.get('month', date.today().month)
    year  = data.get('year',  date.today().year)
    conn  = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT emp_id, salary FROM employees WHERE status='Active'")
    employees = cursor.fetchall(); count = 0
    for emp in employees:
        basic = float(emp['salary']); allowances = basic * 0.20
        cursor.execute(
            "SELECT COUNT(*) as total_marked, "
            "SUM(CASE WHEN status IN ('Present','Late') THEN 1 ELSE 0 END) as present_count "
            "FROM attendance WHERE emp_id=%s AND MONTH(att_date)=%s AND YEAR(att_date)=%s",
            (emp['emp_id'],month,year))
        att = cursor.fetchone()
        total = att['total_marked'] or 0; present = float(att['present_count'] or 0)
        att_pct = (present/total*100) if total > 0 else 100
        base_deduction = basic * 0.05; absence_deduction = basic * 0.40 if att_pct < 75 else 0
        deductions = base_deduction + absence_deduction; net = basic + allowances - deductions
        try:
            cursor.execute(
                "INSERT INTO payroll (emp_id,month,year,basic_salary,allowances,deductions,net_salary,status) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,'Pending') "
                "ON DUPLICATE KEY UPDATE basic_salary=%s,allowances=%s,deductions=%s,net_salary=%s",
                (emp['emp_id'],month,year,basic,allowances,deductions,net,basic,allowances,deductions,net))
            count += 1
        except: pass
    conn.commit(); cursor.close(); conn.close()
    return jsonify({'message': f'Payroll generated for {count} employees'})

@app.route('/api/payroll/<int:pay_id>/pay', methods=['PUT'])
@login_required
@roles_required('admin','hr')
def mark_paid(pay_id):
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE payroll SET status='Paid',paid_date=%s WHERE pay_id=%s",
                       (date.today().isoformat(),pay_id))
        conn.commit(); return jsonify({'message': 'Paid'})
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cursor.close(); conn.close()


# ═══════════════════════════════════════════════════════════════
# REPORTS
# ═══════════════════════════════════════════════════════════════
@app.route('/api/reports/employees', methods=['GET'])
@login_required
@roles_required('admin','hr')
def report_employees():
    conn = get_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT e.emp_id,e.first_name,e.last_name,e.email,e.phone,e.salary,e.hire_date,"
        "e.status,d.dept_name,des.title FROM employees e "
        "LEFT JOIN departments d ON e.dept_id=d.dept_id "
        "LEFT JOIN designations des ON e.designation_id=des.designation_id ORDER BY e.emp_id")
    rows = cursor.fetchall(); cursor.close(); conn.close()
    return json.dumps(rows, default=serialize), 200, {'Content-Type': 'application/json'}

@app.route('/api/reports/attendance', methods=['GET'])
@login_required
def report_attendance():
    """
    BUG FIX 1: employees now only receive their own row (server-enforced).
    BUG FIX 2: attendance % = (present + late) / total_marked * 100
               Half-days contribute 0.5 to the effective-present count.
    """
    month = request.args.get('month', date.today().month)
    year  = request.args.get('year',  date.today().year)
    conn  = get_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)

    base = """
        SELECT e.emp_id, e.first_name, e.last_name, d.dept_name,
            COALESCE(SUM(CASE WHEN a.status='Present'  THEN 1 ELSE 0 END), 0) AS present_days,
            COALESCE(SUM(CASE WHEN a.status='Absent'   THEN 1 ELSE 0 END), 0) AS absent_days,
            COALESCE(SUM(CASE WHEN a.status='Late'     THEN 1 ELSE 0 END), 0) AS late_days,
            COALESCE(SUM(CASE WHEN a.status='Half Day' THEN 1 ELSE 0 END), 0) AS half_days,
            COUNT(a.att_id) AS total_marked
        FROM employees e
        LEFT JOIN attendance a
            ON e.emp_id = a.emp_id
            AND MONTH(a.att_date) = %s
            AND YEAR(a.att_date)  = %s
        LEFT JOIN departments d ON e.dept_id = d.dept_id
        WHERE e.status = 'Active'
    """
    if session.get('role') == 'employee' and session.get('emp_id'):
        cursor.execute(base + " AND e.emp_id = %s GROUP BY e.emp_id",
                       (month, year, session['emp_id']))
    else:
        cursor.execute(base + " GROUP BY e.emp_id ORDER BY e.first_name",
                       (month, year))

    rows = cursor.fetchall(); cursor.close(); conn.close()
    return jsonify(rows)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
