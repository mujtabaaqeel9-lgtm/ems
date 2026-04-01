# EMS v2 — Render Deployment Guide

## Step 1: GitHub Par Upload Karo

1. GitHub.com par jao → New Repository banao → name: "ems"
2. VS Code terminal mein:
```
git init
git add .
git commit -m "EMS v2 initial"
git remote add origin https://github.com/YOURUSERNAME/ems.git
git push -u origin main
```

---

## Step 2: MySQL Cloud Database (FreeSQLDatabase.com)

1. https://www.freesqldatabase.com par jao
2. Free account banao
3. Database create karo — credentials save karo:
   - Host
   - Database name
   - Username
   - Password
4. PhpMyAdmin se database.sql import karo

---

## Step 3: Render Par Deploy

1. https://render.com par jao → Free account banao
2. "New Web Service" click karo
3. GitHub repo connect karo
4. Settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
5. Environment Variables add karo:
   - DB_HOST = (freesqldatabase host)
   - DB_USER = (your db username)
   - DB_PASSWORD = (your db password)
   - DB_NAME = (your db name)
6. "Deploy" click karo!

---

## Local Mein Run (v2)

```
pip install -r requirements.txt
python app.py
```
Then open: http://localhost:5000

---

## New Features in v2:

✅ Professional Blue & White Theme
✅ Attendance Tracking (daily mark karo)
✅ Monthly Attendance Log
✅ Payroll Generation (auto calculate)
✅ Salary Slip / Payslip (printable)
✅ Mark as Paid
✅ Employee Reports + CSV Export
✅ Attendance Reports + CSV Export
✅ Present Today counter on dashboard
