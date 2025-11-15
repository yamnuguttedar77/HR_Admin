# hr_app_with_auth_payroll_pdf.py
"""
HR Management App (Streamlit)
- Auth (admin/employee)
- Employees, Performance, Leaves, Attendance
- Payroll + PDF payslips (FPDF)

Default admin auto-created:
  Username: Admin
  Password: admin@123

This version: New Dashboard UI with colorful icon tiles similar to the provided image.
"""

import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
from datetime import date, datetime
from passlib.hash import pbkdf2_sha256
from fpdf import FPDF

# Try to import plotly; if not available, fall back to Streamlit charts
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except Exception:
    PLOTLY_AVAILABLE = False

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

# ---------------------------
# Helper functions
# ---------------------------
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
                   VALUES(?,?,?,?,?,?,?,?,?)''', (emp_id, month, year, basic, hra, allowances, deductions, net, generated_on))
    conn.commit()
    return cur.lastrowid

def get_payroll_df():
    return pd.read_sql_query('SELECT p.*, e.name FROM payroll p JOIN employees e ON p.emp_id = e.emp_id', conn)

def get_payroll_for_employee(emp_id):
    return pd.read_sql_query('SELECT * FROM payroll WHERE emp_id=? ORDER BY year DESC, month DESC', conn, params=(emp_id,))

def update_user_password(username, new_password):
    pw_hash = hash_password(new_password)
    cur.execute('UPDATE users SET password_hash=? WHERE username=?', (pw_hash, username))
    conn.commit()

# ---------------------------
# Create DEFAULT ADMIN (if none)
# ---------------------------
def ensure_default_admin():
    cur.execute('SELECT COUNT(*) FROM users')
    count = cur.fetchone()[0]
    if count == 0:
        create_user('Admin', 'admin@123', role='admin')
        print('Default admin created: Admin / admin@123')
ensure_default_admin()

# ---------------------------
# PDF generation (payslip)
# ---------------------------
class PayslipPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Company XYZ - Payslip', ln=True, align='C')
        self.ln(5)

    def employee_block(self, emp):
        self.set_font('Arial', '', 11)
        self.cell(40, 8, f"Employee ID: {emp.get('emp_id')}", ln=0)
        self.cell(0, 8, f"Name: {emp.get('name')}", ln=1)
        self.cell(40, 8, f"Department: {emp.get('department')}", ln=0)
        self.cell(0, 8, f"Designation: {emp.get('designation')}", ln=1)
        self.ln(3)

    def payroll_block(self, pay):
        self.set_font('Arial', '', 11)
        self.cell(40, 8, f"Month: {pay.get('month')} {pay.get('year')}", ln=1)
        self.cell(60, 8, f"Basic: {pay.get('basic')}", ln=1)
        self.cell(60, 8, f"HRA: {pay.get('hra')}", ln=1)
        self.cell(60, 8, f"Allowances: {pay.get('allowances')}", ln=1)
        self.cell(60, 8, f"Deductions: {pay.get('deductions')}", ln=1)
        self.set_font('Arial', 'B', 12)
        self.cell(60, 10, f"Net Pay: {pay.get('net_pay')}", ln=1)

def create_payslip_pdf(emp_row: dict, payroll_row: dict) -> bytes:
    pdf = PayslipPDF()
    pdf.add_page()
    pdf.employee_block(emp_row)
    pdf.payroll_block(payroll_row)
    pdf.set_y(-30)
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 10, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", align='C')
    return pdf.output(dest='S').encode('latin-1')

# ---------------------------
# Safe rerun helper
# ---------------------------
def safe_rerun():
    try:
        st.experimental_rerun()
    except Exception:
        try:
            st.experimental_set_query_params(_r=str(datetime.now().timestamp()))
        except Exception:
            st.session_state['_force_rerun'] = not st.session_state.get('_force_rerun', False)

# ---------------------------
# Streamlit UI + Styling
# ---------------------------
st.set_page_config(page_title='HR System', layout='wide')

# Dashboard CSS: colorful tiles, icons
st.markdown("""
    <style>
    /* overall dark background is controlled by Streamlit theme */
    .tile-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 18px; }
    .tile {
        background: linear-gradient(135deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
        border-radius: 12px;
        padding: 16px;
        min-height: 110px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.45);
        display:flex;
        flex-direction:column;
        justify-content:space-between;
    }
    .tile .icon {
        width:46px; height:46px; border-radius:10px; display:inline-flex; align-items:center; justify-content:center;
        font-size:22px; color:#fff;
    }
    .t-title { font-size:14px; color:#e6eef6; margin-top:6px; }
    .t-sub { font-size:20px; font-weight:700; color:#fff; margin-top:6px; }
    /* color variants */
    .bg-1{ background: linear-gradient(135deg,#6EE7B7,#34D399); }
    .bg-2{ background: linear-gradient(135deg,#A78BFA,#7C3AED); }
    .bg-3{ background: linear-gradient(135deg,#FDE68A,#F59E0B); }
    .bg-4{ background: linear-gradient(135deg,#FCA5A5,#EF4444); }
    .bg-5{ background: linear-gradient(135deg,#93C5FD,#3B82F6); }
    .bg-6{ background: linear-gradient(135deg,#FDBA74,#FB923C); }
    .small-muted{ color:#9aa6ae; font-size:12px; }
    </style>
""", unsafe_allow_html=True)

if 'user' not in st.session_state:
    st.session_state.user = None

# Sidebar auth UI
with st.sidebar:
    st.title('HR System')
    if st.session_state.user:
        st.write(f"Logged in as: {st.session_state.user['username']} ({st.session_state.user['role']})")
        if st.button('Logout'):
            st.session_state.user = None
            safe_rerun()
    else:
        st.subheader('Login')
        username = st.text_input('Username', key='login_user')
        password = st.text_input('Password', type='password', key='login_pass')
        if st.button('Login'):
            user = authenticate(username, password)
            if user:
                st.session_state.user = user
                st.success('Login successful')
                safe_rerun()
            else:
                st.error('Invalid credentials')

        st.markdown('---')
        st.subheader('Register (admin only)')
        st.info('Default Admin exists. Create further users from Users menu.')
        reg_user = st.text_input('New username', key='reg_user')
        reg_pass = st.text_input('New password', type='password', key='reg_pass')
        reg_role = st.selectbox('Role', ['admin', 'employee'], key='reg_role')
        if st.button('Register'):
            success = create_user(reg_user, reg_pass, reg_role)
            if success:
                st.success('User created. If employee, link emp_id via admin panel.')
            else:
                st.error('Username already exists')

if not st.session_state.user:
    st.header('Welcome to HR Management System')
    st.write('Please login from the left sidebar or register.')
    st.warning('Default Admin → Username: Admin | Password: admin@123')
    st.stop()

user = st.session_state.user

# Main menu
menu_options = ['Dashboard', 'Employees', 'Performance', 'Leaves', 'Attendance', 'Payroll', 'Users']
choice = st.sidebar.selectbox('Menu', menu_options)

# ---------- New Tile-based Dashboard ----------
if choice == 'Dashboard':
    st.title("Dashboard")
    # fetch counts
    emp_count = pd.read_sql_query('SELECT COUNT(*) as c FROM employees', conn)['c'][0]
    leave_count = pd.read_sql_query('SELECT COUNT(*) as c FROM leaves', conn)['c'][0]
    attend_count = pd.read_sql_query('SELECT COUNT(*) as c FROM attendance', conn)['c'][0]
    payroll_count = pd.read_sql_query('SELECT COUNT(*) as c FROM payroll', conn)['c'][0]

    # tiles data: (icon emoji, title, count/value, color class)
    tiles = [
        ("📝","Requests & Tasks","","bg-1"),
        ("👥","Employees", str(emp_count),"bg-2"),
        ("💬","Vibe","","bg-3"),
        ("💸","Reimbursement","","bg-4"),
        ("💰","Compensation","","bg-5"),
        ("📋","Attendance", str(attend_count),"bg-6"),
        ("🏖️","Leave", str(leave_count),"bg-1"),
        ("📂","HR Documents","","bg-2"),
        ("🔍","Recruitment","","bg-3"),
        ("📅","Calendar","","bg-4"),
        ("📈","Performance","","bg-5"),
        ("📁","Project","","bg-6"),
        ("🛎️","Helpdesk","","bg-1"),
        ("✈️","Travel","","bg-2"),
        ("🏆","Recognition","","bg-3"),
        ("⏱️","Time Sheets","","bg-4"),
        ("📊","Reports","","bg-5"),
        ("🧾","Reports Builder","","bg-6"),
    ]

    # render tiles in responsive grid
    st.markdown('<div class="tile-grid">', unsafe_allow_html=True)
    for icon, title, val, css in tiles:
        # show actionable counts for those we have values for
        value_html = f'<div class="t-sub">{val}</div>' if val else ''
        # create tile
        tile_html = f'''
            <div class="tile">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div style="display:flex;gap:12px;align-items:center;">
                        <div class="icon {css}" style="box-shadow: 0 6px 14px rgba(0,0,0,0.35);">
                            {icon}
                        </div>
                        <div>
                            <div class="t-title">{title}</div>
                            <div class="small-muted">{ "" if val=="" else "Total / Recent" }</div>
                        </div>
                    </div>
                    <div style="text-align:right;">
                        {value_html}
                    </div>
                </div>
            </div>
        '''
        st.markdown(tile_html, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    # optionally add a small charts row below for quick insights
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Headcount by Department")
        emp_df = get_employees_df()
        if not emp_df.empty:
            dept_counts = emp_df.groupby('department')['emp_id'].count().reset_index().rename(columns={'emp_id':'count'})
            if PLOTLY_AVAILABLE:
                fig = px.bar(dept_counts, x='department', y='count', text='count', height=320)
                fig.update_layout(margin=dict(l=10,r=10,t=40,b=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.bar_chart(dept_counts.set_index('department')['count'])
        else:
            st.info("No employees yet — add employees from Employees menu.")

    with col2:
        st.subheader("Payrolls / Recent")
        payroll_df = get_payroll_df()
        if not payroll_df.empty:
            payroll_df['generated_on_dt'] = pd.to_datetime(payroll_df['generated_on'], errors='coerce')
            recent = payroll_df.sort_values('generated_on_dt', ascending=False).head(8)
            if PLOTLY_AVAILABLE:
                fig2 = px.line(recent, x='generated_on_dt', y='net_pay', markers=True, height=320)
                fig2.update_layout(margin=dict(l=10,r=10,t=40,b=10))
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.line_chart(recent.set_index('generated_on_dt')['net_pay'])
        else:
            st.info("No payrolls yet — generate payrolls from Payroll menu.")

    st.caption("Dashboard: click menu items on the left to manage Employees, Payroll, Attendance, etc.")

# --- Employees ---
elif choice == 'Employees':
    st.title('Employees')
    if user['role'] == 'admin':
        with st.expander('Add Employee'):
            name = st.text_input('Name', key='e_name')
            dept = st.text_input('Department', key='e_dept')
            desig = st.text_input('Designation', key='e_desig')
            basic = st.number_input('Basic Salary', min_value=0.0, key='e_basic')
            if st.button('Add Employee', key='add_emp'):
                new_id = add_employee(name, dept, desig, basic)
                st.success(f'Added employee with ID {new_id}')
        df = get_employees_df()
        st.dataframe(df)
        st.subheader('Update or Delete Employee')
        if not df.empty:
            sel = st.selectbox('Select Employee', df['emp_id'].tolist())
            row = df[df['emp_id'] == sel].iloc[0]
            u_name = st.text_input('Name', value=row['name'], key='u_name')
            u_dept = st.text_input('Department', value=row['department'], key='u_dept')
            u_desig = st.text_input('Designation', value=row['designation'], key='u_desig')
            u_basic = st.number_input('Basic Salary', value=float(row['basic_salary']), key='u_basic')
            if st.button('Update Employee'):
                update_employee(sel, u_name, u_dept, u_desig, u_basic)
                st.success('Updated')
            if st.button('Delete Employee'):
                delete_employee(sel)
                st.success('Deleted')
    else:
        st.subheader('My Profile')
        emp_id = user.get('emp_id')
        if not emp_id:
            st.info('No employee profile linked to your user. Contact admin.')
        else:
            df = get_employees_df()
            row = df[df['emp_id'] == emp_id]
            if row.empty:
                st.error('Employee record not found')
            else:
                st.table(row.T)

# --- Performance ---
elif choice == 'Performance':
    st.title('Performance Reviews')
    if user['role'] == 'admin':
        df_emp = get_employees_df()
        emp_choice = st.selectbox('Employee', df_emp['emp_id'].tolist())
        rating = st.slider('Rating', 1, 5, 3)
        remarks = st.text_area('Remarks')
        if st.button('Submit Review'):
            add_performance(emp_choice, rating, remarks)
            st.success('Review submitted')
        st.subheader('All Reviews')
        st.dataframe(pd.read_sql_query('SELECT p.*, e.name FROM performance p JOIN employees e ON p.emp_id=e.emp_id', conn))
    else:
        emp_id = user.get('emp_id')
        if not emp_id:
            st.info('No linked employee id')
        else:
            st.dataframe(pd.read_sql_query('SELECT * FROM performance WHERE emp_id=?', conn, params=(emp_id,)))

# --- Leaves ---
elif choice == 'Leaves':
    st.title('Leaves')
    df_emp = get_employees_df()
    emp_choice = st.selectbox('Employee', df_emp['emp_id'].tolist()) if user['role']=='admin' else user.get('emp_id')
    leave_type = st.selectbox('Leave Type', ['Sick', 'Casual', 'Earned'])
    days = st.number_input('Days', min_value=1, value=1)
    if st.button('Apply/Record Leave'):
        add_leave(emp_choice, leave_type, days)
        st.success('Leave recorded')
    st.subheader('All Leaves')
    st.dataframe(pd.read_sql_query('SELECT l.*, e.name FROM leaves l JOIN employees e ON l.emp_id=e.emp_id', conn))

# --- Attendance ---
elif choice == 'Attendance':
    st.title('Attendance')
    df_emp = get_employees_df()
    emp_choice = st.selectbox('Employee', df_emp['emp_id'].tolist()) if user['role']=='admin' else user.get('emp_id')
    status = st.radio('Status', ['Present', 'Absent'])
    if st.button('Mark Attendance'):
        add_attendance(emp_choice, status)
        st.success('Attendance marked')
    st.subheader('Attendance Records')
    st.dataframe(pd.read_sql_query('SELECT a.*, e.name FROM attendance a JOIN employees e ON a.emp_id=e.emp_id', conn))

# --- Payroll ---
elif choice == 'Payroll':
    st.title('Payroll')
    df_emp = get_employees_df()
    if user['role']=='admin':
        emp_choice = st.selectbox('Employee', df_emp['emp_id'].tolist())
        month = st.selectbox('Month', ['January','February','March','April','May','June','July','August','September','October','November','December'])
        year = st.number_input('Year', min_value=2000, max_value=2100, value=date.today().year)
        basic = st.number_input('Basic Salary', min_value=0.0)
        hra_pct = st.slider('HRA % of Basic', 0.0, 0.5, 0.2)
        allowances = st.number_input('Allowances', min_value=0.0)
        deductions = st.number_input('Deductions', min_value=0.0)
        if st.button('Generate Payroll'):
            pid = generate_payroll(emp_choice, month, int(year), basic, hra_pct, allowances, deductions)
            st.success(f'Payroll generated with id {pid}')
        st.subheader('Payroll Records')
        st.dataframe(get_payroll_df())
        st.subheader('Download Payslip (select payroll)')
        payroll_df = get_payroll_df()
        if not payroll_df.empty:
            sel = st.selectbox('Select payroll id', payroll_df['payroll_id'].tolist())
            pay_row = payroll_df[payroll_df['payroll_id'] == sel].iloc[0].to_dict()
            emp_row = pd.read_sql_query('SELECT * FROM employees WHERE emp_id=?', conn, params=(pay_row['emp_id'],)).iloc[0].to_dict()
            pdf_bytes = create_payslip_pdf(emp_row, pay_row)
            st.download_button('Download Payslip PDF', data=pdf_bytes, file_name=f"payslip_{pay_row['emp_id']}_{pay_row['month']}_{pay_row['year']}.pdf", mime='application/pdf')
    else:
        emp_id = user.get('emp_id')
        if not emp_id:
            st.info('No linked employee id')
        else:
            st.subheader('My Payrolls')
            df = get_payroll_for_employee(emp_id)
            st.dataframe(df)
            if not df.empty:
                sel_row = st.selectbox('Select payroll', df['payroll_id'].tolist())
                pr = df[df['payroll_id']==sel_row].iloc[0].to_dict()
                emp_row = pd.read_sql_query('SELECT * FROM employees WHERE emp_id=?', conn, params=(emp_id,)).iloc[0].to_dict()
                pdf_bytes = create_payslip_pdf(emp_row, pr)
                st.download_button('Download Payslip PDF', data=pdf_bytes, file_name=f"payslip_{emp_id}_{pr['month']}_{pr['year']}.pdf", mime='application/pdf')

# --- Users / Admin ---
elif choice == 'Users':
    if user['role'] != 'admin':
        st.error('Only admin can manage users')
    else:
        st.title('User Management')
        st.subheader('Create user linked to employee')
        df_emp = get_employees_df()
        if not df_emp.empty:
            emp_choice = st.selectbox('Employee (link user)', df_emp['emp_id'].tolist())
            new_user = st.text_input('Username for employee')
            new_pass = st.text_input('Password', type='password')
            if st.button('Create User for Employee'):
                ok = create_user(new_user, new_pass, 'employee', emp_choice)
                if ok:
                    st.success('User created and linked')
                else:
                    st.error('Could not create user (username might exist)')
        else:
            st.info('Add employees first')

        st.subheader('All Users')
        users_df = pd.read_sql_query('SELECT u.user_id, u.username, u.role, u.emp_id, e.name FROM users u LEFT JOIN employees e ON u.emp_id=e.emp_id', conn)
        st.dataframe(users_df)

        st.subheader('Change user password')
        sel_username = st.selectbox('Select user to change password', users_df['username'].tolist() if not users_df.empty else [])
        new_password = st.text_input('New password for selected user', type='password')
        if st.button('Change Password'):
            if new_password and sel_username:
                update_user_password(sel_username, new_password)
                st.success(f"Password updated for user '{sel_username}'")
            else:
                st.error('Please select a user and enter a new password')

# End of app
