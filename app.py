from flask import Flask, render_template, request, jsonify, make_response
import mysql.connector
from mysql.connector import Error
import os
import json
from datetime import datetime, date
from decimal import Decimal

app = Flask(__name__)

# ─── DB CONFIG ────────────────────────────────
# For local: set your password below
# For Render: set environment variable DATABASE_URL or individual vars
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', '12345678'),
    'database': os.environ.get('DB_NAME', 'employee_db')
}

def get_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"DB Error: {e}")
        return None

def serialize(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

# ─── MAIN ─────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

# ─── STATS ────────────────────────────────────
@app.route('/api/stats')
def get_stats():
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB connection failed'}), 500
    cursor = conn.cursor(dictionary=True)
    stats = {}
    cursor.execute("SELECT COUNT(*) as total FROM employees")
    stats['total_employees'] = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM employees WHERE status='Active'")
    stats['active_employees'] = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM departments")
    stats['total_departments'] = cursor.fetchone()['total']
    cursor.execute("SELECT COALESCE(AVG(salary),0) as avg FROM employees")
    stats['avg_salary'] = round(float(cursor.fetchone()['avg']), 2)
    today = date.today().isoformat()
    cursor.execute("SELECT COUNT(*) as total FROM attendance WHERE att_date=%s AND status='Present'", (today,))
    stats['present_today'] = cursor.fetchone()['total']
    cursor.close(); conn.close()
    return jsonify(stats)

# ─── EMPLOYEES ────────────────────────────────
@app.route('/api/employees', methods=['GET'])
def get_employees():
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB connection failed'}), 500
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.*, d.dept_name, des.title as designation_title
        FROM employees e
        LEFT JOIN departments d ON e.dept_id = d.dept_id
        LEFT JOIN designations des ON e.designation_id = des.designation_id
        ORDER BY e.emp_id DESC
    """)
    rows = cursor.fetchall()
    cursor.close(); conn.close()
    return json.dumps(rows, default=serialize), 200, {'Content-Type': 'application/json'}

@app.route('/api/employees', methods=['POST'])
def add_employee():
    data = request.json
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB connection failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO employees (first_name,last_name,email,phone,salary,hire_date,dept_id,designation_id,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (data['first_name'],data['last_name'],data['email'],data.get('phone'),
              data.get('salary',0),data.get('hire_date'),data.get('dept_id'),
              data.get('designation_id'),data.get('status','Active')))
        conn.commit()
        return jsonify({'message': 'Employee added', 'id': cursor.lastrowid}), 201
    except Error as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()

@app.route('/api/employees/<int:emp_id>', methods=['GET'])
def get_employee(emp_id):
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB connection failed'}), 500
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.*, d.dept_name, des.title as designation_title
        FROM employees e
        LEFT JOIN departments d ON e.dept_id=d.dept_id
        LEFT JOIN designations des ON e.designation_id=des.designation_id
        WHERE e.emp_id=%s
    """, (emp_id,))
    row = cursor.fetchone()
    cursor.close(); conn.close()
    if row: return json.dumps(row, default=serialize), 200, {'Content-Type': 'application/json'}
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/employees/<int:emp_id>', methods=['PUT'])
def update_employee(emp_id):
    data = request.json
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB connection failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE employees SET first_name=%s,last_name=%s,email=%s,phone=%s,
            salary=%s,hire_date=%s,dept_id=%s,designation_id=%s,status=%s WHERE emp_id=%s
        """, (data['first_name'],data['last_name'],data['email'],data.get('phone'),
              data.get('salary',0),data.get('hire_date'),data.get('dept_id'),
              data.get('designation_id'),data.get('status','Active'),emp_id))
        conn.commit()
        return jsonify({'message': 'Updated'})
    except Error as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()

@app.route('/api/employees/<int:emp_id>', methods=['DELETE'])
def delete_employee(emp_id):
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB connection failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM employees WHERE emp_id=%s", (emp_id,))
        conn.commit()
        return jsonify({'message': 'Deleted'})
    except Error as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()

# ─── DEPARTMENTS ──────────────────────────────
@app.route('/api/departments', methods=['GET'])
def get_departments():
    conn = get_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM departments ORDER BY dept_name")
    rows = cursor.fetchall()
    cursor.close(); conn.close()
    return jsonify(rows)

@app.route('/api/departments', methods=['POST'])
def add_department():
    data = request.json
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO departments (dept_name,location) VALUES (%s,%s)",
                       (data['dept_name'], data.get('location','')))
        conn.commit()
        return jsonify({'message': 'Added', 'id': cursor.lastrowid}), 201
    except Error as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()

@app.route('/api/departments/<int:dept_id>', methods=['DELETE'])
def delete_department(dept_id):
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM departments WHERE dept_id=%s", (dept_id,))
        conn.commit()
        return jsonify({'message': 'Deleted'})
    except Error as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()

# ─── DESIGNATIONS ─────────────────────────────
@app.route('/api/designations', methods=['GET'])
def get_designations():
    conn = get_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM designations ORDER BY title")
    rows = cursor.fetchall()
    cursor.close(); conn.close()
    return jsonify(rows)

@app.route('/api/designations', methods=['POST'])
def add_designation():
    data = request.json
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO designations (title) VALUES (%s)", (data['title'],))
        conn.commit()
        return jsonify({'message': 'Added', 'id': cursor.lastrowid}), 201
    except Error as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()

# ─── ATTENDANCE ───────────────────────────────
@app.route('/api/attendance', methods=['GET'])
def get_attendance():
    date_filter = request.args.get('date', date.today().isoformat())
    conn = get_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.*, e.first_name, e.last_name, d.dept_name
        FROM attendance a
        JOIN employees e ON a.emp_id=e.emp_id
        LEFT JOIN departments d ON e.dept_id=d.dept_id
        WHERE a.att_date=%s ORDER BY e.first_name
    """, (date_filter,))
    rows = cursor.fetchall()
    cursor.close(); conn.close()
    return json.dumps(rows, default=serialize), 200, {'Content-Type': 'application/json'}

@app.route('/api/attendance', methods=['POST'])
def mark_attendance():
    data = request.json
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO attendance (emp_id, att_date, status, check_in, check_out, notes)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE status=%s, check_in=%s, check_out=%s, notes=%s
        """, (data['emp_id'], data['att_date'], data['status'],
              data.get('check_in'), data.get('check_out'), data.get('notes',''),
              data['status'], data.get('check_in'), data.get('check_out'), data.get('notes','')))
        conn.commit()
        return jsonify({'message': 'Attendance marked'})
    except Error as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()

@app.route('/api/attendance/summary/<int:emp_id>', methods=['GET'])
def attendance_summary(emp_id):
    month = request.args.get('month', date.today().month)
    year = request.args.get('year', date.today().year)
    conn = get_connection()
    if not conn: return jsonify({})
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT status, COUNT(*) as count FROM attendance
        WHERE emp_id=%s AND MONTH(att_date)=%s AND YEAR(att_date)=%s
        GROUP BY status
    """, (emp_id, month, year))
    rows = cursor.fetchall()
    cursor.close(); conn.close()
    return jsonify(rows)

# ─── PAYROLL ──────────────────────────────────
@app.route('/api/payroll', methods=['GET'])
def get_payroll():
    month = request.args.get('month', date.today().month)
    year = request.args.get('year', date.today().year)
    conn = get_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*, e.first_name, e.last_name, d.dept_name, des.title
        FROM payroll p
        JOIN employees e ON p.emp_id=e.emp_id
        LEFT JOIN departments d ON e.dept_id=d.dept_id
        LEFT JOIN designations des ON e.designation_id=des.designation_id
        WHERE p.month=%s AND p.year=%s ORDER BY e.first_name
    """, (month, year))
    rows = cursor.fetchall()
    cursor.close(); conn.close()
    return json.dumps(rows, default=serialize), 200, {'Content-Type': 'application/json'}

@app.route('/api/payroll/generate', methods=['POST'])
def generate_payroll():
    data = request.json
    month = data.get('month', date.today().month)
    year = data.get('year', date.today().year)
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT emp_id, salary FROM employees WHERE status='Active'")
    employees = cursor.fetchall()
    count = 0
    for emp in employees:
        basic = float(emp['salary'])
        allowances = basic * 0.20

        # Attendance percentage
        cursor.execute("""
            SELECT COUNT(*) as total_marked,
                   SUM(CASE WHEN status IN ('Present','Late') THEN 1 ELSE 0 END) as present_count
            FROM attendance
            WHERE emp_id=%s AND MONTH(att_date)=%s AND YEAR(att_date)=%s
        """, (emp['emp_id'], month, year))
        att = cursor.fetchone()
        total = att['total_marked'] or 0
        present = float(att['present_count'] or 0)
        att_pct = (present / total * 100) if total > 0 else 100

        # Deduction logic
        base_deduction = basic * 0.05
        absence_deduction = basic * 0.40 if att_pct < 75 else 0
        deductions = base_deduction + absence_deduction
        net = basic + allowances - deductions

        try:
            cursor.execute("""
                INSERT INTO payroll (emp_id, month, year, basic_salary, allowances, deductions, net_salary, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'Pending')
                ON DUPLICATE KEY UPDATE basic_salary=%s, allowances=%s, deductions=%s, net_salary=%s
            """, (emp['emp_id'], month, year, basic, allowances, deductions, net,
                  basic, allowances, deductions, net))
            count += 1
        except: pass
    conn.commit()
    cursor.close(); conn.close()
    return jsonify({'message': f'Payroll generated for {count} employees'})

@app.route('/api/payroll/<int:pay_id>/pay', methods=['PUT'])
def mark_paid(pay_id):
    conn = get_connection()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE payroll SET status='Paid', paid_date=%s WHERE pay_id=%s",
                       (date.today().isoformat(), pay_id))
        conn.commit()
        return jsonify({'message': 'Marked as paid'})
    except Error as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cursor.close(); conn.close()

# ─── REPORTS ──────────────────────────────────
@app.route('/api/reports/employees', methods=['GET'])
def report_employees():
    conn = get_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.emp_id, e.first_name, e.last_name, e.email, e.phone,
               e.salary, e.hire_date, e.status, d.dept_name, des.title
        FROM employees e
        LEFT JOIN departments d ON e.dept_id=d.dept_id
        LEFT JOIN designations des ON e.designation_id=des.designation_id
        ORDER BY e.emp_id
    """)
    rows = cursor.fetchall()
    cursor.close(); conn.close()
    return json.dumps(rows, default=serialize), 200, {'Content-Type': 'application/json'}

@app.route('/api/reports/attendance', methods=['GET'])
def report_attendance():
    month = request.args.get('month', date.today().month)
    year = request.args.get('year', date.today().year)
    conn = get_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.emp_id, e.first_name, e.last_name, d.dept_name,
               SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) as present_days,
               SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END) as absent_days,
               SUM(CASE WHEN a.status='Late' THEN 1 ELSE 0 END) as late_days,
               SUM(CASE WHEN a.status='Half Day' THEN 1 ELSE 0 END) as half_days,
               COUNT(a.att_id) as total_marked
        FROM employees e
        LEFT JOIN attendance a ON e.emp_id=a.emp_id AND MONTH(a.att_date)=%s AND YEAR(a.att_date)=%s
        LEFT JOIN departments d ON e.dept_id=d.dept_id
        WHERE e.status='Active'
        GROUP BY e.emp_id ORDER BY e.first_name
    """, (month, year))
    rows = cursor.fetchall()
    cursor.close(); conn.close()
    return jsonify(rows)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
