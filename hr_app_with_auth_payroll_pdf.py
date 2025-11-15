# hr_app_with_auth_payroll_pdf.py
"""
HR Management App (Streamlit)
- Auth (admin/employee)
- Employees, Performance, Leaves, Attendance
- Payroll + PDF payslips (FPDF)
Default admin auto-created:
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
        # NOTE: avoid printing in Streamlit cloud logs if you prefer
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
        self.cell(40, 8, f'Employee ID: {emp.get(\"emp_id\")}', ln=0)
        self.cell(0, 8, f'Name: {emp.get(\"name\")}', ln=1)
        self.cell(40, 8, f'Department: {emp.get(\"department\")}', ln=0)
        self.cell(0, 8, f'Designation: {emp.get(\"designation\")}', ln=1)
        self.ln(3)
    def payroll_block(self, pay):
        self.set_font('Arial', '', 11)
        self.cell(40, 8, f'Month: {pay.get(\"month\")} {pay.get(\"year\")}', ln=1)
        self.cell(60, 8, f'Basic: {pay.get(\"basic\")}', ln=1)
        self.cell(60, 8, f'HRA: {pay.get(\"hra\")}', ln=1)
        self.cell(60, 8, f'Allowances: {pay.get(\"allowances\")}', ln=1)
        self.cell(60, 8, f'Deductions: {pay.get(\"deductions\")}', ln=1)
        self.set_font('Arial', 'B', 12)
        self.cell(60, 10, f'Net Pay: {pay.get(\"net_pay\")}', ln=1)

def create_payslip_pdf(emp_row: dict, payroll_row: dict) -> bytes:
    pdf = PayslipPDF()
    pdf.add_page()
    pdf.employee_block(emp_row)
    pdf.payroll_block(payroll_row)
    pdf.set_y(-30)
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 10, f'Generated on {datetime.now().strftime(\"%Y-%m-%d %H:%M:%S\")}', align='C')
    return pdf.output(dest='S').encode('latin-1')

# ---------------------------
# Safe rerun helper (works if st.experimental_rerun isn't available)
# ---------------------------
def safe_rerun():
    try:
        # preferred method
        st.experimental_rerun()
    except Exception:
        # fallback: mutate query params to force Streamlit to reload the page
        try:
            st.experimental_set_query_params(_r=str(datetime.now().timestamp()))
        except Exception:
            # last fallback: set a session_state toggle (may not always force rerun)
            st.session_state['_force_rerun'] = not st.session_state.get('_force_rerun', False)

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title='HR System', layout='wide')

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
        st.info('To create initial admin: default Admin user exists; create further users from Users menu.')
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

# (the rest of UI - same as before)
if choice == 'Dashboard':
    st.title('Dashboard')
    df_counts = {
        'Employees': pd.read_sql_query('SELECT COUNT(*) as c FROM employees', conn)['c'][0],
        'Leaves': pd.read_sql_query('SELECT COUNT(*) as c FROM leaves', conn)['c'][0],
        'Attendance': pd.read_sql_query('SELECT COUNT(*) as c FROM attendance', conn)['c'][0],
        'Payrolls': pd.read_sql_query('SELECT COUNT(*) as c FROM payroll', conn)['c'][0]
    }
    cols = st.columns(4)
    for i,(k,v) in enumerate(df_counts.items()):
        cols[i].metric(k, v)
    st.subheader('Recent payrolls')
    st.dataframe(get_payroll_df().sort_values(['year','month'], ascending=False).head(10))

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
        sel_username = st.selectbox('Select user to change password', users_df['username'].tolist())
        new_password = st.text_input('New password for selected user', type='password')
        if st.button('Change Password'):
            if new_password:
                update_user_password(sel_username, new_password)
                st.success(f"Password updated for user '{sel_username}'")
            else:
                st.error('Please enter a new password')

# End of app

