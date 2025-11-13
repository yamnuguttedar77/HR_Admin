# HR Management Streamlit App

This repository contains a Streamlit HR Management app with authentication, payroll and PDF payslip generation.

## Files
- `hr_app_with_auth_payroll_pdf.py` — the Streamlit app
- `requirements.txt` — Python dependencies
- `.streamlit/config.toml` — optional Streamlit server config

## Deploy to Streamlit Cloud (share.streamlit.io)

1. Create a new GitHub repository and push these files (or upload this repo as a new repo).
2. Go to https://share.streamlit.io and sign in with your GitHub account.
3. Click **'New app'** → select the repository, branch (usually `main`), and the file `hr_app_with_auth_payroll_pdf.py`.
4. Click **'Deploy'**. Streamlit Cloud will install dependencies from `requirements.txt` and launch the app.
5. (Optional) Add secrets (Settings → Secrets) if you need SMTP credentials or other private keys. Use `st.secrets` in the app to access them.

## Notes
- If your app uses local files or a database (SQLite), consider using an external database for production.
- To allow file downloads (PDF payslips) Streamlit Cloud supports that by default.

