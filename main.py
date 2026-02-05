from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, os, time, json
from collections import Counter

# =========================
# Storage (Render Free-safe)
# =========================
# على Render Free لا تستخدم /var/data (يحتاج Persistent Disk)
# استخدم /tmp (قابل للكتابة) لكن البيانات قد تنحذف عند restart/deploy
DB_DIR = os.getenv("DB_DIR", "/tmp")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "survey.db")

# =========================
# Admin password (ENV)
# =========================
# ضعها في Render -> Environment Variables:
# ADMIN_PASSWORD = كلمة_قوية
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# =========================
# CORS
# =========================
# عند النشر: حدد دومين موقعك فقط عبر FRONTEND_ORIGIN
# مثال: https://username.github.io
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")

app = FastAPI(title="qanun survey api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN] if FRONTEND_ORIGIN != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at INTEGER NOT NULL,
        payload TEXT NOT NULL
      )
    """)
    return conn

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/submit")
async def submit(request: Request):
    body = await request.json()
    payload = body.get("payload")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be an object")

    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO responses(created_at, payload) VALUES (?, ?)",
            (int(time.time()), json.dumps(payload, ensure_ascii=False))
        )
        conn.commit()
    finally:
        conn.close()

    return {"status": "saved"}

def _require_admin(body: dict):
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=500, detail="ADMIN_PASSWORD is not set on server")
    if body.get("password") != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/admin/list")
async def admin_list(request: Request):
    body = await request.json()
    _require_admin(body)

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, created_at, payload FROM responses ORDER BY id DESC LIMIT 200")
        rows = cur.fetchall()
    finally:
        conn.close()

    out = []
    for rid, ts, payload_str in rows:
        try:
            payload = json.loads(payload_str)
        except:
            payload = {"raw": payload_str}
        out.append({"id": rid, "created_at": ts, "payload": payload})
    return {"rows": out}

@app.post("/admin/summary")
async def admin_summary(request: Request):
    body = await request.json()
    _require_admin(body)

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT payload FROM responses")
        payload_rows = cur.fetchall()
    finally:
        conn.close()

    single_fields = [
        "age", "app_rating", "will_use", "legal_status",
        "ai_use_work", "ai_sources_pref", "ai_trust", "ai_feature", "ai_disclaimer"
    ]
    multi_fields = ["why_use", "signup", "payment"]

    counters = {f: Counter() for f in single_fields}
    multi_counters = {f: Counter() for f in multi_fields}

    total = 0
    for (payload_str,) in payload_rows:
        try:
            p = json.loads(payload_str)
        except:
            continue

        total += 1

        for f in single_fields:
            v = p.get(f)
            if isinstance(v, str) and v.strip():
                counters[f][v.strip()] += 1

        for f in multi_fields:
            v = p.get(f)
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, str) and item.strip():
                        multi_counters[f][item.strip()] += 1

    def counter_to_labels_values(c: Counter):
        items = c.most_common()
        return {"labels": [k for k, _ in items], "values": [v for _, v in items]}

    summary = {
        "total": total,
        "single": {f: counter_to_labels_values(counters[f]) for f in single_fields},
        "multi":  {f: counter_to_labels_values(multi_counters[f]) for f in multi_fields},
    }
    return summary

@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return "<h1>Admin UI موجود عندك في النسخة الكاملة السابقة</h1>"
