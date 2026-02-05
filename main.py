from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, os, time, json
from collections import Counter

# =========================
# Storage (Render Free-safe)
# =========================
DB_DIR = os.getenv("DB_DIR", "/tmp")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "survey.db")

# =========================
# CORS
# =========================
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

# =========================
# Root route
# =========================
@app.get("/", response_class=HTMLResponse)
def root():
    return """
<!doctype html>
<html lang="ar" dir="rtl">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>qanun survey api</title>
    <style>
      body{font-family:system-ui,-apple-system,"Segoe UI",Tahoma,Arial,sans-serif;margin:24px;line-height:1.8}
      a{display:block;margin:8px 0}
      code{background:#f5f5f5;padding:2px 6px;border-radius:6px}
    </style>
  </head>
  <body>
    <h2>qanun survey api ✅</h2>
    <p>روابط سريعة:</p>
    <a href="/health">/health</a>
    <a href="/docs">/docs</a>
    <a href="/admin">/admin</a>
    <p>إذا كنت تشغّل Frontend خارجي، تأكد أن <code>FRONTEND_ORIGIN</code> مضبوط.</p>
  </body>
</html>
"""

@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)

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

# =========================
# Admin APIs (بدون كلمة سر)
# =========================
@app.post("/admin/list")
async def admin_list():
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
        except Exception:
            payload = {"raw": payload_str}
        out.append({"id": rid, "created_at": ts, "payload": payload})
    return {"rows": out}

@app.post("/admin/summary")
async def admin_summary():
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
        except Exception:
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

# =========================
# Admin UI (بدون كلمة سر)
# =========================
@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return """
<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>qanun | Admin</title>

  <style>
    :root{
      --gold-1:#d7b24a; --gold-2:#b88d2e; --gold-3:#a9791f;
      --ink:#141414; --muted:#575757;
      --card: rgba(255,255,255,.92);
      --shadow: 0 18px 50px rgba(0,0,0,.18);
      --radius: 18px;
      --stroke: rgba(17,17,17,.10);
    }
    *{box-sizing:border-box}
    body{
      margin:0;
      font-family: system-ui, -apple-system, "Segoe UI", Tahoma, Arial, sans-serif;
      color:var(--ink);
      min-height:100vh;
      background:
        radial-gradient(900px 500px at 50% 5%, rgba(255,255,255,.35), transparent 60%),
        linear-gradient(180deg, var(--gold-1) 0%, var(--gold-2) 55%, var(--gold-3) 100%);
      padding:24px;
    }
    .wrap{max-width:1200px;margin:0 auto;display:grid;gap:14px}
    .topbar{
      background: rgba(255,255,255,.14);
      border: 1px solid rgba(255,255,255,.25);
      border-radius: var(--radius);
      padding: 16px;
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      box-shadow: var(--shadow);
      color:#fff;
      display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;
    }
    .brand{display:flex;align-items:center;gap:12px}
    .logo{
      width:46px;height:46px;border-radius:14px;background:rgba(255,255,255,.95);
      display:flex;align-items:center;justify-content:center;box-shadow:0 10px 25px rgba(0,0,0,.18);
    }
    .logo svg{width:28px;height:28px;fill:none;stroke:#c28d12;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}
    h1{margin:0;font-size:18px}
    .small{margin:0;opacity:.95;font-size:12px;line-height:1.6}

    .grid{
      display:grid;
      grid-template-columns: 1.15fr .85fr;
      gap: 14px;
      align-items:start;
    }
    @media (max-width: 980px){ .grid{grid-template-columns:1fr} }

    .card{
      background: var(--card);
      border: 1px solid rgba(255,255,255,.55);
      border-radius: var(--radius);
      padding: 16px;
      box-shadow: var(--shadow);
    }
    .card h2{margin:0 0 10px;font-size:16px}
    .muted{color:var(--muted);font-size:12px;line-height:1.7;margin:0}
    .row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
    @media (max-width: 820px){ .row{grid-template-columns:1fr} }

    .kpi{
      border:1px solid var(--stroke);
      border-radius: 16px;
      padding: 14px;
      background: rgba(255,255,255,.75);
    }
    .kpi .label{font-size:12px;color:var(--muted)}
    .kpi .value{font-size:26px;font-weight:900;margin-top:6px}
    .kpi .sub{font-size:12px;color:var(--muted);margin-top:4px}

    button{
      margin-top:10px;
      padding: 11px 12px;
      border-radius: 14px;
      border:0;
      cursor:pointer;
      font-weight:900;
      color:#1b1406;
      background: linear-gradient(90deg, #f3d27a, #d8aa3c, #c38a16);
      box-shadow: 0 12px 22px rgba(0,0,0,.12);
    }
    .msg{
      margin-top:10px;
      padding: 10px 12px;
      border-radius: 14px;
      display:none;
      font-size:12px;
      line-height:1.7;
    }
    .msg.err{display:block;background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.25);color:#5a1212}
    .msg.ok{display:block;background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.25);color:#0f3d20}

    .charts{
      display:grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    @media (max-width: 980px){ .charts{grid-template-columns:1fr} }
    .chartBox{
      border:1px solid var(--stroke);
      border-radius: 16px;
      padding: 12px;
      background: rgba(255,255,255,.78);
    }
    .chartTitle{margin:0 0 8px;font-size:13px;font-weight:900}

    table{width:100%;border-collapse:collapse;margin-top:10px}
    th,td{border:1px solid rgba(17,17,17,.10);padding:10px;vertical-align:top;text-align:right;font-size:12px}
    th{background:rgba(0,0,0,.04);font-weight:900}
    pre{margin:0;white-space:pre-wrap;word-break:break-word}
  </style>

  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>

<body>
  <div class="wrap">
    <div class="topbar">
      <div class="brand">
        <div class="logo" aria-hidden="true">
          <svg viewBox="0 0 24 24">
            <path d="M12 3v18"></path>
            <path d="M4 21h16"></path>
            <path d="M6 7h12"></path>
            <path d="M7 7l-3 6h6l-3-6z"></path>
            <path d="M17 7l-3 6h6l-3-6z"></path>
          </svg>
        </div>
        <div>
          <h1>qanun — لوحة الإدارة</h1>
          <p class="small">بدون كلمة مرور (أي شخص يملك الرابط يستطيع رؤية البيانات)</p>
        </div>
      </div>
      <div class="small" id="statusText">غير متصل بعد</div>
    </div>

    <div class="grid">
      <div class="card">
        <h2>لوحة الإحصائيات</h2>
        <p class="muted">اضغط “تحميل” لقراءة الملخص والردود.</p>

        <button id="loadBtn">تحميل</button>
        <div id="msg" class="msg err"></div>

        <div class="row" style="margin-top:12px">
          <div class="kpi">
            <div class="label">عدد الاستبيانات</div>
            <div class="value" id="kpiTotal">—</div>
            <div class="sub" id="kpiUpdated">—</div>
          </div>
          <div class="kpi">
            <div class="label">أكثر تقييم للتطبيق</div>
            <div class="value" style="font-size:18px" id="kpiTopRating">—</div>
            <div class="sub" id="kpiTopRatingCount">—</div>
          </div>
          <div class="kpi">
            <div class="label">هل سيستخدم التطبيق؟</div>
            <div class="value" style="font-size:18px" id="kpiWillUse">—</div>
            <div class="sub" id="kpiWillUseCount">—</div>
          </div>
        </div>

        <div class="charts" style="margin-top:12px">
          <div class="chartBox">
            <p class="chartTitle">توزيع العمر</p>
            <canvas id="chartAge"></canvas>
          </div>
          <div class="chartBox">
            <p class="chartTitle">تقييم التطبيق</p>
            <canvas id="chartRating"></canvas>
          </div>
          <div class="chartBox">
            <p class="chartTitle">استخدام التطبيق مستقبلًا</p>
            <canvas id="chartWillUse"></canvas>
          </div>
          <div class="chartBox">
            <p class="chartTitle">أكثر أسباب الاستخدام/عدم الاستخدام</p>
            <canvas id="chartWhy"></canvas>
          </div>
          <div class="chartBox">
            <p class="chartTitle">مصادر الذكاء الاصطناعي المفضلة</p>
            <canvas id="chartAiSources"></canvas>
          </div>
          <div class="chartBox">
            <p class="chartTitle">الثقة بإجابات الذكاء الاصطناعي</p>
            <canvas id="chartAiTrust"></canvas>
          </div>
        </div>
      </div>

      <div class="card">
        <h2>آخر الردود (أحدث 200)</h2>
        <p class="muted">يعرض البيانات الخام لكل رد (JSON).</p>
        <div id="tableWrap" class="muted" style="margin-top:10px">لم يتم التحميل بعد.</div>
      </div>
    </div>
  </div>

<script>
  const API = location.origin;

  const statusText = document.getElementById("statusText");
  const msg = document.getElementById("msg");

  const kpiTotal = document.getElementById("kpiTotal");
  const kpiUpdated = document.getElementById("kpiUpdated");
  const kpiTopRating = document.getElementById("kpiTopRating");
  const kpiTopRatingCount = document.getElementById("kpiTopRatingCount");
  const kpiWillUse = document.getElementById("kpiWillUse");
  const kpiWillUseCount = document.getElementById("kpiWillUseCount");

  const tableWrap = document.getElementById("tableWrap");

  let charts = [];

  function showError(t){
    msg.className = "msg err";
    msg.textContent = t;
    msg.style.display = "block";
  }
  function showOk(t){
    msg.className = "msg ok";
    msg.textContent = t;
    msg.style.display = "block";
  }
  function clearMsg(){ msg.style.display = "none"; msg.textContent = ""; }

  function destroyCharts(){
    charts.forEach(c => c.destroy());
    charts = [];
  }

  function topOf(labels, values){
    if(!labels || labels.length===0) return ["—", 0];
    let maxIdx = 0;
    for(let i=1;i<values.length;i++) if(values[i] > values[maxIdx]) maxIdx = i;
    return [labels[maxIdx], values[maxIdx]];
  }

  function makeBar(canvasId, labels, values){
    const ctx = document.getElementById(canvasId);
    return new Chart(ctx, {
      type: "bar",
      data: { labels, datasets: [{ label: "عدد", data: values }]},
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } }
      }
    });
  }

  function makePie(canvasId, labels, values){
    const ctx = document.getElementById(canvasId);
    return new Chart(ctx, {
      type: "pie",
      data: { labels, datasets: [{ data: values }]},
      options: { responsive: true, plugins: { legend: { position: "bottom" } } }
    });
  }

  async function postJSON(path){
    const res = await fetch(API + path, {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({})
    });
    const data = await res.json().catch(()=> ({}));
    if(!res.ok) throw new Error(data.detail || "Request failed");
    return data;
  }

  function renderTable(rows){
    if(!rows || rows.length===0){
      tableWrap.innerHTML = "لا توجد ردود بعد.";
      return;
    }
    let html = `<table>
      <thead><tr><th>ID</th><th>الوقت</th><th>البيانات</th></tr></thead><tbody>`;
    for(const r of rows){
      const t = new Date((r.created_at||0)*1000).toLocaleString();
      const payload = JSON.stringify(r.payload, null, 2);
      html += `<tr>
        <td>${r.id}</td>
        <td>${t}</td>
        <td><pre>${payload}</pre></td>
      </tr>`;
    }
    html += `</tbody></table>`;
    tableWrap.innerHTML = html;
  }

  document.getElementById("loadBtn").onclick = async () => {
    try{
      clearMsg();
      statusText.textContent = "جاري التحميل...";

      const summary = await postJSON("/admin/summary");
      const total = summary.total || 0;

      const list = await postJSON("/admin/list");
      const rows = list.rows || [];

      kpiTotal.textContent = total;
      kpiUpdated.textContent = "آخر تحديث: " + new Date().toLocaleString();

      const r = summary.single.app_rating || {labels:[], values:[]};
      const [rt, rcount] = topOf(r.labels, r.values);
      kpiTopRating.textContent = rt;
      kpiTopRatingCount.textContent = "عدد: " + rcount;

      const wu = summary.single.will_use || {labels:[], values:[]};
      const [wut, wuc] = topOf(wu.labels, wu.values);
      kpiWillUse.textContent = wut;
      kpiWillUseCount.textContent = "عدد: " + wuc;

      destroyCharts();

      const age = summary.single.age || {labels:[], values:[]};
      charts.push(makeBar("chartAge", age.labels, age.values));

      charts.push(makePie("chartRating", r.labels, r.values));
      charts.push(makePie("chartWillUse", wu.labels, wu.values));

      const why = summary.multi.why_use || {labels:[], values:[]};
      charts.push(makeBar("chartWhy", why.labels, why.values));

      const ais = summary.single.ai_sources_pref || {labels:[], values:[]};
      charts.push(makePie("chartAiSources", ais.labels, ais.values));

      const ait = summary.single.ai_trust || {labels:[], values:[]};
      charts.push(makeBar("chartAiTrust", ait.labels, ait.values));

      renderTable(rows);

      statusText.textContent = "تم التحميل بنجاح";
      showOk("تم تحميل الملخص والردود.");
    }catch(e){
      statusText.textContent = "فشل التحميل";
      showError("خطأ: " + e.message);
    }
  };
</script>

</body>
</html>
"""
