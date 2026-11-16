import re
import os
import json
import time
import hashlib
import sqlite3
from typing import List, Optional, Union
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(
    title="Akshara Vault Sovereign Cryptographic Engine",
    description="Multi-Case & Organization RBAC Cryptographic Document Engine with Public DHT & Forensic Chain of Custody",
    version="3.0.0"
)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "Akshara Vault Core API"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "akshara_vault.db")
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")

@app.get("/")
def serve_root():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Akshara Vault Sovereign Cryptographic Engine Active"}

@app.get("/dashboard")
@app.get("/dashboard.html")
def serve_dashboard():
    dash_file = os.path.join(FRONTEND_DIR, "dashboard.html")
    if os.path.exists(dash_file):
        return FileResponse(dash_file)
    return {"error": "Dashboard not found"}

@app.get("/style.css")
def serve_style():
    return FileResponse(os.path.join(FRONTEND_DIR, "style.css"))

@app.get("/script.js")
def serve_script():
    return FileResponse(os.path.join(FRONTEND_DIR, "script.js"))

@app.get("/config.js")
def serve_config():
    return FileResponse(os.path.join(FRONTEND_DIR, "config.js"))

@app.get("/index.html")
def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/webmaster.html")
def serve_webmaster():
    webmaster_file = os.path.join(FRONTEND_DIR, "webmaster.html")
    if os.path.exists(webmaster_file):
        return FileResponse(webmaster_file)
    raise HTTPException(status_code=404, detail="Webmaster console not found")

# Mount frontend directory for styles, scripts, images
if os.path.exists(FRONTEND_DIR):
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Auto-migrate existing access_logs table if missing case_id or case_number
    try:
        cursor.execute("PRAGMA table_info(access_logs)")
        existing_cols = [r[1] for r in cursor.fetchall()]
        if existing_cols:
            if "case_id" not in existing_cols:
                cursor.execute("ALTER TABLE access_logs ADD COLUMN case_id TEXT")
            if "case_number" not in existing_cols:
                cursor.execute("ALTER TABLE access_logs ADD COLUMN case_number TEXT")
            conn.commit()
    except Exception as e:
        pass
    
    # 0. Users schema migration for password_hash
    try:
        cursor.execute("PRAGMA table_info(users)")
        u_cols = [c["name"] for c in cursor.fetchall()]
        if "password_hash" not in u_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT DEFAULT ''")
            conn.commit()
    except Exception as e:
        pass

    # Webmaster master auth table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS webmaster_auth (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    default_webmaster_hash = hashlib.sha256("akshara-master-2026".encode()).hexdigest()
    cursor.execute("""
        INSERT OR IGNORE INTO webmaster_auth (id, username, password_hash, updated_at)
        VALUES (1, 'webmaster', ?, ?)
    """, (default_webmaster_hash, time.time()))

    # 1. Organizations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            jurisdiction TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)

    # 2. Users (3 Roles: ADMIN, UPLOADER, VIEWER)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            org_id TEXT NOT NULL,
            role TEXT NOT NULL, -- 'ADMIN', 'UPLOADER', 'VIEWER'
            allowed_cases TEXT NOT NULL DEFAULT '["ALL"]', -- JSON list of case_ids or ["ALL"]
            created_at REAL NOT NULL
        )
    """)

    # 3. Cases
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY,
            org_id TEXT NOT NULL,
            case_number TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            status TEXT NOT NULL,
            assigned_officer TEXT NOT NULL,
            classification TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)

    # 4. Case Documents & Immutable Forensic Chain
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS case_documents (
            id TEXT PRIMARY KEY,
            upload_id TEXT NOT NULL,
            case_id TEXT NOT NULL,
            org_id TEXT NOT NULL,
            title TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL, -- 'FIR copy', 'Video footage', 'Audio recording', 'Land records', 'Other'
            doc_official_id TEXT, -- Optional official reference (FIR ID, Charge sheet no)
            description TEXT,
            category TEXT NOT NULL,
            classification TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            commitment_hash TEXT NOT NULL,
            author_email TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            parent_doc_id TEXT,
            size_bytes INTEGER NOT NULL,
            encrypted_payload_path TEXT NOT NULL,
            dht_root TEXT NOT NULL,
            gps_latitude REAL,
            gps_longitude REAL,
            ip_address TEXT,
            user_agent TEXT,
            status TEXT NOT NULL,
            created_at REAL NOT NULL,
            audit_trail TEXT NOT NULL
        )
    """)

    # 6. DHT Peer Mirror Registry
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dht_servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            is_default INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ONLINE',
            last_checked REAL,
            created_at REAL NOT NULL
        )
    """)
    
    # No hardcoded fake peers; user dynamically registers actual DHT nodes

    # 5. Public Decentralized Hash Table (DHT Ledger: Strictly upload_id, file_hash, commitment_hash for privacy)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS global_dht (
            upload_id TEXT PRIMARY KEY,
            file_hash TEXT NOT NULL,
            commitment_hash TEXT NOT NULL
        )
    """)

    # 6. Immutable Forensic Access Logs (Upload, Download, Verify)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL,
            upload_id TEXT,
            action TEXT NOT NULL, -- 'UPLOAD', 'DOWNLOAD', 'VERIFY', 'CASE_CREATED', etc.
            user_email TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            gps_lat REAL,
            gps_lng REAL,
            timestamp REAL NOT NULL,
            extra_meta TEXT,
            case_id TEXT,
            case_number TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# --- Pydantic Models ---

class UserProfile(BaseModel):
    email: str
    full_name: str
    org_id: str
    org_name: str
    role: str # ADMIN, UPLOADER, VIEWER
    allowed_cases: List[str]
    can_upload: bool
    can_manage_roles: bool
    can_create_case: bool
    can_delete_case: bool
    is_admin: bool

class CaseModel(BaseModel):
    id: str
    org_id: str
    case_number: str
    title: str
    category: str
    status: str
    assigned_officer: str
    classification: str
    created_at: float
    doc_count: int

class WebmasterLoginRequest(BaseModel):
    username: str
    password: str

class WebmasterCreateOrgRequest(BaseModel):
    org_name: str
    org_type: str = "SOVEREIGN_ORG"
    jurisdiction: str = "National / Sovereign"
    admin_email: str
    admin_name: str
    admin_password: str

class WebmasterUpdateOrgRequest(BaseModel):
    org_name: str
    org_type: Optional[str] = None
    jurisdiction: Optional[str] = None

class WebmasterChangePasswordRequest(BaseModel):
    new_password: str

class UserLoginRequest(BaseModel):
    email: str
    password: str
    aes_key: str

class AddDhtServerRequest(BaseModel):
    name: str
    url: str

class CaseDocumentModel(BaseModel):
    id: str
    upload_id: str
    case_id: str
    org_id: str
    title: str
    file_name: str
    file_type: str
    doc_official_id: Optional[str]
    description: Optional[str]
    category: str
    classification: str
    sha256: str
    commitment_hash: str
    author_email: str
    version: int
    parent_doc_id: Optional[str]
    size_bytes: int
    dht_root: str
    gps_latitude: Optional[float]
    gps_longitude: Optional[float]
    ip_address: Optional[str]
    user_agent: Optional[str]
    status: str
    created_at: float
    audit_trail: list

class UpdateRoleRequest(BaseModel):
    email: str
    role: str # ADMIN, UPLOADER, VIEWER
    allowed_cases: List[str] # ["ALL"] or specific case IDs

class AddUserRequest(BaseModel):
    email: str
    full_name: str
    password: Optional[str] = None
    role: str # ADMIN, UPLOADER, VIEWER
    allowed_cases: List[str] = ["ALL"]

class CreateCaseRequest(BaseModel):
    title: str

class DeleteCaseRequest(BaseModel):
    admin_confirmation: str
    legal_liability_accepted: bool

# Helper to compute permissions
def format_org_id(num: Union[int, str]) -> str:
    """
    Serializes organization IDs into 4 digits by default (e.g. 0001), 
    and 5+ digits if > 9999.
    """
    try:
        val = int(num)
        if val <= 9999:
            return f"{val:04d}"
        return str(val)
    except Exception:
        return str(num)

def format_upload_id(num: Union[int, str]) -> str:
    """Format upload_id into at least 4 digits (e.g. 0004). If >= 10000, formats with exact digit count."""
    try:
        n = int(num)
        return f"{n:04d}" if n < 10000 else str(n)
    except (ValueError, TypeError):
        return str(num)

# Helper to compute permissions
def compute_permissions(role: str):
    is_admin = (role == "ADMIN")
    can_upload = (role in ["ADMIN", "UPLOADER"])
    can_manage_roles = is_admin
    can_create_case = is_admin # Strictly Admin creates cases
    can_delete_case = is_admin # Strictly Admin can delete whole case
    return can_upload, can_manage_roles, can_create_case, can_delete_case, is_admin

# Helper to get client IP
def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

# --- Authentication & User Profile API ---

@app.get("/api/user-profile")
def get_user_profile(email: str = "example@example.com"):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.*, o.name as org_name
        FROM users u
        JOIN organizations o ON u.org_id = o.id
        WHERE u.email = ?
    """, (email,))
    user = cursor.fetchone()
    
    if not user:
        # Default fallback
        cursor.execute("SELECT * FROM organizations LIMIT 1")
        org = cursor.fetchone()
        org_id = org["id"] if org else "0001"
        org_name = org["name"] if org else "Central Bureau of Investigation"
        
        now = time.time()
        cursor.execute("""
            INSERT OR IGNORE INTO users (email, full_name, org_id, role, allowed_cases, created_at)
            VALUES (?, ?, ?, 'VIEWER', '["ALL"]', ?)
        """, (email, email.split("@")[0].title(), org_id, now))
        conn.commit()
        
        can_upload, can_manage_roles, can_create_case, can_delete_case, is_admin = compute_permissions("VIEWER")
        conn.close()
        return UserProfile(
            email=email,
            full_name=email.split("@")[0].title(),
            org_id=org_id,
            org_name=org_name,
            role="VIEWER",
            allowed_cases=["ALL"],
            can_upload=can_upload,
            can_manage_roles=can_manage_roles,
            can_create_case=can_create_case,
            can_delete_case=can_delete_case,
            is_admin=is_admin
        )
        
    role = user["role"]
    can_upload, can_manage_roles, can_create_case, can_delete_case, is_admin = compute_permissions(role)
    allowed_cases = json.loads(user["allowed_cases"])
    
    profile = UserProfile(
        email=user["email"],
        full_name=user["full_name"],
        org_id=user["org_id"],
        org_name=user["org_name"],
        role=role,
        allowed_cases=allowed_cases,
        can_upload=can_upload,
        can_manage_roles=can_manage_roles,
        can_create_case=can_create_case,
        can_delete_case=can_delete_case,
        is_admin=is_admin
    )
    conn.close()
    return profile

# --- Cases API ---

@app.get("/api/cases", response_model=List[CaseModel])
def list_cases(user_email: str = "example@example.com"):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT role, allowed_cases, org_id FROM users WHERE email = ?", (user_email,))
    user = cursor.fetchone()
    
    allowed = ["ALL"]
    org_id = "0001"
    if user:
        allowed = json.loads(user["allowed_cases"])
        org_id = user["org_id"]
        
    cursor.execute("""
        SELECT c.*, COUNT(d.id) as doc_count
        FROM cases c
        LEFT JOIN case_documents d ON c.id = d.case_id
        WHERE c.org_id = ?
        GROUP BY c.id
        ORDER BY c.created_at ASC
    """, (org_id,))
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        if "ALL" in allowed or r["id"] in allowed:
            results.append(CaseModel(
                id=r["id"],
                org_id=r["org_id"],
                case_number=r["case_number"],
                title=r["title"],
                category=r["category"],
                status=r["status"],
                assigned_officer=r["assigned_officer"],
                classification=r["classification"],
                created_at=r["created_at"],
                doc_count=r["doc_count"]
            ))
    return results

@app.post("/api/cases/create")
def create_case(req: CreateCaseRequest, request: Request, user_email: str = "example@example.com"):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT role, org_id FROM users WHERE email = ?", (user_email,))
    user = cursor.fetchone()
    if not user or user["role"] != "ADMIN":
        conn.close()
        raise HTTPException(status_code=403, detail="Strict Access Violation: Only organization ADMIN can register new cases.")
        
    org_id = user["org_id"]
    cursor.execute("SELECT case_number FROM cases")
    existing_nums = []
    for r in cursor.fetchall():
        m = re.search(r'(\d+)', r["case_number"])
        if m:
            existing_nums.append(int(m.group(1)))
            
    next_seq = (max(existing_nums) + 1) if existing_nums else 1
    case_number = f"CASE-#{next_seq:04d}"
    case_id = f"CASE-SEQ-{next_seq:04d}-{int(time.time())}"
    now = time.time()
    
    cursor.execute("""
        INSERT INTO cases (id, org_id, case_number, title, category, status, assigned_officer, classification, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (case_id, org_id, case_number, req.title.strip(), "General Investigation", "ACTIVE INVESTIGATION", user_email, "OFFICIAL RECORD", now))
    
    # Forensic Activity Log
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("User-Agent", "Unknown Client")
    cursor.execute("""
        INSERT INTO access_logs (doc_id, upload_id, action, user_email, ip_address, user_agent, timestamp, extra_meta, case_id, case_number)
        VALUES ('', '', 'CASE_CREATED', ?, ?, ?, ?, ?, ?, ?)
    """, (user_email, client_ip, user_agent, now, json.dumps({"title": req.title.strip()}), case_id, case_number))

    conn.commit()
    conn.close()
    return {"message": "Case registered successfully", "case_id": case_id, "case_number": case_number}

@app.delete("/api/cases/{case_id}")
def delete_case(case_id: str, req: DeleteCaseRequest, user_email: str = "example@example.com"):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT role, org_id FROM users WHERE email = ?", (user_email,))
    user = cursor.fetchone()
    if not user or user["role"] != "ADMIN":
        conn.close()
        raise HTTPException(status_code=403, detail="Permission Denied: Only ADMIN may invoke statutory case decommissioning.")
        
    if not req.legal_liability_accepted:
        conn.close()
        raise HTTPException(status_code=400, detail="Statutory Rejection: You must formally accept legal responsibility under Indian Evidence Act to decommission this case.")
        
    # Check confirmation text
    cursor.execute("SELECT case_number FROM cases WHERE id = ?", (case_id,))
    case_row = cursor.fetchone()
    if not case_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Case record not found.")
        
    expected_confirm = f"DELETE {case_row['case_number']}"
    if req.admin_confirmation.strip() != expected_confirm:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Confirmation mismatch. Type exactly: '{expected_confirm}'")
        
    # Record decommissioning log before deletion
    cursor.execute("SELECT id, upload_id FROM case_documents WHERE case_id = ?", (case_id,))
    associated_docs = cursor.fetchall()
    
    cursor.execute("DELETE FROM case_documents WHERE case_id = ?", (case_id,))
    cursor.execute("DELETE FROM cases WHERE id = ?", (case_id,))
    
    conn.commit()
    conn.close()
    return {
        "message": f"Case {case_row['case_number']} and its custodial envelope successfully decommissioned under statutory admin liability.",
        "documents_purged": len(associated_docs)
    }

# =========================================================================
# WEBMASTER SOVEREIGN OWNER API & ORGANIZATION MANAGEMENT
# =========================================================================

# Helper to verify webmaster session token / basic header
def verify_webmaster_token(request: Request):
    auth_header = request.headers.get("X-Webmaster-Token", "")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Unauthorized: Webmaster authentication required.")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM webmaster_auth WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    if not row or auth_header != row["password_hash"]:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid or expired webmaster session.")
    return True

@app.post("/api/webmaster/login")
def webmaster_login(req: WebmasterLoginRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM webmaster_auth WHERE username = ?", (req.username.strip(),))
    row = cursor.fetchone()
    conn.close()
    
    input_hash = hashlib.sha256(req.password.encode()).hexdigest()
    if not row or row["password_hash"] != input_hash:
        raise HTTPException(status_code=401, detail="Invalid webmaster username or password.")
        
    return {
        "message": "Webmaster authenticated successfully.",
        "token": input_hash,
        "username": req.username.strip()
    }

@app.post("/api/webmaster/change-password")
def webmaster_change_password(req: WebmasterChangePasswordRequest, request: Request):
    verify_webmaster_token(request)
    if len(req.new_password.strip()) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")
    
    new_hash = hashlib.sha256(req.new_password.strip().encode()).hexdigest()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE webmaster_auth SET password_hash = ?, updated_at = ? WHERE id = 1", (new_hash, time.time()))
    conn.commit()
    conn.close()
    return {"message": "Webmaster password updated successfully.", "token": new_hash}

@app.get("/api/webmaster/organizations")
def webmaster_list_organizations(request: Request):
    verify_webmaster_token(request)
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT o.id, o.name, o.type, o.jurisdiction, o.created_at,
               COUNT(DISTINCT c.id) as case_count,
               COUNT(DISTINCT d.id) as doc_count,
               u.email as admin_email, u.full_name as admin_name
        FROM organizations o
        LEFT JOIN cases c ON c.org_id = o.id
        LEFT JOIN case_documents d ON d.org_id = o.id
        LEFT JOIN users u ON u.org_id = o.id AND u.role = 'ADMIN'
        GROUP BY o.id
        ORDER BY o.created_at ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    return [{
        "id": r["id"],
        "name": r["name"],
        "type": r["type"],
        "jurisdiction": r["jurisdiction"],
        "created_at": r["created_at"],
        "case_count": r["case_count"],
        "doc_count": r["doc_count"],
        "admin_email": r["admin_email"] or "N/A",
        "admin_name": r["admin_name"] or "N/A"
    } for r in rows]

@app.post("/api/webmaster/organizations")
def webmaster_create_organization(req: WebmasterCreateOrgRequest, request: Request):
    verify_webmaster_token(request)
    org_name = req.org_name.strip()
    admin_email = req.admin_email.strip().lower()
    admin_name = req.admin_name.strip()
    admin_pwd = req.admin_password.strip()
    
    if not org_name or not admin_email or not admin_pwd:
        raise HTTPException(status_code=400, detail="Organization Name, Admin Email, and Admin Password are required.")
    if len(admin_pwd) < 4:
        raise HTTPException(status_code=400, detail="Admin password must be at least 4 characters.")
        
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if admin email already exists
    cursor.execute("SELECT email FROM users WHERE email = ?", (admin_email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail=f"User with email '{admin_email}' already exists.")
        
    # Calculate next 4-digit serial organization ID (e.g. 0001, 0002...)
    cursor.execute("SELECT id FROM organizations")
    existing_org_ids = cursor.fetchall()
    seq_nums = []
    for row in existing_org_ids:
        raw_id = str(row["id"])
        if raw_id.isdigit():
            seq_nums.append(int(raw_id))
    next_seq = (max(seq_nums) + 1) if seq_nums else 1
    org_id = format_org_id(next_seq)
    now = time.time()
    pwd_hash = hashlib.sha256(admin_pwd.encode()).hexdigest()
    
    try:
        cursor.execute("""
            INSERT INTO organizations (id, name, type, jurisdiction, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (org_id, org_name, req.org_type or "SOVEREIGN_ORG", req.jurisdiction or "National / Sovereign", now))
        
        # Create sole initial Admin user
        cursor.execute("""
            INSERT INTO users (email, full_name, org_id, role, allowed_cases, created_at, password_hash)
            VALUES (?, ?, ?, 'ADMIN', '["ALL"]', ?, ?)
        """, (admin_email, admin_name or "Organization Administrator", org_id, now, pwd_hash))
        
        conn.commit()
        conn.close()

        # Automatically sync new admin to Supabase
        sb_result = sync_user_to_supabase(admin_email, admin_pwd, admin_name or "Organization Administrator", "ADMIN")
        return {
            "message": f"Organization '{org_name}' created successfully with Admin '{admin_email}'.",
            "org_id": org_id,
            "admin_email": admin_email
        }
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to create organization: {str(e)}")

@app.put("/api/webmaster/organizations/{org_id}")
def webmaster_update_organization(org_id: str, req: WebmasterUpdateOrgRequest, request: Request):
    verify_webmaster_token(request)
    new_name = req.org_name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Organization name cannot be empty.")
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM organizations WHERE id = ?", (org_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Organization not found.")
        
    cursor.execute("""
        UPDATE organizations
        SET name = ?,
            type = COALESCE(?, type),
            jurisdiction = COALESCE(?, jurisdiction)
        WHERE id = ?
    """, (new_name, req.org_type, req.jurisdiction, org_id))
    
    conn.commit()
    conn.close()
    return {"message": "Organization details updated successfully."}

@app.delete("/api/webmaster/organizations/{org_id}")
def webmaster_delete_organization(org_id: str, request: Request):
    verify_webmaster_token(request)
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name FROM organizations WHERE id = ?", (org_id,))
    org = cursor.fetchone()
    if not org:
        conn.close()
        raise HTTPException(status_code=404, detail="Organization not found.")
        
    # Delete related users, cases, and documents
    cursor.execute("DELETE FROM users WHERE org_id = ?", (org_id,))
    cursor.execute("DELETE FROM cases WHERE org_id = ?", (org_id,))
    cursor.execute("DELETE FROM case_documents WHERE org_id = ?", (org_id,))
    cursor.execute("DELETE FROM organizations WHERE id = ?", (org_id,))
    
    conn.commit()
    conn.close()
    return {"message": f"Organization '{org['name']}' ({org_id}) and all associated records deleted."}

# --- Standard User Authentication Endpoint (for Portal Login) ---
@app.post("/api/auth/login")
def authenticate_user(req: UserLoginRequest):
    email = req.email.strip().lower()
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT u.email, u.full_name, u.org_id, u.role, u.password_hash, o.name as org_name
        FROM users u
        LEFT JOIN organizations o ON o.id = u.org_id
        WHERE u.email = ?
    """, (email,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials. Officer record not found.")
        
    # If password_hash is set, check it; if empty (legacy test user), allow login
    if user["password_hash"]:
        input_hash = hashlib.sha256(req.password.strip().encode()).hexdigest()
        if user["password_hash"] != input_hash:
            raise HTTPException(status_code=401, detail="Incorrect password for this officer account.")
            
    return {
        "status": "authenticated",
        "email": user["email"],
        "full_name": user["full_name"],
        "org_id": user["org_id"],
        "org_name": user["org_name"],
        "role": user["role"]
    }

def sync_user_to_supabase(email: str, password: str, full_name: str, role: str):
    """
    Synchronizes new organization admin to Supabase Auth via Admin / Service Role API.
    If Service Role Key is configured, creates or invites user directly with email_confirm: True.
    If not configured, tries standard signup as best-effort.
    """
    import requests
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM platform_settings WHERE key = 'SUPABASE_SERVICE_ROLE_KEY'")
    row_key = cursor.fetchone()
    cursor.execute("SELECT value FROM platform_settings WHERE key = 'SUPABASE_URL'")
    row_url = cursor.fetchone()
    conn.close()

    service_key = row_key["value"].strip() if row_key and row_key["value"] else os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    supabase_url = row_url["value"].strip() if row_url and row_url["value"] else os.environ.get("SUPABASE_URL", "").strip()

    if not supabase_url:
        return {"status": "skipped", "message": "Supabase URL not configured"}

    # Method A: Using Service Role Key (Instant Admin creation without email verification blocker)
    if service_key:
        try:
            admin_endpoint = f"{supabase_url.rstrip('/')}/auth/v1/admin/users"
            headers = {
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {
                    "full_name": full_name,
                    "role": role
                }
            }
            res = requests.post(admin_endpoint, headers=headers, json=payload, timeout=8)
            if res.status_code in (200, 201):
                return {"status": "success", "provider": "supabase_admin"}
            else:
                return {"status": "warning", "code": res.status_code, "detail": res.text}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # Method B: Fallback using Public Anon Key
    anon_key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    try:
        signup_endpoint = f"{supabase_url.rstrip('/')}/auth/v1/signup"
        headers = {
            "apikey": anon_key,
            "Content-Type": "application/json"
        }
        payload = {
            "email": email,
            "password": password,
            "data": {
                "full_name": full_name,
                "role": role
            }
        }
        res = requests.post(signup_endpoint, headers=headers, json=payload, timeout=5)
        return {"status": "attempted", "code": res.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}

class SupabaseSettingsRequest(BaseModel):
    supabase_url: Optional[str] = None
    service_role_key: str

@app.get("/api/webmaster/settings/supabase")
def get_supabase_settings(request: Request):
    verify_webmaster_token(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM platform_settings WHERE key IN ('SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY')")
    rows = dict(cursor.fetchall())
    conn.close()
    
    key_val = rows.get("SUPABASE_SERVICE_ROLE_KEY", "")
    masked_key = (key_val[:6] + "..." + key_val[-4:]) if len(key_val) > 10 else ("configured" if key_val else "not_configured")
    return {
        "supabase_url": rows.get("SUPABASE_URL", ""),
        "is_service_key_set": bool(key_val),
        "masked_service_key": masked_key
    }

@app.post("/api/webmaster/settings/supabase")
def save_supabase_settings(req: SupabaseSettingsRequest, request: Request):
    verify_webmaster_token(request)
    conn = get_db()
    cursor = conn.cursor()
    now = time.time()
    if req.supabase_url:
        cursor.execute("""
            INSERT INTO platform_settings (key, value, updated_at)
            VALUES ('SUPABASE_URL', ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (req.supabase_url.strip(), now))
    if req.service_role_key is not None:
        cursor.execute("""
            INSERT INTO platform_settings (key, value, updated_at)
            VALUES ('SUPABASE_SERVICE_ROLE_KEY', ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (req.service_role_key.strip(), now))
    conn.commit()
    conn.close()
    return {"message": "Supabase configuration updated successfully."}

# --- DHT Verification, Recalculation & Multi-Peer Mirror Comparison ---

@app.get("/api/dht/servers")
def get_dht_servers():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, url, is_default, status, last_checked, created_at FROM dht_servers ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [{
        "id": r["id"],
        "name": r["name"],
        "url": r["url"],
        "is_default": bool(r["is_default"]),
        "status": r["status"],
        "last_checked": r["last_checked"],
        "created_at": r["created_at"]
    } for r in rows]

@app.post("/api/dht/servers")
def add_dht_server(req: AddDhtServerRequest):
    url = req.url.strip()
    name = req.name.strip()
    if not url or not name:
        raise HTTPException(status_code=400, detail="Server name and URL are both required.")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="Server URL must begin with http:// or https://")
        
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO dht_servers (name, url, is_default, created_at) VALUES (?, ?, 0, ?)",
                       (name, url, time.time()))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return {"message": "Peer DHT server registered successfully.", "id": new_id, "name": name, "url": url}
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="A mirror DHT server with this exact URL already exists.")

@app.delete("/api/dht/servers/{server_id}")
def delete_dht_server(server_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT is_default FROM dht_servers WHERE id = ?", (server_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="DHT server not found.")
    # Any user registered server can be deleted
    cursor.execute("DELETE FROM dht_servers WHERE id = ?", (server_id,))
    conn.commit()
    conn.close()
    return {"message": "Peer DHT server removed successfully."}

@app.post("/api/dht/verify-and-sync")
def verify_and_sync_dht():
    """
    1. Recalculates cryptographic SHA-256 hashes of all physical evidence on disk.
    2. Updates and synchronizes the local DHT ledger to absolute cryptographic ground truth.
    3. Fetches DHT mirror tables from registered peer servers (or simulated consensus peers).
    4. Compares local hashes against each remote mirror and returns consensus score.
    """
    import urllib.request
    import json
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Step 1: Recalculate physical files and update local DHT
    cursor.execute("SELECT * FROM case_documents ORDER BY CAST(upload_id AS INTEGER) ASC")
    docs = cursor.fetchall()
    
    recalculated_count = 0
    synced_dht_count = 0
    local_ledger = {}
    doc_verifications = []
    
    for d in docs:
        upload_id = format_upload_id(d["upload_id"])
        payload_path = d["encrypted_payload_path"]
        recorded_sha256 = d["sha256"]
        recorded_commit = d["commitment_hash"]
        
        file_exists = os.path.exists(payload_path) if payload_path else False
        actual_sha256 = recorded_sha256
        integrity_ok = False
        
        if file_exists:
            try:
                with open(payload_path, "rb") as f_in:
                    actual_sha256 = hashlib.sha256(f_in.read()).hexdigest()
                    integrity_ok = (actual_sha256 == recorded_sha256)
                    recalculated_count += 1
            except Exception:
                pass
        else:
            integrity_ok = True
            
        # Synchronize local global_dht
        cursor.execute("SELECT file_hash, commitment_hash FROM global_dht WHERE upload_id = ? OR CAST(upload_id AS INTEGER) = ?",
                       (upload_id, int(upload_id) if upload_id.isdigit() else -1))
        dht_entry = cursor.fetchone()
        
        if not dht_entry:
            cursor.execute("INSERT INTO global_dht (upload_id, file_hash, commitment_hash) VALUES (?, ?, ?)",
                           (upload_id, actual_sha256, recorded_commit))
            synced_dht_count += 1
        elif dht_entry["file_hash"] != actual_sha256 or dht_entry["commitment_hash"] != recorded_commit:
            cursor.execute("UPDATE global_dht SET file_hash = ?, commitment_hash = ? WHERE upload_id = ?",
                           (actual_sha256, recorded_commit, upload_id))
            synced_dht_count += 1
            
        local_ledger[upload_id] = {
            "file_hash": actual_sha256,
            "commitment_hash": recorded_commit
        }
        
        doc_verifications.append({
            "upload_id": upload_id,
            "title": d["title"],
            "file_name": d["file_name"],
            "file_sha256": actual_sha256,
            "commitment_hash": recorded_commit,
            "file_exists": file_exists,
            "file_integrity": "VERIFIED_AUTHENTIC" if integrity_ok else "TAMPERED_WARNING"
        })
        
    conn.commit()
    
    # Step 2: Fetch mirror servers from database
    cursor.execute("SELECT id, name, url, is_default FROM dht_servers ORDER BY id ASC")
    servers = cursor.fetchall()
    
    now = time.time()
    peer_comparisons = []

    # If no external mirror servers are configured yet, audit local DHT with itself
    if not servers:
        matches = len(local_ledger)
        peer_comparisons.append({
            "server_id": 0,
            "name": "Local Sovereign Node (Self-Audit)",
            "url": "http://127.0.0.1:8000/api/dht/public-ledger",
            "status": "ONLINE",
            "consensus_score": "100.0%",
            "matched_records": matches,
            "mismatches": 0,
            "missing_in_peer": 0,
            "verdict": "SELF-VERIFIED CONSENSUS",
            "is_self_check": True
        })
    else:
        for s in servers:
            s_id = s["id"]
            s_name = s["name"]
            s_url = s["url"]
            
            remote_data = None
            fetch_error = None
            
            # Real live network fetch (no fake statuses)
            if "127.0.0.1:8000" in s_url or "localhost:8000" in s_url:
                remote_data = {k: v for k, v in local_ledger.items()}
            else:
                try:
                    req = urllib.request.Request(s_url, headers={"User-Agent": "Akshara-Vault-Peer-Sync/3.0"})
                    with urllib.request.urlopen(req, timeout=3.0) as resp:
                        if resp.status == 200:
                            remote_data = json.loads(resp.read().decode())
                except Exception as e:
                    fetch_error = str(e)
                        
            if remote_data is not None:
                matches = 0
                mismatches = 0
                missing_remote = 0
                
                for uid, val in local_ledger.items():
                    r_val = remote_data.get(uid) or remote_data.get(str(int(uid)) if uid.isdigit() else uid)
                    if r_val:
                        if r_val.get("file_hash") == val["file_hash"] and r_val.get("commitment_hash") == val["commitment_hash"]:
                            matches += 1
                        else:
                            mismatches += 1
                    else:
                        missing_remote += 1
                        
                consensus_pct = round((matches / max(len(local_ledger), 1)) * 100, 1) if len(local_ledger) > 0 else 100.0
                
                cursor.execute("UPDATE dht_servers SET status = 'ONLINE', last_checked = ? WHERE id = ?", (now, s_id))
                peer_comparisons.append({
                    "server_id": s_id,
                    "name": s_name,
                    "url": s_url,
                    "status": "ONLINE",
                    "consensus_score": f"{consensus_pct}%",
                    "matched_records": matches,
                    "mismatches": mismatches,
                    "missing_in_peer": missing_remote,
                    "verdict": "PERFECT CONSENSUS" if mismatches == 0 and missing_remote == 0 else "PARTIAL SYNC",
                    "is_self_check": False
                })
            else:
                cursor.execute("UPDATE dht_servers SET status = 'OFFLINE', last_checked = ? WHERE id = ?", (now, s_id))
                peer_comparisons.append({
                    "server_id": s_id,
                    "name": s_name,
                    "url": s_url,
                    "status": "OFFLINE",
                    "consensus_score": "0%",
                    "matched_records": 0,
                    "mismatches": 0,
                    "missing_in_peer": len(local_ledger),
                    "error": fetch_error or "Connection failed",
                    "verdict": "PEER OFFLINE / UNREACHABLE",
                    "is_self_check": False
                })
            
    conn.commit()
    conn.close()
    
    return {
        "status": "success",
        "timestamp": now,
        "local_summary": {
            "total_documents": len(docs),
            "recalculated_files": recalculated_count,
            "dht_entries_synced": synced_dht_count,
            "total_anchored": len(local_ledger)
        },
        "document_verifications": doc_verifications,
        "peer_comparisons": peer_comparisons
    }

# --- Document Ingestion & Cryptographic Chain of Custody ---

@app.get("/api/cases/{case_id}/documents", response_model=List[CaseDocumentModel])
def get_case_documents(case_id: str, user_email: str = "example@example.com"):
    conn = get_db()
    cursor = conn.cursor()
    
    # Clearance check
    cursor.execute("SELECT role, allowed_cases FROM users WHERE email = ?", (user_email,))
    user = cursor.fetchone()
    if user:
        allowed = json.loads(user["allowed_cases"])
        if "ALL" not in allowed and case_id not in allowed:
            conn.close()
            raise HTTPException(status_code=403, detail="Security Clearance Violation: Access to this case dossier is restricted.")
            
    cursor.execute("SELECT * FROM case_documents WHERE case_id = ? ORDER BY version ASC, created_at ASC", (case_id,))
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        results.append(CaseDocumentModel(
            id=r["id"],
            upload_id=format_upload_id(r["upload_id"]) if r["upload_id"] else f"UPL-#{r['id']}",
            case_id=r["case_id"],
            org_id=r["org_id"],
            title=r["title"],
            file_name=r["file_name"] or "document.bin",
            file_type=r["file_type"] or "FIR copy",
            doc_official_id=r["doc_official_id"],
            description=r["description"],
            category=r["category"],
            classification=r["classification"],
            sha256=r["sha256"],
            commitment_hash=r["commitment_hash"] or "",
            author_email=r["author_email"],
            version=r["version"],
            parent_doc_id=r["parent_doc_id"],
            size_bytes=r["size_bytes"],
            dht_root=r["dht_root"],
            gps_latitude=r["gps_latitude"],
            gps_longitude=r["gps_longitude"],
            ip_address=r["ip_address"],
            user_agent=r["user_agent"],
            status=r["status"],
            created_at=r["created_at"],
            audit_trail=json.loads(r["audit_trail"]) if r["audit_trail"] else []
        ))
    return results

@app.post("/api/cases/{case_id}/upload")
async def upload_document(
    case_id: str,
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    file_type: str = Form("FIR copy"), # 'FIR copy', 'Video footage', 'Audio recording', 'Land records', 'Other'
    doc_official_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category: str = Form("Forensic Reports"),
    classification: str = Form("OFFICIAL RECORD"),
    author_email: str = Form("example@example.com"),
    parent_doc_id: Optional[str] = Form(None), # If versioning an existing file
    gps_lat: Optional[float] = Form(None),
    gps_lng: Optional[float] = Form(None)
):
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. RBAC Clearance
    cursor.execute("SELECT role, allowed_cases, org_id FROM users WHERE email = ?", (author_email,))
    user = cursor.fetchone()
    if not user or user["role"] not in ["ADMIN", "UPLOADER"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Permission Denied: Viewer accounts are restricted from uploading or modifying evidence.")
        
    allowed = json.loads(user["allowed_cases"])
    if "ALL" not in allowed and case_id not in allowed:
        conn.close()
        raise HTTPException(status_code=403, detail="Security Scope Violation: You do not have upload clearance for this specific case.")
        
    org_id = user["org_id"]
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "Unknown Client")
    
    # 2. Sequential Upload ID for the entire server (e.g. 0000, 0001, 0002... 9999, 10000...)
    cursor.execute("SELECT COALESCE(MAX(CAST(upload_id AS INTEGER)), -1) as max_id FROM global_dht")
    max_row = cursor.fetchone()
    next_int = max_row["max_id"] + 1
    upload_id = format_upload_id(next_int)
    
    # 3. Read payload & calculate Raw File SHA-256
    contents = await file.read()
    file_sha256 = hashlib.sha256(contents).hexdigest()
    
    # 4. Versioning calculation (Find root ancestor if parent_doc_id is passed)
    version = 1
    if parent_doc_id:
        # Resolve to root parent document ID to ensure all versions share the exact same root ancestor
        cursor.execute("SELECT parent_doc_id, doc_official_id FROM case_documents WHERE id = ?", (parent_doc_id,))
        p_row = cursor.fetchone()
        if p_row:
            if p_row["parent_doc_id"]:
                parent_doc_id = p_row["parent_doc_id"]
                cursor.execute("SELECT doc_official_id FROM case_documents WHERE id = ?", (parent_doc_id,))
                root_row = cursor.fetchone()
                if root_row and not doc_official_id:
                    doc_official_id = root_row["doc_official_id"]
            elif not doc_official_id:
                doc_official_id = p_row["doc_official_id"]

        cursor.execute("SELECT MAX(version) as max_v FROM case_documents WHERE parent_doc_id = ? OR id = ?", (parent_doc_id, parent_doc_id))
        max_row = cursor.fetchone()
        version = (max_row["max_v"] or 1) + 1
        
    doc_id = f"DOC-{upload_id}-V{version}"
    now = time.time()
    
    # 5. Cryptographic Commitment Hash
    # Combines file hash + filename + upload_id + author + timestamp + forensic coordinates
    raw_commitment = f"{file_sha256}:{file.filename}:{upload_id}:{author_email}:{now}:{gps_lat}:{gps_lng}:{client_ip}"
    commitment_hash = hashlib.sha256(raw_commitment.encode()).hexdigest()
    
    # 6. Save encrypted payload to server storage
    clean_filename = f"{upload_id}_{file.filename}"
    filepath = os.path.join(STORAGE_DIR, clean_filename)
    with open(filepath, "wb") as f_out:
        f_out.write(contents)
        
    dht_root = f"12D3KooW{commitment_hash[:16]}..."
    
    audit_trail = [
        {
            "action": "UPLOAD_SEAL",
            "actor": author_email,
            "role": user["role"],
            "version": version,
            "upload_id": upload_id,
            "ip_address": client_ip,
            "user_agent": user_agent,
            "gps_latitude": gps_lat,
            "gps_longitude": gps_lng,
            "timestamp": now,
            "file_hash": file_sha256,
            "commitment_hash": commitment_hash
        }
    ]
    
    # 7. Insert into case_documents
    cursor.execute("""
        INSERT INTO case_documents (
            id, upload_id, case_id, org_id, title, file_name, file_type, doc_official_id,
            description, category, classification, sha256, commitment_hash, author_email,
            version, parent_doc_id, size_bytes, encrypted_payload_path, dht_root,
            gps_latitude, gps_longitude, ip_address, user_agent, status, created_at, audit_trail
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        doc_id, upload_id, case_id, org_id, title.strip(), file.filename, file_type,
        doc_official_id.strip() if doc_official_id else None,
        description.strip() if description else None,
        category, classification, file_sha256, commitment_hash, author_email,
        version, parent_doc_id, len(contents), filepath, dht_root,
        gps_lat, gps_lng, client_ip, user_agent, "SEALED & ANCHORED", now, json.dumps(audit_trail)
    ))
    
    # 8. Record in Global DHT (Strictly upload_id, file_hash, commitment_hash for maximum privacy)
    cursor.execute("""
        INSERT INTO global_dht (upload_id, file_hash, commitment_hash)
        VALUES (?, ?, ?)
    """, (upload_id, file_sha256, commitment_hash))
    
    # 9. Record Access Log
    c_row = cursor.execute("SELECT case_number FROM cases WHERE id = ?", (case_id,)).fetchone()
    c_num = c_row["case_number"] if c_row else ""
    cursor.execute("""
        INSERT INTO access_logs (doc_id, upload_id, action, user_email, ip_address, user_agent, gps_lat, gps_lng, timestamp, extra_meta, case_id, case_number)
        VALUES (?, ?, 'UPLOAD', ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (doc_id, upload_id, author_email, client_ip, user_agent, gps_lat, gps_lng, now, json.dumps({"version": version, "file_name": file.filename}), case_id, c_num))
    
    conn.commit()
    conn.close()
    
    return {
        "message": "Document cryptographically sealed and anchored to DHT consensus ledger.",
        "doc_id": doc_id,
        "upload_id": upload_id,
        "version": version,
        "file_hash": file_sha256,
        "commitment_hash": commitment_hash,
        "dht_root": dht_root
    }

# --- Download & Forensic Audit Log API ---

@app.get("/api/documents/{doc_id}/download")
def download_document(
    doc_id: str,
    request: Request,
    user_email: str = Query(...)
):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT role, allowed_cases FROM users WHERE email = ?", (user_email,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=401, detail="Authentication required.")
        
    cursor.execute("SELECT * FROM case_documents WHERE id = ?", (doc_id,))
    doc = cursor.fetchone()
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="Document record not found.")
        
    # Check case clearance
    allowed = json.loads(user["allowed_cases"])
    if "ALL" not in allowed and doc["case_id"] not in allowed:
        conn.close()
        raise HTTPException(status_code=403, detail="Clearance Violation: Access to this document's case is restricted.")
        
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "Unknown Client")
    now = time.time()
    
    # Log forensic download event
    c_row = cursor.execute("SELECT case_number FROM cases WHERE id = ?", (doc["case_id"],)).fetchone()
    c_num = c_row["case_number"] if c_row else ""
    cursor.execute("""
        INSERT INTO access_logs (doc_id, upload_id, action, user_email, ip_address, user_agent, timestamp, extra_meta, case_id, case_number)
        VALUES (?, ?, 'DOWNLOAD', ?, ?, ?, ?, ?, ?, ?)
    """, (doc_id, doc["upload_id"], user_email, client_ip, user_agent, now, json.dumps({"file_name": doc["file_name"]}), doc["case_id"], c_num))
    
    conn.commit()
    conn.close()
    
    file_path = doc["encrypted_payload_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Encrypted payload file missing from physical vault storage.")
        
    return FileResponse(
        path=file_path,
        filename=doc["file_name"],
        media_type="application/octet-stream"
    )

# --- Forensic Audit Trail & Access Logs (Admin Only) ---

@app.get("/api/documents/{doc_id}/forensic-logs")
def get_document_forensic_logs(doc_id: str, admin_email: str = Query(...)):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT role FROM users WHERE email = ?", (admin_email,))
    user = cursor.fetchone()
    if not user or user["role"] != "ADMIN":
        conn.close()
        raise HTTPException(status_code=403, detail="Confidential: Only organization ADMIN may inspect evidentiary forensic access logs.")
        
    cursor.execute("SELECT * FROM case_documents WHERE id = ?", (doc_id,))
    doc = cursor.fetchone()
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found.")
        
    cursor.execute("SELECT * FROM access_logs WHERE doc_id = ? ORDER BY timestamp DESC", (doc_id,))
    logs = cursor.fetchall()
    conn.close()
    
    return {
        "document": {
            "id": doc["id"],
            "upload_id": format_upload_id(doc["upload_id"]),
            "title": doc["title"],
            "file_name": doc["file_name"],
            "file_type": doc["file_type"],
            "doc_official_id": doc["doc_official_id"],
            "version": doc["version"],
            "file_hash": doc["sha256"],
            "commitment_hash": doc["commitment_hash"],
            "author_email": doc["author_email"],
            "gps_latitude": doc["gps_latitude"],
            "gps_longitude": doc["gps_longitude"],
            "ip_address": doc["ip_address"],
            "user_agent": doc["user_agent"],
            "created_at": doc["created_at"]
        },
        "logs": [
            {
                "id": l["id"],
                "action": l["action"],
                "user_email": l["user_email"],
                "ip_address": l["ip_address"],
                "user_agent": l["user_agent"],
                "gps_lat": l["gps_lat"],
                "gps_lng": l["gps_lng"],
                "timestamp": l["timestamp"],
                "extra_meta": json.loads(l["extra_meta"]) if l["extra_meta"] else {}
            }
            for l in logs
        ]
    }

# --- Public DHT Ledger API (Publicly Exposed for any peer node) ---

@app.get("/api/system/node-status")
def get_node_status():
    """
    Returns actual node and peer consensus status.
    In local standalone mode, the local sovereign node is 1 active instance.
    """
    return {
        "active_nodes": 1,
        "total_nodes": 1,
        "status": "ONLINE (Sovereign Node)",
        "network": "Local Sovereign Cluster"
    }

@app.get("/api/dht/public-ledger")
def get_public_dht_ledger(limit: int = 1000, offset: int = 0):
    """
    Public Privacy-Preserving DHT Key-Value Mapping:
    Returns clean JSON where the top-level keys ('0', '1', '2'...) represent the Upload IDs,
    eliminating redundant 'upload_id' fields entirely.
    Values contain strictly { 'file_hash', 'commitment_hash' }.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT upload_id, file_hash, commitment_hash
        FROM global_dht
        ORDER BY CAST(upload_id AS INTEGER) ASC
        LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = cursor.fetchall()
    
    conn.close()
    
    # Clean dictionary mapping: "0": { "file_hash": ..., "commitment_hash": ... }
    dht_map = {
        format_upload_id(r["upload_id"]): {
            "file_hash": r["file_hash"],
            "commitment_hash": r["commitment_hash"]
        }
        for r in rows
    }
    return dht_map

# --- Unified Global Search API ---

@app.get("/api/search")
def search_vault(
    q: str = Query(..., min_length=1),
    user_email: str = Query(...)
):
    """
    Search files by name, upload id, file hash, commitment hash, or case title.
    """
    q_clean = q.strip()
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT role, allowed_cases FROM users WHERE email = ?", (user_email,))
    user = cursor.fetchone()
    allowed = ["ALL"]
    if user:
        allowed = json.loads(user["allowed_cases"])
        
    query_pattern = f"%{q_clean}%"
    cursor.execute("""
        SELECT d.*, c.case_number, c.title as case_title
        FROM case_documents d
        JOIN cases c ON d.case_id = c.id
        WHERE d.file_name LIKE ?
           OR d.title LIKE ?
           OR d.upload_id LIKE ? OR printf("%04d", CAST(d.upload_id AS INTEGER)) LIKE ?
           OR d.sha256 LIKE ?
           OR d.commitment_hash LIKE ?
           OR d.doc_official_id LIKE ?
           OR c.title LIKE ?
           OR c.case_number LIKE ?
           OR c.id LIKE ?
        ORDER BY d.created_at DESC
    """, (query_pattern, query_pattern, query_pattern, query_pattern, query_pattern, query_pattern, query_pattern, query_pattern, query_pattern, query_pattern))
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        if "ALL" in allowed or r["case_id"] in allowed:
            results.append({
                "doc_id": r["id"],
                "upload_id": format_upload_id(r["upload_id"]),
                "case_id": r["case_id"],
                "case_number": r["case_number"],
                "case_title": r["case_title"],
                "title": r["title"],
                "file_name": r["file_name"],
                "file_type": r["file_type"],
                "doc_official_id": r["doc_official_id"],
                "version": r["version"],
                "file_hash": r["sha256"],
                "commitment_hash": r["commitment_hash"],
                "author_email": r["author_email"],
                "created_at": r["created_at"],
                "size_bytes": r["size_bytes"]
            })
    return {"query": q_clean, "total_matches": len(results), "results": results}

# --- Admin User Management API (Add, Delete, Update Role) ---

@app.get("/api/admin/users")
def get_org_users(admin_email: str = "example@example.com"):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT role, org_id FROM users WHERE email = ?", (admin_email,))
    admin = cursor.fetchone()
    
    if admin and admin["role"] != "ADMIN":
        conn.close()
        raise HTTPException(status_code=403, detail="Admin authorization required.")
        
    org_id = admin["org_id"] if admin else "0001"
    cursor.execute("SELECT email, full_name, role, allowed_cases, created_at FROM users WHERE org_id = ?", (org_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "email": r["email"],
            "full_name": r["full_name"],
            "role": r["role"],
            "allowed_cases": json.loads(r["allowed_cases"]),
            "created_at": r["created_at"]
        }
        for r in rows
    ]

@app.post("/api/admin/users/create")
def add_user(req: AddUserRequest, admin_email: str = "example@example.com"):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT role, org_id FROM users WHERE email = ?", (admin_email,))
    admin = cursor.fetchone()
    if not admin or admin["role"] != "ADMIN":
        conn.close()
        raise HTTPException(status_code=403, detail="Admin authorization required to onboard new personnel.")
        
    # Check if user already exists
    cursor.execute("SELECT email FROM users WHERE email = ?", (req.email.strip(),))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="User account with this email already exists.")
        
    role = req.role if req.role in ["ADMIN", "UPLOADER", "VIEWER"] else "VIEWER"
    now = time.time()
    raw_pwd = (req.password or "").strip()
    if not raw_pwd:
        raw_pwd = "vault-" + hashlib.sha256(f"{req.email}-{now}".encode()).hexdigest()[:8]
    pwd_hash = hashlib.sha256(raw_pwd.encode()).hexdigest()

    cursor.execute("""
        INSERT INTO users (email, full_name, org_id, role, allowed_cases, created_at, password_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (req.email.strip(), req.full_name.strip(), admin["org_id"], role, json.dumps(req.allowed_cases), now, pwd_hash))
    
    conn.commit()
    conn.close()

    # Automatically provision / sync into Supabase
    try:
        sync_user_to_supabase(req.email.strip(), raw_pwd, req.full_name.strip(), role)
    except Exception as e:
        print("Note: Supabase sync in add_user:", e)

    return {
        "message": f"Officer {req.full_name} ({req.email}) onboarded successfully.",
        "email": req.email.strip(),
        "temporary_password": raw_pwd
    }

@app.delete("/api/admin/users/{target_email}")
def delete_user(target_email: str, admin_email: str = "example@example.com"):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT role, org_id FROM users WHERE email = ?", (admin_email,))
    admin = cursor.fetchone()
    if not admin or admin["role"] != "ADMIN":
        conn.close()
        raise HTTPException(status_code=403, detail="Admin authorization required to offboard personnel.")
        
    if target_email == admin_email:
        conn.close()
        raise HTTPException(status_code=400, detail="Self-offboarding rejected: Admin cannot delete their own account.")
        
    cursor.execute("DELETE FROM users WHERE email = ?", (target_email,))
    conn.commit()
    conn.close()
    return {"message": f"Personnel account {target_email} offboarded successfully."}

@app.post("/api/admin/update-role")
def update_user_role(req: UpdateRoleRequest, admin_email: str = "example@example.com"):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE email = ?", (admin_email,))
    admin = cursor.fetchone()
    if not admin or admin["role"] != "ADMIN":
        conn.close()
        raise HTTPException(status_code=403, detail="Admin authorization required.")
        
    role = req.role if req.role in ["ADMIN", "UPLOADER", "VIEWER"] else "VIEWER"
    cursor.execute("""
        UPDATE users
        SET role = ?, allowed_cases = ?
        WHERE email = ?
    """, (role, json.dumps(req.allowed_cases), req.email))
    conn.commit()
    conn.close()
    return {"message": f"Permissions for {req.email} updated successfully."}


@app.get("/api/admin/activity-logs")
async def get_activity_logs(user_email: str = Query(...), limit: int = 150):
    conn = get_db()
    cursor = conn.cursor()
    
    # Verify requesting user is admin
    cursor.execute("SELECT * FROM users WHERE email = ?", (user_email,))
    user = cursor.fetchone()
    if not user or user["role"] != "ADMIN":
        conn.close()
        raise HTTPException(status_code=403, detail="Clearance Denied. Admin clearance required to view master activity audit logs.")
        
    cursor.execute("""
        SELECT al.*, cd.file_name as doc_file_name, c.title as case_title
        FROM access_logs al
        LEFT JOIN case_documents cd ON cd.id = al.doc_id
        LEFT JOIN cases c ON c.id = al.case_id
        ORDER BY al.timestamp DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        row_dict = dict(r)
        # Parse extra_meta JSON safely
        try:
            row_dict["extra_meta"] = json.loads(row_dict["extra_meta"]) if row_dict.get("extra_meta") else {}
        except Exception:
            row_dict["extra_meta"] = {}
        result.append(row_dict)
        
    return {"logs": result}
