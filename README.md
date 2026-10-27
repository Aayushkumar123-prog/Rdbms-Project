# Campus Lost & Found — RDBMS Project

A working student-facing lost-and-found portal with a FastAPI backend, MySQL database, and responsive HTML/CSS/JavaScript frontend. Designed for a 20-mark RDBMS project and viva.

## Features
- Student registration/login with PBKDF2 password hashing and cookie sessions
- Lost/found report creation, category/location filters, keyword search
- Automatic candidate matching by category, location, date, and item-name keywords
- Student ownership claims with duplicate-pending-claim prevention
- Admin claim review (approve/reject with reason)
- Transactional handover workflow; prevents duplicate handovers
- Notifications, dispute records, admin overview, audit log
- SQL schema includes PK/FK, UNIQUE, CHECK, indexes, normalized lookup tables, reporting views, a stored procedure, and a trigger-maintained claim history
- Admin overview analytics, complex joins, aggregates, and API health check

## Requirements
- Python 3.10+
- MySQL Server 8.x (MySQL Workbench alone is only the GUI; the MySQL Server service must also be installed and running)
- VS Code or another editor

## Setup on Windows
1. Install and start **MySQL Server 8.x**. MySQL Workbench is useful for running SQL but is not the database server itself.
2. Open MySQL Workbench, connect to your local server, open `database/schema.sql`, and execute the entire script.
3. Copy `.env.example` to `.env`. Update `DB_PASSWORD` to the password for your local MySQL `root` user. Keep `DB_NAME=campus_lost_found`.
4. Open a terminal in this project folder and run:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python -m pip install python-dotenv
   ```
5. Start the app:
   ```powershell
   python -m uvicorn app:app --reload
   ```
6. Visit http://127.0.0.1:8000
7. Check database connection at http://127.0.0.1:8000/health

If PowerShell blocks activation, use `\.venv\Scripts\python.exe -m pip install -r requirements.txt` and `\.venv\Scripts\python.exe -m pip install python-dotenv`, then start with `\.venv\Scripts\python.exe -m uvicorn app:app --reload`.

## Create an admin account
For safety, public registration always creates a student account. After registering a normal account, promote it to admin using MySQL Workbench:

```sql
USE campus_lost_found;
UPDATE users SET role='admin' WHERE email='your_registered_email@campus.edu';
```

Log out and log back in so the session refreshes. Do not expose admin credentials in a public repo.

## Demo flow
1. Register Student A and create a found report.
2. Register Student B and submit a claim on the found report.
3. Promote a separate account to admin in Workbench and sign in as admin.
4. Open **Review claims**, approve/reject with a reason, then record a handover for an approved claim.
5. Check notifications, report statuses, `claims`, `claim_history`, `handovers`, and `audit_logs` in Workbench.

## Frontend and video
- The landing and sign-in pages use locally bundled, muted looping campus footage. The report-to-return captions respond to report actions and scroll position.
- The first homepage visit in a tab has a short Lottie opening animation, with a reduced-motion path.
- The sign-in page offers an opt-in request for the browser password manager. The app does not store the password in local storage.
- Campus video and animation sources and licenses are listed in `static/ASSET_CREDITS.md`.

## Advanced SQL demonstrations
```sql
SELECT * FROM v_open_reports;
SELECT * FROM v_pending_claims;
SELECT * FROM v_recovery_summary;
CALL sp_report_counts_by_category();
```
`trg_claim_status_history` automatically adds a row to `claim_history` when a claim status changes, inside the same database transaction.

## Important notes
- This is a college/demo project, not a hardened production deployment. Before real campus deployment, use HTTPS, a strong `SESSION_SECRET`, restricted CORS, secure cookie settings, rate limiting, university email verification, image upload/storage controls, and privacy review.
- Matching is a transparent heuristic, not machine learning. It suggests candidates; humans must verify ownership.
- Do not put passwords or real private student information in GitHub. Use fictional sample data for evaluation.

## Suggested viva SQL
```sql
-- 1. Count reports by category
SELECT c.category_name, COUNT(*) AS report_count
FROM item_reports r JOIN categories c ON c.category_id=r.category_id
GROUP BY c.category_name ORDER BY report_count DESC;

-- 2. Pending claims with report and claimant
SELECT cl.claim_id, r.item_name, u.full_name, cl.status, cl.created_at
FROM claims cl JOIN item_reports r ON r.report_id=cl.report_id
JOIN users u ON u.user_id=cl.claimant_id
WHERE cl.status='pending';

-- 3. Locations with the most reports
SELECT l.location_name, COUNT(*) AS total_reports
FROM item_reports r JOIN locations l ON l.location_id=r.location_id
GROUP BY l.location_id,l.location_name
HAVING COUNT(*) > 0 ORDER BY total_reports DESC;

-- 4. Successful recoveries by category
SELECT c.category_name, COUNT(h.handover_id) AS recovered
FROM categories c
LEFT JOIN item_reports r ON r.category_id=c.category_id
LEFT JOIN handovers h ON h.report_id=r.report_id
GROUP BY c.category_id,c.category_name ORDER BY recovered DESC;

-- 5. Audit history
SELECT action, entity_type, entity_id, details, created_at
FROM audit_logs ORDER BY created_at DESC;
```


## Verification status
- Python syntax compilation passed.
- Frontend JavaScript syntax check passed.
- The homepage, `/login`, bundled video clips, Lottie animation, and frontend scripts were verified through the running local server.
- If the database check returns 503, verify the local `.env` credentials and import `database/schema.sql` to enable sign-in and report workflows.
