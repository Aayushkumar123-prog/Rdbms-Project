import os
import json
import secrets
import hashlib
import hmac
from datetime import date, datetime
from typing import Optional

import mysql.connector
from mysql.connector import pooling, Error
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="Campus Lost & Found", version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "change-this-session-secret-before-deployment"))
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "campus_lost_found"),
    "autocommit": False,
}
pool = None

def get_pool():
    global pool
    if pool is None:
        try:
            pool = pooling.MySQLConnectionPool(pool_name="campus_pool", pool_size=5, **DB_CONFIG)
        except Error as e:
            raise HTTPException(status_code=503, detail="Cannot connect to MySQL. Check .env and run database/schema.sql. Details: " + str(e))
    return pool

def query(sql, params=(), fetch="all", conn=None):
    own = conn is None
    c = get_pool().get_connection() if own else conn
    cur = c.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        result = cur.fetchall() if fetch == "all" else (cur.fetchone() if fetch == "one" else cur.lastrowid)
        if own:
            c.commit()
        return result
    except Exception:
        if own:
            c.rollback()
        raise
    finally:
        cur.close()
        if own:
            c.close()

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180000)
    return salt.hex() + "$" + digest.hex()

def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 180000)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False

def current_user(request: Request):
    uid = request.session.get("user_id")
    if not uid:
        return None
    return query("SELECT user_id, full_name, email, role FROM users WHERE user_id=%s", (uid,), "one")

def require_user(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Please log in first.")
    return user

def require_admin(request: Request):
    user = require_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user

def audit(actor_id, action, entity_type, entity_id=None, details=None, conn=None):
    query("INSERT INTO audit_logs(actor_id,action,entity_type,entity_id,details) VALUES(%s,%s,%s,%s,%s)",
          (actor_id, action, entity_type, entity_id, json.dumps(details or {})), "id", conn)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    with open("static/index.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/login", response_class=HTMLResponse)
def login_page():
    with open("static/login.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/api/me")
def me(request: Request):
    return {"user": current_user(request)}

@app.post("/api/register")
def register(request: Request, full_name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    full_name, email = full_name.strip(), email.strip().lower()
    if len(full_name) < 2 or "@" not in email or len(password) < 8:
        raise HTTPException(400, "Enter a name, valid email, and password with at least 8 characters.")
    try:
        uid = query("INSERT INTO users(full_name,email,password_hash) VALUES(%s,%s,%s)",
                    (full_name, email, hash_password(password)), "id")
        request.session["user_id"] = uid
        return {"ok": True, "message": "Account created.", "user": current_user(request)}
    except mysql.connector.IntegrityError:
        raise HTTPException(409, "An account with this email already exists.")

@app.post("/api/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = query("SELECT * FROM users WHERE email=%s", (email.strip().lower(),), "one")
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "Incorrect email or password.")
    request.session.clear()
    request.session["user_id"] = user["user_id"]
    return {"ok": True, "user": {"user_id": user["user_id"], "full_name": user["full_name"], "email": user["email"], "role": user["role"]}}

@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}

@app.get("/api/meta")
def meta():
    return {
        "categories": query("SELECT category_id, category_name FROM categories ORDER BY category_name"),
        "locations": query("SELECT location_id, location_name, building FROM locations ORDER BY location_name")
    }

@app.get("/api/reports")
def reports(report_type: Optional[str] = None, category_id: Optional[int] = None,
            location_id: Optional[int] = None, q: Optional[str] = None, status: Optional[str] = None):
    sql = """SELECT r.report_id,r.report_type,r.item_name,r.description,r.event_date,r.contact_note,
             r.image_url,r.status,r.created_at,u.full_name AS reporter,c.category_name,l.location_name,
             r.category_id,r.location_id
             FROM item_reports r JOIN users u ON u.user_id=r.reporter_id
             JOIN categories c ON c.category_id=r.category_id JOIN locations l ON l.location_id=r.location_id
             WHERE 1=1"""
    params = []
    if report_type in ("lost", "found"):
        sql += " AND r.report_type=%s"; params.append(report_type)
    if category_id:
        sql += " AND r.category_id=%s"; params.append(category_id)
    if location_id:
        sql += " AND r.location_id=%s"; params.append(location_id)
    if status in ("open", "matched", "claimed", "returned", "closed"):
        sql += " AND r.status=%s"; params.append(status)
    if q:
        sql += " AND (r.item_name LIKE %s OR r.description LIKE %s)"
        params.extend([f"%{q.strip()}%", f"%{q.strip()}%"])
    sql += " ORDER BY r.created_at DESC LIMIT 200"
    return {"reports": query(sql, tuple(params))}

@app.post("/api/reports")
def create_report(request: Request, report_type: str = Form(...), item_name: str = Form(...),
                  description: str = Form(...), category_id: int = Form(...), location_id: int = Form(...),
                  event_date: date = Form(...), contact_note: str = Form(""), image_url: str = Form("")):
    user = require_user(request)
    if report_type not in ("lost", "found"):
        raise HTTPException(400, "Report type must be lost or found.")
    if len(item_name.strip()) < 2 or len(description.strip()) < 5:
        raise HTTPException(400, "Enter an item name and a more detailed description.")
    if event_date > date.today():
        raise HTTPException(400, "The event date cannot be in the future.")
    if not query("SELECT category_id FROM categories WHERE category_id=%s", (category_id,), "one"):
        raise HTTPException(400, "Invalid category.")
    if not query("SELECT location_id FROM locations WHERE location_id=%s", (location_id,), "one"):
        raise HTTPException(400, "Invalid location.")
    rid = query("""INSERT INTO item_reports(reporter_id,category_id,location_id,report_type,item_name,
                 description,event_date,contact_note,image_url) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (user["user_id"], category_id, location_id, report_type, item_name.strip(),
                 description.strip(), event_date, contact_note.strip() or None, image_url.strip() or None), "id")
    audit(user["user_id"], "REPORT_CREATED", "item_report", rid, {"report_type": report_type})
    generate_matches(rid, user["user_id"])
    return {"ok": True, "report_id": rid, "message": "Report submitted. Potential matches have been checked."}

def generate_matches(report_id, actor_id):
    report = query("SELECT * FROM item_reports WHERE report_id=%s", (report_id,), "one")
    if not report:
        return
    other_type = "found" if report["report_type"] == "lost" else "lost"
    candidates = query("""SELECT * FROM item_reports WHERE report_type=%s AND status IN ('open','matched')
                       AND category_id=%s AND report_id<>%s
                       AND ABS(DATEDIFF(event_date,%s))<=30 ORDER BY created_at DESC LIMIT 100""",
                       (other_type, report["category_id"], report_id, report["event_date"]))
    for candidate in candidates:
        score = 45
        reasons = ["same category"]
        if candidate["location_id"] == report["location_id"]:
            score += 30; reasons.append("same location")
        days = abs((candidate["event_date"] - report["event_date"]).days)
        if days <= 2:
            score += 20; reasons.append("dates within 2 days")
        elif days <= 7:
            score += 12; reasons.append("dates within 7 days")
        a = set(report["item_name"].lower().split())
        b = set(candidate["item_name"].lower().split())
        overlap = a.intersection(b)
        if overlap:
            score = min(100, score + min(10, 5 * len(overlap)))
            reasons.append("shared keywords: " + ", ".join(sorted(overlap)))
        lost_id = report_id if report["report_type"] == "lost" else candidate["report_id"]
        found_id = report_id if report["report_type"] == "found" else candidate["report_id"]
        query("""INSERT IGNORE INTO matches(lost_report_id,found_report_id,match_score,match_reason)
                 VALUES(%s,%s,%s,%s)""", (lost_id, found_id, min(score,100), "; ".join(reasons)), "id")
        if score >= 65:
            query("UPDATE item_reports SET status='matched' WHERE report_id IN (%s,%s) AND status='open'",
                  (lost_id, found_id), "none")

@app.get("/api/matches")
def get_matches(request: Request):
    user = require_user(request)
    return {"matches": query("""SELECT m.match_id,m.match_score,m.match_reason,m.status,
        l.report_id AS lost_report_id,l.item_name AS lost_item,l.event_date AS lost_date,
        fl.report_id AS found_report_id,fl.item_name AS found_item,fl.event_date AS found_date,
        ll.location_name AS lost_location, lf.location_name AS found_location
        FROM matches m JOIN item_reports l ON l.report_id=m.lost_report_id
        JOIN item_reports fl ON fl.report_id=m.found_report_id
        JOIN locations ll ON ll.location_id=l.location_id
        JOIN locations lf ON lf.location_id=fl.location_id
        WHERE (l.reporter_id=%s OR fl.reporter_id=%s OR %s='admin')
        ORDER BY m.match_score DESC,m.created_at DESC LIMIT 100""",
        (user["user_id"], user["user_id"], user["role"]))}

@app.post("/api/claims")
def create_claim(request: Request, report_id: int = Form(...), ownership_details: str = Form(...),
                 evidence_note: str = Form("")):
    user = require_user(request)
    report = query("SELECT * FROM item_reports WHERE report_id=%s", (report_id,), "one")
    if not report or report["report_type"] != "found" or report["status"] in ("returned", "closed"):
        raise HTTPException(400, "Claims can only be made on active found-item reports.")
    if report["reporter_id"] == user["user_id"]:
        raise HTTPException(400, "You cannot claim an item you reported as found.")
    if len(ownership_details.strip()) < 8:
        raise HTTPException(400, "Describe specific details proving ownership.")
    existing = query("SELECT claim_id FROM claims WHERE report_id=%s AND claimant_id=%s AND status='pending'",
                     (report_id, user["user_id"]), "one")
    if existing:
        raise HTTPException(409, "You already have a pending claim for this report.")
    cid = query("""INSERT INTO claims(report_id,claimant_id,ownership_details,evidence_note)
                   VALUES(%s,%s,%s,%s)""",
                (report_id, user["user_id"], ownership_details.strip(), evidence_note.strip() or None), "id")
    audit(user["user_id"], "CLAIM_SUBMITTED", "claim", cid, {"report_id": report_id})
    query("INSERT INTO notifications(user_id,title,message) VALUES(%s,%s,%s)",
          (report["reporter_id"], "New ownership claim", f"A student has submitted a claim for report #{report_id}."))
    return {"ok": True, "claim_id": cid, "message": "Claim submitted for admin review."}

@app.get("/api/claims")
def list_claims(request: Request):
    user = require_user(request)
    if user["role"] == "admin":
        sql = """SELECT c.*,r.item_name,r.report_id,u.full_name AS claimant_name,u.email AS claimant_email
                 FROM claims c JOIN item_reports r ON r.report_id=c.report_id
                 JOIN users u ON u.user_id=c.claimant_id ORDER BY c.created_at DESC"""
        return {"claims": query(sql)}
    return {"claims": query("""SELECT c.claim_id,c.report_id,c.ownership_details,c.evidence_note,c.status,
              c.review_reason,c.created_at,r.item_name FROM claims c JOIN item_reports r ON r.report_id=c.report_id
              WHERE c.claimant_id=%s ORDER BY c.created_at DESC""", (user["user_id"],))}

@app.post("/api/claims/{claim_id}/review")
def review_claim(claim_id: int, request: Request, status: str = Form(...), reason: str = Form(...)):
    admin = require_admin(request)
    if status not in ("approved", "rejected"):
        raise HTTPException(400, "Status must be approved or rejected.")
    conn = get_pool().get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM claims WHERE claim_id=%s FOR UPDATE", (claim_id,))
        claim = cur.fetchone()
        if not claim:
            raise HTTPException(404, "Claim not found.")
        if claim["status"] != "pending":
            raise HTTPException(409, "Only pending claims can be reviewed.")
        cur.execute("SELECT * FROM item_reports WHERE report_id=%s FOR UPDATE", (claim["report_id"],))
        report = cur.fetchone()
        if status == "approved" and report["status"] == "returned":
            raise HTTPException(409, "This item has already been returned.")
        cur.execute("""UPDATE claims SET status=%s,reviewed_by=%s,review_reason=%s,reviewed_at=NOW()
                       WHERE claim_id=%s""", (status, admin["user_id"], reason.strip(), claim_id))
        if status == "approved":
            cur.execute("UPDATE item_reports SET status='claimed' WHERE report_id=%s", (claim["report_id"],))
        cur.execute("INSERT INTO notifications(user_id,title,message) VALUES(%s,%s,%s)",
                    (claim["claimant_id"], "Claim " + status, "Your claim for report #" + str(claim["report_id"]) + " was " + status + "."))
        cur.execute("""INSERT INTO audit_logs(actor_id,action,entity_type,entity_id,details)
                       VALUES(%s,%s,%s,%s,%s)""",
                    (admin["user_id"], "CLAIM_" + status.upper(), "claim", claim_id,
                     json.dumps({"reason": reason.strip()})))
        conn.commit()
        return {"ok": True, "message": f"Claim {status}."}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, "Could not review claim: " + str(e))
    finally:
        cur.close()
        conn.close()

@app.post("/api/handovers")
def create_handover(request: Request, claim_id: int = Form(...), handover_note: str = Form("")):
    admin = require_admin(request)
    conn = get_pool().get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM claims WHERE claim_id=%s FOR UPDATE", (claim_id,))
        claim = cur.fetchone()
        if not claim or claim["status"] != "approved":
            raise HTTPException(400, "Only approved claims can be handed over.")
        cur.execute("SELECT * FROM item_reports WHERE report_id=%s FOR UPDATE", (claim["report_id"],))
        report = cur.fetchone()
        if report["status"] == "returned":
            raise HTTPException(409, "This item has already been handed over.")
        cur.execute("""INSERT INTO handovers(report_id,claim_id,handed_over_by,received_by,handover_note)
                       VALUES(%s,%s,%s,%s,%s)""",
                    (claim["report_id"], claim_id, admin["user_id"], claim["claimant_id"], handover_note.strip() or None))
        cur.execute("UPDATE item_reports SET status='returned' WHERE report_id=%s", (claim["report_id"],))
        cur.execute("INSERT INTO notifications(user_id,title,message) VALUES(%s,%s,%s)",
                    (claim["claimant_id"], "Item handover recorded", "The handover for report #" + str(claim["report_id"]) + " has been recorded."))
        cur.execute("""INSERT INTO audit_logs(actor_id,action,entity_type,entity_id,details)
                       VALUES(%s,'ITEM_HANDED_OVER','item_report',%s,%s)""",
                    (admin["user_id"], claim["report_id"], json.dumps({"claim_id": claim_id})))
        conn.commit()
        return {"ok": True, "message": "Handover recorded and item marked returned."}
    except HTTPException:
        conn.rollback()
        raise
    except mysql.connector.IntegrityError:
        conn.rollback()
        raise HTTPException(409, "A handover already exists for this report or claim.")
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, "Handover failed: " + str(e))
    finally:
        cur.close()
        conn.close()

@app.get("/api/notifications")
def notifications(request: Request):
    user = require_user(request)
    return {"notifications": query("""SELECT notification_id,title,message,is_read,created_at
        FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 50""", (user["user_id"],))}

@app.post("/api/notifications/{notification_id}/read")
def read_notification(notification_id: int, request: Request):
    user = require_user(request)
    query("UPDATE notifications SET is_read=TRUE WHERE notification_id=%s AND user_id=%s",
          (notification_id, user["user_id"]), "none")
    return {"ok": True}

@app.post("/api/disputes")
def open_dispute(request: Request, report_id: int = Form(...), description: str = Form(...)):
    user = require_user(request)
    if len(description.strip()) < 10:
        raise HTTPException(400, "Please describe the dispute in at least 10 characters.")
    if not query("SELECT report_id FROM item_reports WHERE report_id=%s", (report_id,), "one"):
        raise HTTPException(404, "Report not found.")
    did = query("INSERT INTO disputes(report_id,opened_by,description) VALUES(%s,%s,%s)",
                (report_id, user["user_id"], description.strip()), "id")
    audit(user["user_id"], "DISPUTE_OPENED", "dispute", did)
    return {"ok": True, "dispute_id": did}

@app.get("/api/admin/overview")
def admin_overview(request: Request):
    require_admin(request)
    return {
      "counts": query("""SELECT
        (SELECT COUNT(*) FROM item_reports WHERE report_type='lost' AND status NOT IN ('returned','closed')) AS open_lost,
        (SELECT COUNT(*) FROM item_reports WHERE report_type='found' AND status NOT IN ('returned','closed')) AS open_found,
        (SELECT COUNT(*) FROM claims WHERE status='pending') AS pending_claims,
        (SELECT COUNT(*) FROM handovers) AS recoveries""", fetch="one"),
      "categories": query("""SELECT c.category_name,COUNT(r.report_id) AS total
        FROM categories c LEFT JOIN item_reports r ON r.category_id=c.category_id
        GROUP BY c.category_id,c.category_name ORDER BY total DESC"""),
      "locations": query("""SELECT l.location_name,COUNT(r.report_id) AS total
        FROM locations l LEFT JOIN item_reports r ON r.location_id=l.location_id
        GROUP BY l.location_id,l.location_name ORDER BY total DESC LIMIT 5"""),
      "disputes": query("""SELECT d.*,r.item_name,u.full_name AS opened_by_name
        FROM disputes d JOIN item_reports r ON r.report_id=d.report_id
        JOIN users u ON u.user_id=d.opened_by WHERE d.status IN ('open','investigating')
        ORDER BY d.created_at DESC""")
    }


@app.get("/api/my-reports")
def my_reports(request: Request):
    user = require_user(request)
    return {"reports": query("""SELECT r.report_id,r.report_type,r.item_name,r.description,r.event_date,
        r.status,r.created_at,c.category_name,l.location_name
        FROM item_reports r JOIN categories c ON c.category_id=r.category_id
        JOIN locations l ON l.location_id=r.location_id
        WHERE r.reporter_id=%s ORDER BY r.created_at DESC""", (user["user_id"],))}

@app.get("/api/admin/users")
def admin_users(request: Request, q: Optional[str] = None, role: Optional[str] = None):
    require_admin(request)
    sql = "SELECT user_id,full_name,email,role,created_at FROM users WHERE 1=1"
    params = []
    if q and q.strip():
        sql += " AND (full_name LIKE %s OR email LIKE %s)"
        params.extend([f"%{q.strip()}%", f"%{q.strip()}%"])
    if role in ("student", "admin"):
        sql += " AND role=%s"
        params.append(role)
    sql += " ORDER BY created_at DESC LIMIT 500"
    return {"users": query(sql, tuple(params)), "total": query("SELECT COUNT(*) AS total FROM users", fetch="one")["total"]}

@app.get("/api/admin/disputes")
def admin_disputes(request: Request):
    require_admin(request)
    return {"disputes": query("""SELECT d.dispute_id,d.report_id,d.description,d.status,d.resolution,
        d.created_at,r.item_name,u.full_name AS opened_by_name,u.email AS opened_by_email
        FROM disputes d JOIN item_reports r ON r.report_id=d.report_id
        JOIN users u ON u.user_id=d.opened_by ORDER BY d.created_at DESC LIMIT 200""")}

@app.get("/api/admin/audit")
def admin_audit(request: Request):
    require_admin(request)
    return {"logs": query("""SELECT a.*,u.full_name AS actor_name FROM audit_logs a
        LEFT JOIN users u ON u.user_id=a.actor_id ORDER BY a.created_at DESC LIMIT 100""")}

@app.post("/api/admin/disputes/{dispute_id}/resolve")
def resolve_dispute(dispute_id: int, request: Request, status: str = Form(...), resolution: str = Form(...)):
    admin = require_admin(request)
    if status not in ("investigating", "resolved", "dismissed"):
        raise HTTPException(400, "Invalid dispute status.")
    query("""UPDATE disputes SET status=%s,resolution=%s,resolved_by=%s,
        resolved_at=IF(%s IN ('resolved','dismissed'),NOW(),NULL) WHERE dispute_id=%s""",
        (status, resolution.strip(), admin["user_id"], status, dispute_id), "none")
    audit(admin["user_id"], "DISPUTE_" + status.upper(), "dispute", dispute_id)
    return {"ok": True}

@app.get("/health")
def health():
    try:
        query("SELECT 1 AS ok", fetch="one")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "error", "database": str(e)})
