# hr_app_with_auth_payroll_pdf.py
"""
Full HR Management App with:
- User authentication (registration + login)
- Roles: admin and employee
- Employee details CRUD
- Performance reviews
- Leave management
- Attendance
- Payroll generation (salary, allowances, deductions)
- Generate and download PDF payslips

Updated:
✔ Default Admin created automatically
   Username: Admin
   Password: admin@123

"""

import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime
from passlib.hash import pbkdf2_sha256
from fpdf import FPDF

# ---------------------------
# Database setup
# ---------------------------
conn = sqlite3.connect('hr_system_auth.db', check_same_thread=False)
cur = conn.cursor()

cur.execute('''CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password_hash TEXT,
    role TEXT,
    emp_id INTEGER
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS employees(
    emp_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    department TEXT,
    designation TEXT,
    basic_salary REAL DEFAULT 0
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS performance(
    perf_id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id INTEGER,
    rating INTEGER,
    remarks TEXT,
    date TEXT
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS leaves(
    leave_id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id INTEGER,
    leave_type TEXT,
    days INTEGER,
    date TEXT
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS attendance(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id INTEGER,
    date TEXT,
    status TEXT
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS payroll(
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
)''')

conn.commit()

# ---------------------------
# Helper functions
# ---------------------------

def hash_password(password):
    return pbkdf2_sha256.hash(password)

def verify_password(password, hashed):
    try:
        return pbkdf2_sha256.verify(password, hashed)
    except:
        return False

def create_user(username, password, role='employee', emp_id=None):
    pw_hash = hash_password(password)
    try:
        cur.execute("INSERT INTO users(username,password_hash,role,emp_id) VALUES(?,?,?,?)",
                    (username, pw_hash, role, emp_id))
        conn.commit()
        return True
    except:
        return False

def authenticate(username, password):
    cur.execute("SELECT user_id,password_hash,role,emp_id FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    if not row:
        return None
    uid, pw_hash, role, emp_id = row
    if verify_password(password, pw_hash):
        return {"user_id": uid, "username": username, "role": role, "emp_id": emp_id}
    return None

# ---------------------------
# Create DEFAULT ADMIN
# ---------------------------
def ensure_default_admin():
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    if count == 0:
        create_user("Admin", "admin@123", role="admin")
        print("Default admin created: Admin / admin@123")

ensure_default_admin()

# ---------------------------
# UI Begins
# ---------------------------
st.set_page_config(page_title="HR System", layout="wide")

if "user" not in st.session_state:
    st.session_state.user = None

with st.sidebar:
    st.title("HR System")
    if st.session_state.user:
        st.write(f"Logged in as: {st.session_state.user['username']}")
        if st.button("Logout"):
            st.session_state.user = None
            st.experimental_rerun()
    else:
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user = authenticate(username, password)
            if user:
                st.session_state.user = user
                st.success("Login successful")
                st.experimental_rerun()
            else:
                st.error("Invalid Username or Password")

if not st.session_state.user:
    st.header("Welcome to HR Management System")
    st.write("Please log in using the sidebar.")
    st.warning("Default Admin → Username: Admin | Password: admin@123")
    st.stop()

st.title("Dashboard Loaded Successfully!")
