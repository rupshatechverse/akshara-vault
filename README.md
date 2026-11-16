# Akshara Vault

A Sovereign, Quantum-Resilient Digital Document Management System for courts, law enforcement, sensitive government archives, and regulated enterprise.

## Project Structure

```
akshara-vault/
├── backend/                  # FastAPI REST API & Ledger Storage
│   ├── main.py               # Multi-Case & RBAC API endpoints & ledger database
│   ├── akshara_vault.db      # SQLite immutable ledger database
│   ├── requirements.txt      # Python dependencies
│   ├── storage/              # Encrypted document storage payloads
│   └── venv/                 # Python virtual environment
├── frontend/                 # Client Application Only
│   ├── index.html            # Public sovereign landing page & portal login
│   ├── dashboard.html        # Organization Custodial Workspace (Multi-Case & RBAC)
│   ├── style.css             # Institutional design system & styling
│   ├── script.js             # Client-side WebCrypto RAM AES & UI interactions
│   └── config.js             # Supabase credentials & project configuration
├── run.sh                    # Unified 1-click startup script
└── README.md
```

## Quick Start

To launch both the backend API and open the client in your browser:

```bash
./run.sh
```

Or run manually:

```bash
# 1. Start backend
./backend/venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 2. Open frontend
xdg-open frontend/index.html
```

## Features

1. **Organization-Level Architecture**:
   - Manages multiple institutional cases under the agency (e.g. Central Bureau of Investigation - Special Crimes Division).
   - Drill down into any case to inspect anchored documents or ingest new chain-of-custody evidence.
2. **Fine-Grained Role-Based Access Control (RBAC)**:
   - **ADMIN**: Full authority, case registration, document uploading, and permission delegation.
   - **INVESTIGATOR**: Case registration, document ingestion, and inspection across authorized cases.
   - **FORENSIC SCIENTIST**: Specialized evidence upload and sector dump hashing for assigned cases.
   - **AUDITOR**: Read-only cross-ledger audit verification.
   - **VIEWER**: Strict read-only clearance on assigned cases.
3. **Case-Specific Clearance Limits**:
   - Organization Admins can scope an officer to `All Cases` or restrict clearance to individual cases via the Admin panel.
4. **Zero-Knowledge Client RAM**:
   - AES keys are derived strictly in client browser RAM using WebCrypto API without transmitting raw keys over the wire.
5. **Supabase Auth**:
   - Integrated with Supabase Auth
