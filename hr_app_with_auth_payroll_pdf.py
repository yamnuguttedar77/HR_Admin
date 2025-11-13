# hr_app_with_auth_payroll_pdf.py
# IMPORTANT: Remove 'pip install streamlit' from inside the script (should not be in Python files)

# ---------------------------
# FULL CODE FROM CANVAS (cleaned)
# ---------------------------
# You can now run this: streamlit run hr_app_with_auth_payroll_pdf.py

import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime
from passlib.hash import pbkdf2_sha256
from fpdf import FPDF
import io

# ---------------------------
# Database setup
# ---------------------------
conn = sqlite3.connect('hr_system_auth.db', check_same_thread=False)
cur = conn.cursor()

cur.execute('''
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password_hash TEXT,
    role TEXT,
    emp_id INTEGER
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS employees(
    emp_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    department TEXT,
    designation TEXT,
    basic_salary REAL DEFAULT 0
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS performance(
    perf_id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id INTEGER,
    rating INTEGER,
    remarks TEXT,
    date TEXT
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS leaves(
    leave_id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id INTEGER,
    leave_type TEXT,
    days INTEGER,
    date TEXT
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS attendance(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id INTEGER,
    date TEXT,
    status TEXT
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS payroll(
    payroll_id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id INTEGER,
    month TEXT,
    year INTEGER,
    basic REAL,
    hra REAL,
    allowances REAL,
    deductions REAL,
    net_pay REAL,
    generated_on TEXT
)
''')

conn.commit()

def hash_password(password: str) -> str:
    return pbkdf2_sha256.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    try:
        return pbkdf2_sha256.verify(password, hashed)
    except Exception:
        return False

def create_user(username, password, role='employee', emp_id=None):
    pw_hash = hash_password(password)
    try:
        cur.execute('INSERT INTO users(username, password_hash, role, emp_id) VALUES(?,?,?,?)',
                    (username, pw_hash, role, emp_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def authenticate(username, password):
    cur.execute('SELECT user_id, password_hash, role, emp_id FROM users WHERE username=?', (username,))
    row = cur.fetchone()
    if not row:
        return None
    user_id, pw_hash, role, emp_id = row
    if verify_password(password, pw_hash):
        return {'user_id': user_id, 'username': username, 'role': role, 'emp_id': emp_id}
    return None

def add_employee(name, dept, desig, basic_salary):
    cur.execute('INSERT INTO employees(name, department, designation, basic_salary) VALUES(?,?,?,?)',
                (name, dept, desig, basic_salary))
    conn.commit()
    return cur.lastrowid

def update_employee(emp_id, name, dept, desig, basic_salary):
    cur.execute('UPDATE employees SET name=?, department=?, designation=?, basic_salary=? WHERE emp_id=?',
                (name, dept, desig, basic_salary, emp_id))
    conn.commit()

def delete_employee(emp_id):
    cur.execute('DELETE FROM employees WHERE emp_id=?', (emp_id,))
    conn.commit()

def get_employees_df():
    return pd.read_sql_query('SELECT * FROM employees', conn)

def add_performance(emp_id, rating, remarks):
    cur.execute('INSERT INTO performance(emp_id, rating, remarks, date) VALUES(?,?,?,?)',
                (emp_id, rating, remarks, str(date.today())))
    conn.commit()

def add_leave(emp_id, leave_type, days):
    cur.execute('INSERT INTO leaves(emp_id, leave_type, days, date) VALUES(?,?,?,?)',
                (emp_id, leave_type, days, str(date.today())))
    conn.commit()

def add_attendance(emp_id, status):
    cur.execute('INSERT INTO attendance(emp_id, date, status) VALUES(?,?,?)',
                (emp_id, str(date.today()), status))
    conn.commit()

def generate_payroll(emp_id, month, year, basic, hra_pct=0.2, allowances=0, deductions=0):
    hra = basic * hra_pct
    gross = basic + hra + allowances
    net = gross - deductions
    generated_on = datetime.now().isoformat()
    cur.execute('''INSERT INTO payroll(emp_id, month, year, basic, hra, allowances, deductions, net_pay, generated_on)
                   VALUES(?,?,?,?,?,?,?,?,?)''',
                   (emp_id, month, year, basic, hra, allowances, deductions, net, generated_on))
    conn.commit()
    return cur.lastrowid

def get_payroll_df():
    return pd.read_sql_query('SELECT p.*, e.name FROM payroll p JOIN employees e ON p.emp_id = e.emp_id', conn)

def get_payroll_for_employee(emp_id):
    return pd.read_sql_query('SELECT * FROM payroll WHERE emp_id=? ORDER BY year DESC, month DESC', conn, params=(emp_id,))

class PayslipPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Company XYZ - Payslip', ln=True, align='C')
        self.ln(5)

    def employee_block(self, emp):
        self.set_font('Arial', '', 11)
        self.cell(40, 8, f'Employee ID: {emp.get("emp_id")}', ln=0)
        self.cell(0, 8, f'Name: {emp.get("name")}', ln=1)
        self.cell(40, 8, f'Department: {emp.get("department")}', ln=0)
        self.cell(0, 8, f'Designation: {emp.get("designation")}', ln=1)
        self.ln(3)

    def payroll_block(self, pay):
        self.set_font('Arial', '', 11)
        self.cell(40, 8, f'Month: {pay.get("month")} {pay.get("year")}', ln=1)
        self.cell(60, 8, f'Basic: {pay.get("basic")}', ln=1)
        self.cell(60, 8, f'HRA: {pay.get("hra")}', ln=1)
        self.cell(60, 8, f'Allowances: {pay.get("allowances")}', ln=1)
        self.cell(60, 8, f'Deductions: {pay.get("deductions")}', ln=1)
        self.set_font('Arial', 'B', 12)
        self.cell(60, 10, f'Net Pay: {pay.get("net_pay")}', ln=1)

def create_payslip_pdf(emp_row: dict, payroll_row: dict) -> bytes:
    pdf = PayslipPDF()
    pdf.add_page()
    pdf.employee_block(emp_row)
    pdf.payroll_block(payroll_row)
    pdf.set_y(-30)
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 10, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', align='C')
    return pdf.output(dest='S').encode('latin-1')

st.set_page_config(page_title='HR System', layout='wide')

if 'user' not in st.session_state:
    st.session_state.user = None

with st.sidebar:
    st.title('HR System')
    if st.session_state.user:
        st.write(f"Logged in as: {st.session_state.user['username']} ({st.session_state.user['role']})")
        if st.button('Logout'):
            st.session_state.user = None
            st.experimental_rerun()
    else:
        st.subheader('Login')
        username = st.text_input('Username')
        password = st.text_input('Password', type='password')
        if st.button('Login'):
            logged = authenticate(username, password)
            if logged:
                st.session_state.user = logged
                st.experimental_rerun()
            else:
                st.error('Invalid Login')

st.write("App Loaded Successfully!")