#!/usr/bin/env python3
"""
generate_dashboard.py
Jala datos de HubSpot y genera index.html para el dashboard de ventas Legalario.
Corre automáticamente cada hora via GitHub Actions.
"""

import os, json, urllib.request, urllib.parse
from datetime import datetime, timezone

TOKEN = os.environ.get("HUBSPOT_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
BASE    = "https://api.hubapi.com"

# ── Configuración del equipo ──
OWNERS = {
    "38239642":  "Ernesto",
    "79533376":  "Rossana",
    "372683861": "Karla",
    "480423184": "Ilse",
    "392741743": "Diego",
}
METAS_Q1    = {"Ernesto":1300000,"Karla":1100000,"Rossana":750000,"Ilse":650000,"Diego":0}
METAS_ANUAL = {"Ernesto":5200000,"Karla":4400000,"Rossana":3000000,"Ilse":2600000,"Diego":0}
META_EQ1, META_EA = 3000000, 12000000

# Stage IDs
CW_STAGES   = {"69056626","155228448"}
SQO_STAGE   = "69056624"
NEG_STAGE   = "69056625"
VERB_STAGE  = "69038107"
SIGN_STAGE  = "94757149"
DEMO_STAGE  = "69755427"

def hs_post(path, payload):
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(f"{BASE}{path}", data=data, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def search_deals(filters, props, limit=200, after=None):
    payload = {"filterGroups":[{"filters":filters}],"properties":props,"limit":limit}
    if after: payload["after"] = after
    return hs_post("/crm/v3/objects/deals/search", payload)

def get_all(filters, props):
    results, after = [], None
    while True:
        resp = search_deals(filters, props, after=after)
        results += resp.get("results", [])
        paging = resp.get("paging",{}).get("next",{})
        after  = paging.get("after")
        if not after: break
    return results

def amt(d):
    try: return float(d.get("properties",{}).get("amount") or 0)
    except: return 0

def owner(d):
    return OWNERS.get(d.get("properties",{}).get("hubspot_owner_id",""), "")

print("Jalando datos de HubSpot...")

# ── 1. Close Won Q1 ──
cw_deals = get_all([
    {"propertyName":"tipo_de_cuenta","operator":"EQ","value":"New Logo"},
    {"propertyName":"dealstage","operator":"IN","values":list(CW_STAGES)},
    {"propertyName":"closedate","operator":"GTE","value":"2026-01-01"},
    {"propertyName":"closedate","operator":"LTE","value":"2026-03-31"},
    {"propertyName":"hubspot_owner_id","operator":"IN","values":list(OWNERS.keys())},
], ["dealname","amount","hubspot_owner_id","closedate"])

cw = {n:0 for n in OWNERS.values()}
for d in cw_deals:
    n = owner(d)
    if n: cw[n] += amt(d)

print(f"CW total: ${sum(cw.values()):,.0f}")

# ── 2. Pipeline activo por stage ──
pipe_deals = get_all([
    {"propertyName":"tipo_de_cuenta","operator":"EQ","value":"New Logo"},
    {"propertyName":"dealstage","operator":"IN","values":[SQO_STAGE,NEG_STAGE,VERB_STAGE,SIGN_STAGE,DEMO_STAGE]},
    {"propertyName":"hubspot_owner_id","operator":"IN","values":list(OWNERS.keys())},
], ["dealname","amount","dealstage","hubspot_owner_id"])

sqo={n:0 for n in OWNERS.values()}
neg={n:0 for n in OWNERS.values()}
demo={n:0 for n in OWNERS.values()}
verb={n:0 for n in OWNERS.values()}
sign={n:0 for n in OWNERS.values()}
fc_deals_list = []

for d in pipe_deals:
    n  = owner(d)
    if not n: continue
    st = d["properties"].get("dealstage","")
    a  = amt(d)
    nm = d["properties"].get("dealname","")
    if st == SQO_STAGE:  sqo[n]  += a
    elif st == NEG_STAGE: neg[n] += a
    elif st == DEMO_STAGE: demo[n]+= a
    elif st == VERB_STAGE:
        verb[n] += a
        fc_deals_list.append({"d":nm,"a":a,"ae":n,"stage":"verbal"})
    elif st == SIGN_STAGE:
        sign[n] += a
        fc_deals_list.append({"d":nm,"a":a,"ae":n,"stage":"sign"})

fc_deals_list.sort(key=lambda x:-x["a"])
print(f"Forecast deals: {len(fc_deals_list)}, total: ${sum(x['a'] for x in fc_deals_list):,.0f}")

# ── 3. SQOs Q1 via sqo_date ──
sqo_q1_count = {n:0 for n in OWNERS.values()}
sqo_q1_arr   = {n:0 for n in OWNERS.values()}

for oid in OWNERS:
    deals = get_all([
        {"propertyName":"hubspot_owner_id","operator":"EQ","value":oid},
        {"propertyName":"sqo_date","operator":"GTE","value":"2026-01-01"},
        {"propertyName":"sqo_date","operator":"LTE","value":"2026-03-31"},
    ], ["dealname","amount","sqo_date"])
    n = OWNERS[oid]
    sqo_q1_count[n] = len(deals)
    sqo_q1_arr[n]   = sum(amt(d) for d in deals)
    print(f"  {n}: {sqo_q1_count[n]} SQOs, ARR=${sqo_q1_arr[n]:,.0f}")

# ── 4. Plan Web (Ilse) ──
pw_deals = get_all([
    {"propertyName":"hubspot_owner_id","operator":"EQ","value":"480423184"},
    {"propertyName":"dealstage","operator":"IN","values":list(CW_STAGES)},
    {"propertyName":"closedate","operator":"GTE","value":"2026-01-01"},
    {"propertyName":"closedate","operator":"LTE","value":"2026-03-31"},
], ["dealname","amount","tipo_de_cuenta","closedate"])

pw_nl, pw_bi = [], []
for d in pw_deals:
    tc = d["properties"].get("tipo_de_cuenta","")
    a  = amt(d)
    nm = d["properties"].get("dealname","")
    cd = d["properties"].get("closedate","")
    mes = "Ene" if "-01-" in cd else "Feb" if "-02-" in cd else "Mar"
    if tc == "Base Instalada":
        pw_bi.append({"d":nm,"a":a,"m":mes})
    else:
        pw_nl.append({"d":nm,"a":a,"m":mes})

pw_nl.sort(key=lambda x:-x["a"])
pw_bi.sort(key=lambda x:-x["a"])
pw_total_nl = sum(x["a"] for x in pw_nl)
pw_total_bi = sum(x["a"] for x in pw_bi)
pw_total    = pw_total_nl + pw_total_bi
print(f"Plan Web: NL=${pw_total_nl:,.0f} BI=${pw_total_bi:,.0f} TOTAL=${pw_total:,.0f}")

# ── Cálculos globales ──
names     = ["Ernesto","Karla","Rossana","Diego","Ilse"]
total_cw  = sum(cw.values())
total_sqo = sum(sqo.values())
total_neg = sum(neg.values())
total_demo= sum(demo.values())
total_verb= sum(verb.values())
total_sign= sum(sign.values())
total_fc  = total_verb + total_sign
total_pipe= total_sqo+total_neg+total_demo+total_verb+total_sign
total_sqo_q1_count = sum(sqo_q1_count.values())
total_sqo_q1_arr   = sum(sqo_q1_arr.values())
ticket_prom = int(total_sqo_q1_arr/total_sqo_q1_count) if total_sqo_q1_count else 0
update_time = datetime.now(timezone.utc).strftime("%-d %b %Y %H:%M UTC").replace("UTC","UTC")
update_date = datetime.now(timezone.utc).strftime("%-d %b %Y")

def js_arr(obj):
    return "{" + ",".join(f"{k}:{int(v)}" for k,v in obj.items()) + "}"

def fmt_js(v):
    if v >= 1_000_000: return f"${v/1_000_000:.2f}M"
    return f"${v/1000:.0f}K"

q1_pct    = round(total_cw/META_EQ1*100)
annual_pct= round(total_cw/META_EA*100)
cwf_pct   = round((total_cw+total_fc)/META_EA*100)
pw_q1_pct = round(pw_total/250000*100)
pw_ann_pct= round(pw_total/1000000*100)

fc_deals_js = json.dumps(fc_deals_list, ensure_ascii=False)
pw_nl_js    = json.dumps(pw_nl, ensure_ascii=False)
pw_bi_js    = json.dumps(pw_bi, ensure_ascii=False)

print("Generando index.html...")

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sales Dashboard — Legalario 2026</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
  :root{{--bg:#f0f4f8;--bg2:#ffffff;--bg3:#e4ecf4;--bg4:#d5e2ee;--border:rgba(30,80,140,0.10);--border2:rgba(30,80,140,0.18);--text:#0d1f3c;--text2:#2c4a6e;--text3:#6b8aaa;--green:#0e8a5f;--green-bg:rgba(14,138,95,0.09);--amber:#b86e00;--amber-bg:rgba(184,110,0,0.09);--red:#b03030;--red-bg:rgba(176,48,48,0.09);--blue:#1a56c4;--blue-bg:rgba(26,86,196,0.09);--purple:#5b3fb5;--purple-bg:rgba(91,63,181,0.09);--teal:#0b7a6a;--teal-bg:rgba(11,122,106,0.09);--font:'Plus Jakarta Sans',sans-serif;--mono:'DM Mono',monospace;}}
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:var(--font);background:var(--bg);color:var(--text);min-height:100vh;}}

  /* ── LOGIN ── */
  #login-screen{{position:fixed;inset:0;background:var(--bg);display:flex;align-items:center;justify-content:center;z-index:9999;}}
  .login-box{{background:var(--bg2);border:1px solid var(--border);border-radius:16px;padding:2.5rem 2rem;width:340px;box-shadow:0 4px 24px rgba(30,80,140,0.10);text-align:center;}}
  .login-logo{{font-size:15px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--text);margin-bottom:1.5rem;}}
  .login-box h2{{font-size:18px;font-weight:600;margin-bottom:.4rem;}}
  .login-box p{{font-size:13px;color:var(--text3);margin-bottom:1.5rem;}}
  .login-box input{{width:100%;padding:.75rem 1rem;border:1px solid var(--border);border-radius:8px;font-family:var(--font);font-size:14px;background:var(--bg3);color:var(--text);outline:none;margin-bottom:.75rem;}}
  .login-box input:focus{{border-color:var(--blue);}}
  .login-btn{{width:100%;padding:.75rem;background:var(--blue);color:#fff;border:none;border-radius:8px;font-family:var(--font);font-size:14px;font-weight:600;cursor:pointer;}}
  .login-btn:hover{{background:#1445a0;}}
  .login-error{{font-size:12px;color:var(--red);margin-top:.5rem;display:none;}}

  /* ── TOPBAR ── */
  .topbar{{position:sticky;top:0;z-index:100;background:rgba(240,244,248,.96);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;padding:0 2rem;height:56px;}}
  .brand{{font-size:14px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--text);}}
  .live-badge{{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--green);}}
  .live-dot{{width:6px;height:6px;border-radius:50%;background:var(--green);animation:pulse 2s infinite;}}
  @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
  .date-badge{{font-size:11px;color:var(--text3);font-family:var(--mono);background:var(--bg3);padding:4px 10px;border-radius:6px;border:1px solid var(--border);}}
  .main{{max-width:1280px;margin:0 auto;padding:2rem;}}
  .tabs{{display:flex;gap:2px;margin-bottom:1.75rem;background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:4px;width:fit-content;}}
  .tab{{font-size:13px;padding:6px 18px;border-radius:7px;cursor:pointer;color:var(--text2);background:transparent;border:none;font-family:var(--font);transition:all .2s;}}
  .tab.active{{background:var(--bg2);color:var(--text);font-weight:600;box-shadow:0 1px 3px rgba(30,80,140,0.08);}}
  .view{{display:none;}}.view.active{{display:block;}}
  .metrics{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:1.5rem;}}
  .mc{{background:var(--bg2);border:1px solid var(--border);border-radius:14px;padding:1.1rem 1.25rem;box-shadow:0 2px 8px rgba(30,80,140,0.06);}}
  .mc-lbl{{font-size:11px;color:var(--text3);margin-bottom:6px;text-transform:uppercase;letter-spacing:.06em;font-weight:500;}}
  .mc-val{{font-size:23px;font-weight:700;letter-spacing:-.02em;}}
  .mc-sub{{font-size:11px;margin-top:4px;color:var(--text2);}}
  .section{{background:var(--bg2);border:1px solid var(--border);border-radius:14px;padding:1.25rem 1.5rem;margin-bottom:1.25rem;box-shadow:0 2px 8px rgba(30,80,140,0.06);}}
  .sec-title{{font-size:13px;font-weight:600;color:var(--text);margin-bottom:1.1rem;letter-spacing:.03em;text-transform:uppercase;}}
  .q-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:1.25rem;}}
  .q-card{{background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:.9rem 1rem;}}
  .q-lbl{{font-size:10px;color:var(--text3);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;}}
  .q-val{{font-size:18px;font-weight:700;margin-bottom:2px;}}
  .q-sub{{font-size:11px;color:var(--text2);margin-bottom:8px;}}
  .q-bar-bg{{background:var(--bg4);border-radius:3px;height:4px;}}
  .q-bar-fill{{height:4px;border-radius:3px;}}
  .ab-wrap{{margin-top:1rem;}}
  .ab-top{{display:flex;justify-content:space-between;font-size:11px;color:var(--text2);margin-bottom:5px;font-family:var(--mono);}}
  .ab-bg{{background:var(--bg4);border-radius:6px;height:16px;position:relative;}}
  .ab-fill{{height:16px;border-radius:6px;background:var(--blue);}}
  .ab-m{{position:absolute;top:-5px;height:26px;width:1.5px;border-radius:1px;background:rgba(176,48,48,.4);}}
  .ab-ticks{{display:flex;justify-content:space-between;font-size:10px;color:var(--text3);font-family:var(--mono);margin-top:4px;}}
  .prog-row{{margin-bottom:16px;}}
  .prog-top{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:5px;}}
  .prog-name{{font-size:13px;font-weight:600;}}
  .prog-nums{{font-size:11px;color:var(--text2);font-family:var(--mono);}}
  .prog-bg{{background:var(--bg4);border-radius:4px;height:8px;position:relative;}}
  .prog-fill{{height:8px;border-radius:4px;}}
  .prog-marker{{position:absolute;top:-5px;height:18px;width:2px;border-radius:1px;background:rgba(176,48,48,.5);}}
  .prog-hint{{font-size:10px;color:var(--text3);margin-top:3px;text-align:right;}}
  .grid2{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-bottom:1.25rem;}}
  .rtbl{{width:100%;border-collapse:collapse;font-size:12px;}}
  .rtbl th{{font-size:10px;color:var(--text3);text-align:right;padding:0 8px 10px;font-weight:500;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap;}}
  .rtbl th:first-child{{text-align:left;}}
  .rtbl td{{padding:8px;color:var(--text2);text-align:right;border-top:1px solid var(--border);vertical-align:middle;}}
  .rtbl td:first-child{{text-align:left;font-weight:600;color:var(--text);}}
  .rtbl .tot td{{font-weight:700;color:var(--text);border-top:1px solid var(--border2);background:var(--bg3);}}
  .sqo-cell{{display:flex;flex-direction:column;align-items:flex-end;gap:1px;}}
  .sqo-n{{font-size:13px;font-weight:600;color:var(--text);}}
  .sqo-v{{font-size:10px;color:var(--text3);font-family:var(--mono);}}
  .dtbl{{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed;}}
  .dtbl th{{font-size:10px;color:var(--text3);padding:0 10px 10px;text-align:left;font-weight:500;text-transform:uppercase;letter-spacing:.05em;}}
  .dtbl td{{padding:7px 10px;border-top:1px solid var(--border);color:var(--text2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
  .dtbl .tot td{{font-weight:700;color:var(--text);border-top:1px solid var(--border2);background:var(--bg3);}}
  .pill{{font-size:10px;padding:2px 8px;border-radius:20px;display:inline-block;font-weight:600;}}
  .pill-v{{background:var(--purple-bg);color:var(--purple);}}
  .pill-s{{background:var(--teal-bg);color:var(--teal);}}
  .att-pill{{font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;display:inline-block;}}
  .leg{{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;}}
  .leg-i{{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--text2);}}
  .leg-d{{width:10px;height:10px;border-radius:2px;flex-shrink:0;}}
  .upd-note{{font-size:11px;color:var(--text3);text-align:center;padding:1rem 0;font-family:var(--mono);}}
  @media(max-width:768px){{.metrics{{grid-template-columns:repeat(2,1fr)}}.q-grid{{grid-template-columns:repeat(2,1fr)}}.grid2{{grid-template-columns:1fr}}.main{{padding:1rem}}.topbar{{padding:0 1rem}}}}
</style>
</head>
<body>

<!-- LOGIN -->
<div id="login-screen">
  <div class="login-box">
    <div class="login-logo">Legalario · Sales</div>
    <h2>Acceso al Dashboard</h2>
    <p>Ingresa la contraseña del equipo</p>
    <input type="password" id="pwd-input" placeholder="Contraseña" onkeydown="if(event.key==='Enter')doLogin()">
    <button class="login-btn" onclick="doLogin()">Entrar</button>
    <div class="login-error" id="login-error">Contraseña incorrecta</div>
  </div>
</div>

<div id="app" style="display:none;">
<div class="topbar">
  <div style="display:flex;align-items:center;gap:1.5rem;">
    <span class="brand">Legalario · Sales</span>
    <span class="live-badge"><span class="live-dot"></span>Actualizado: {update_time}</span>
  </div>
  <span class="date-badge">{update_date}</span>
</div>

<div class="main">
  <div class="tabs">
    <div class="tab active" onclick="switchTab('general')">General</div>
    <div class="tab" onclick="switchTab('reps')">Por AE</div>
    <div class="tab" onclick="switchTab('forecast')">Forecast</div>
    <div class="tab" onclick="switchTab('okr')">OKR Pipeline</div>
    <div class="tab" onclick="switchTab('planweb')">Plan Web</div>
  </div>

  <!-- GENERAL -->
  <div id="view-general" class="view active">
    <div class="metrics" style="grid-template-columns:repeat(5,minmax(0,1fr));">
      <div class="mc"><div class="mc-lbl">Meta anual</div><div class="mc-val">$12.0M</div><div class="mc-sub">New logos 2026</div></div>
      <div class="mc"><div class="mc-lbl">Vendido al momento</div><div class="mc-val" id="g-cw-val" style="color:var(--amber);">—</div><div class="mc-sub" id="g-cw-sub"></div></div>
      <div class="mc"><div class="mc-lbl">Forecast (Verbal+Sign)</div><div class="mc-val" id="g-fc-val" style="color:var(--purple);">—</div><div class="mc-sub" id="g-fc-sub"></div></div>
      <div class="mc"><div class="mc-lbl">Pipeline total</div><div class="mc-val" id="g-pipe-val">—</div><div class="mc-sub" id="g-pipe-sub" style="color:var(--green);">—</div></div>
      <div class="mc"><div class="mc-lbl">Plan Web Q1</div><div class="mc-val" style="color:var(--green);">{fmt_js(pw_total)}</div><div class="mc-sub"><span style="color:var(--{'green' if pw_ann_pct>=25 else 'amber'});">{pw_ann_pct}% de meta anual $1M</span></div></div>
    </div>
    <div class="section">
      <p class="sec-title">Meta anual $12M — attainment acumulado por Q</p>
      <div class="q-grid">
        <div class="q-card" id="q1-card">
          <div class="q-lbl">Q1 · Ene–Mar</div>
          <div class="q-val" id="q1-val">—</div>
          <div class="q-sub" id="q1-sub"></div>
          <div class="q-bar-bg"><div class="q-bar-fill" id="q1-bar" style="width:0%;"></div></div>
        </div>
        <div class="q-card" style="opacity:.45;"><div class="q-lbl">Q2 · Abr–Jun</div><div class="q-val" style="color:var(--text3);">—</div><div class="q-sub">Meta $3M</div><div class="q-bar-bg"><div class="q-bar-fill" style="width:0%;"></div></div></div>
        <div class="q-card" style="opacity:.45;"><div class="q-lbl">Q3 · Jul–Sep</div><div class="q-val" style="color:var(--text3);">—</div><div class="q-sub">Meta $3M</div><div class="q-bar-bg"><div class="q-bar-fill" style="width:0%;"></div></div></div>
        <div class="q-card" style="opacity:.45;"><div class="q-lbl">Q4 · Oct–Dic</div><div class="q-val" style="color:var(--text3);">—</div><div class="q-sub">Meta $3M</div><div class="q-bar-bg"><div class="q-bar-fill" style="width:0%;"></div></div></div>
      </div>
      <div class="ab-wrap">
        <div class="ab-top"><span id="ab-left-txt">—</span><span id="ab-right-txt">—</span></div>
        <div class="ab-bg"><div class="ab-fill" id="ab-fill-bar" style="width:0%;"></div><div class="ab-m" style="left:25%;"></div><div class="ab-m" style="left:50%;"></div><div class="ab-m" style="left:75%;"></div></div>
        <div class="ab-ticks"><span>$0</span><span>Q1 $3M</span><span>Q2 $6M</span><span>Q3 $9M</span><span>$12M</span></div>
      </div>
    </div>
    <div class="section"><p class="sec-title">Vendido al momento por AE — vs meta anual</p><div id="g-prog"></div></div>
    <div class="grid2">
      <div class="section" style="margin-bottom:0;"><p class="sec-title">CW + Forecast por AE</p><div style="position:relative;height:190px;"><canvas id="cwFChart"></canvas></div><div class="leg"><span class="leg-i"><span class="leg-d" style="background:#0e8a5f;"></span>Close Won</span><span class="leg-i"><span class="leg-d" style="background:#5b3fb5;"></span>Verbal</span><span class="leg-i"><span class="leg-d" style="background:#0b7a6a;"></span>Sign</span></div></div>
      <div class="section" style="margin-bottom:0;"><p class="sec-title">Distribución pipeline activo</p><div style="position:relative;height:190px;"><canvas id="pipeDonut"></canvas></div><div class="leg"><span class="leg-i"><span class="leg-d" style="background:#1a56c4;"></span>SQO</span><span class="leg-i"><span class="leg-d" style="background:#b86e00;"></span>Negotiation</span><span class="leg-i"><span class="leg-d" style="background:#e07820;"></span>Demo</span><span class="leg-i"><span class="leg-d" style="background:#5b3fb5;"></span>Verbal</span><span class="leg-i"><span class="leg-d" style="background:#0b7a6a;"></span>Sign</span></div></div>
    </div>
  </div>

  <!-- POR AE -->
  <div id="view-reps" class="view">
    <div class="section"><p class="sec-title">Resumen por AE — Q1 y anual</p><div style="overflow-x:auto;"><table class="rtbl"><thead><tr><th style="text-align:left;">AE</th><th>Meta Q1</th><th>CW Q1</th><th>ATT% Q1</th><th>SQOs Q1</th><th>Pipe total</th><th>Meta anual</th><th>ATT% anual</th></tr></thead><tbody id="reps-tbl"></tbody></table></div></div>
    <div class="section"><p class="sec-title">Pipeline activo por AE</p><div style="overflow-x:auto;"><table class="rtbl"><thead><tr><th style="text-align:left;">AE</th><th>SQOs activos</th><th>Negotiation</th><th>Demo</th><th>Verbal</th><th>Sign</th><th>CW 2026</th><th>Total</th></tr></thead><tbody id="pipe-tbl"></tbody></table></div></div>
  </div>

  <!-- FORECAST -->
  <div id="view-forecast" class="view">
    <div class="metrics">
      <div class="mc"><div class="mc-lbl">Forecast total</div><div class="mc-val" id="f-total" style="color:var(--purple);">—</div><div class="mc-sub">Verbal + Sign</div></div>
      <div class="mc"><div class="mc-lbl">CW + Forecast</div><div class="mc-val" id="f-cwf" style="color:var(--green);">—</div><div class="mc-sub" id="f-cwf-sub"></div></div>
      <div class="mc"><div class="mc-lbl">Deals en forecast</div><div class="mc-val" id="f-count">—</div><div class="mc-sub">Verbal + Sign</div></div>
      <div class="mc"><div class="mc-lbl">Ticket promedio</div><div class="mc-val" id="f-avg">—</div><div class="mc-sub">Por deal en forecast</div></div>
    </div>
    <div class="section">
      <p class="sec-title">Compromiso de forecast por AE</p>
      <table class="rtbl"><thead><tr><th style="text-align:left;">AE</th><th>Verbal</th><th>Sign</th><th>Total forecast</th><th>Meta Q1</th><th>CW actual</th><th>Faltante para meta Q</th></tr></thead><tbody id="commit-tbl"></tbody></table>
    </div>
    <div class="section"><p class="sec-title">Deals en Forecast — Verbal + Sign</p><table class="dtbl"><thead><tr><th style="width:34%;">Deal</th><th style="width:14%;text-align:right;">ARR</th><th style="width:11%;text-align:center;">Stage</th><th style="width:14%;">AE</th><th style="width:27%;text-align:right;">ATT% anual si cierra</th></tr></thead><tbody id="forecast-tbl"></tbody><tfoot id="forecast-foot"></tfoot></table></div>
    <div class="section"><p class="sec-title">Forecast por AE (Verbal + Sign)</p><div style="position:relative;height:200px;"><canvas id="fcChart"></canvas></div><div class="leg"><span class="leg-i"><span class="leg-d" style="background:#5b3fb5;"></span>Verbal</span><span class="leg-i"><span class="leg-d" style="background:#0b7a6a;"></span>Sign</span></div></div>
  </div>

  <!-- OKR -->
  <div id="view-okr" class="view">
    <div class="metrics">
      <div class="mc"><div class="mc-lbl">SQOs generados Q1</div><div class="mc-val" id="o-sqos">—</div><div class="mc-sub">Con sqo_date en ene–mar 2026</div></div>
      <div class="mc"><div class="mc-lbl">ARR nuevo Q1</div><div class="mc-val" id="o-arr" style="color:var(--blue);">—</div><div class="mc-sub">Valor total de SQOs generados</div></div>
      <div class="mc"><div class="mc-lbl">Pipeline activo</div><div class="mc-val" id="o-pipe">—</div><div class="mc-sub">SQO+Demo+Neg+Verbal+Sign</div></div>
      <div class="mc"><div class="mc-lbl">Ticket promedio SQO</div><div class="mc-val" id="o-avg">—</div><div class="mc-sub">Por SQO generado Q1</div></div>
    </div>
    <div class="section"><p class="sec-title">SQOs Q1 por AE — número y valor ARR generado</p><div style="overflow-x:auto;"><table class="rtbl"><thead><tr><th style="text-align:left;">AE</th><th># SQOs Q1</th><th>ARR generado Q1</th><th>Ticket prom.</th><th>Pipeline activo total</th></tr></thead><tbody id="okr-tbl"></tbody></table></div></div>
    <div class="grid2">
      <div class="section" style="margin-bottom:0;"><p class="sec-title"># SQOs generados Q1 por AE</p><div style="position:relative;height:180px;"><canvas id="sqoCntChart"></canvas></div></div>
      <div class="section" style="margin-bottom:0;"><p class="sec-title">ARR generado Q1 por AE</p><div style="position:relative;height:180px;"><canvas id="sqoArrChart"></canvas></div></div>
    </div>
  </div>

  <!-- PLAN WEB -->
  <div id="view-planweb" class="view">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:1.5rem;">
      <span style="font-size:13px;font-weight:600;color:var(--text2);">AE responsable:</span>
      <span style="font-size:13px;font-weight:700;color:var(--text);">Ilse González</span>
      <span style="font-size:11px;background:var(--amber-bg);color:var(--amber);padding:2px 10px;border-radius:20px;margin-left:4px;">en rampa</span>
    </div>
    <div class="metrics">
      <div class="mc"><div class="mc-lbl">Meta anual Plan Web</div><div class="mc-val">$1.00M</div><div class="mc-sub">Canal separado de New Logos</div></div>
      <div class="mc"><div class="mc-lbl">Vendido Q1</div><div class="mc-val" style="color:var(--{'green' if pw_q1_pct>=100 else 'amber'});">{fmt_js(pw_total)}</div><div class="mc-sub"><span style="color:var(--{'green' if pw_q1_pct>=100 else 'amber'});">{'✓ ' if pw_q1_pct>=100 else ''}{pw_q1_pct}% de meta Q {'alcanzada' if pw_q1_pct>=100 else '· Q1 en curso'}</span></div></div>
      <div class="mc"><div class="mc-lbl">New Logo Q1</div><div class="mc-val" style="color:var(--blue);">{fmt_js(pw_total_nl)}</div><div class="mc-sub">{len(pw_nl)} deals · tipo Plan Web</div></div>
      <div class="mc"><div class="mc-lbl">Base Instalada Q1</div><div class="mc-val" style="color:var(--purple);">{fmt_js(pw_total_bi)}</div><div class="mc-sub">{len(pw_bi)} renovaciones</div></div>
    </div>
    <div class="section">
      <p class="sec-title">Meta anual $1M — attainment acumulado</p>
      <div class="q-grid">
        <div class="q-card"><div class="q-lbl">Q1 · Ene–Mar</div><div class="q-val" style="color:var(--{'green' if pw_q1_pct>=100 else 'amber'});">{fmt_js(pw_total)}</div><div class="q-sub" style="color:var(--{'green' if pw_q1_pct>=100 else 'amber'});">{'✓ ' if pw_q1_pct>=100 else ''}{pw_q1_pct}% de $250K meta Q</div><div class="q-bar-bg"><div class="q-bar-fill" style="width:{min(pw_q1_pct,100)}%;background:var(--{'green' if pw_q1_pct>=100 else 'amber'});"></div></div></div>
        <div class="q-card" style="opacity:.45;"><div class="q-lbl">Q2 · Abr–Jun</div><div class="q-val" style="color:var(--text3);">—</div><div class="q-sub">Meta $250K</div><div class="q-bar-bg"><div class="q-bar-fill" style="width:0%;"></div></div></div>
        <div class="q-card" style="opacity:.45;"><div class="q-lbl">Q3 · Jul–Sep</div><div class="q-val" style="color:var(--text3);">—</div><div class="q-sub">Meta $250K</div><div class="q-bar-bg"><div class="q-bar-fill" style="width:0%;"></div></div></div>
        <div class="q-card" style="opacity:.45;"><div class="q-lbl">Q4 · Oct–Dic</div><div class="q-val" style="color:var(--text3);">—</div><div class="q-sub">Meta $250K</div><div class="q-bar-bg"><div class="q-bar-fill" style="width:0%;"></div></div></div>
      </div>
      <div class="ab-wrap">
        <div class="ab-top"><span>Acumulado: {fmt_js(pw_total)}</span><span style="color:var(--{'green' if pw_ann_pct>=25 else 'amber'});">{pw_ann_pct}% de $1M</span></div>
        <div class="ab-bg"><div class="ab-fill" style="width:{min(pw_ann_pct,100):.1f}%;background:var(--blue);"></div><div class="ab-m" style="left:25%;"></div><div class="ab-m" style="left:50%;"></div><div class="ab-m" style="left:75%;"></div></div>
        <div class="ab-ticks"><span>$0</span><span>Q1 $250K</span><span>Q2 $500K</span><span>Q3 $750K</span><span>$1M</span></div>
      </div>
    </div>
    <div class="grid2">
      <div class="section" style="margin-bottom:0;"><p class="sec-title">Vendido por mes — NL vs Base Instalada</p><div style="position:relative;height:190px;"><canvas id="pwMonthChart"></canvas></div><div class="leg"><span class="leg-i"><span class="leg-d" style="background:var(--blue);"></span>New Logo</span><span class="leg-i"><span class="leg-d" style="background:var(--purple);"></span>Base Instalada</span></div></div>
      <div class="section" style="margin-bottom:0;"><p class="sec-title">Distribución Q1</p><div style="position:relative;height:190px;"><canvas id="pwDonut"></canvas></div><div class="leg"><span class="leg-i"><span class="leg-d" style="background:var(--blue);"></span>New Logo {fmt_js(pw_total_nl)} ({round(pw_total_nl/pw_total*100) if pw_total else 0}%)</span><span class="leg-i"><span class="leg-d" style="background:var(--purple);"></span>Base Instalada {fmt_js(pw_total_bi)} ({round(pw_total_bi/pw_total*100) if pw_total else 0}%)</span></div></div>
    </div>
    <div class="section"><p class="sec-title">Deals New Logo — Plan Web Q1 2026</p><table class="rtbl"><thead><tr><th style="text-align:left;">Deal</th><th>Mes</th><th>ARR</th></tr></thead><tbody id="pw-nl-tbl"></tbody></table></div>
    <div class="section"><p class="sec-title">Renovaciones — Base Instalada Q1 2026</p><table class="rtbl"><thead><tr><th style="text-align:left;">Deal</th><th>Mes</th><th>ARR</th></tr></thead><tbody id="pw-bi-tbl"></tbody></table></div>
  </div>

  <p class="upd-note">Datos extraídos de HubSpot · Auto-actualización cada hora · {update_time}</p>
</div>
</div>

<script>
// ── AUTH ──
const PASS_HASH = "legalario2026"; // contraseña simple
function doLogin(){{
  const v = document.getElementById('pwd-input').value;
  if(v === PASS_HASH){{
    sessionStorage.setItem('auth','1');
    document.getElementById('login-screen').style.display='none';
    document.getElementById('app').style.display='block';
  }} else {{
    document.getElementById('login-error').style.display='block';
  }}
}}
if(sessionStorage.getItem('auth')==='1'){{
  document.getElementById('login-screen').style.display='none';
  document.getElementById('app').style.display='block';
}}

// ── DATA ──
const CW   = {js_arr(cw)};
const SQO  = {js_arr(sqo)};
const NEG  = {js_arr(neg)};
const DEMO = {js_arr(demo)};
const VERB = {js_arr(verb)};
const SIGN = {js_arr(sign)};
const SQO_Q1_COUNT = {js_arr(sqo_q1_count)};
const SQO_Q1_ARR   = {js_arr(sqo_q1_arr)};
const METAS_Q1    = {{Ernesto:1300000,Karla:1100000,Rossana:750000,Diego:0,Ilse:650000}};
const METAS_ANUAL = {{Ernesto:5200000,Karla:4400000,Rossana:3000000,Diego:0,Ilse:2600000}};
const META_EQ1=3000000, META_EA=12000000;
const FC_DEALS = {fc_deals_js};
const PW_NL    = {pw_nl_js};
const PW_BI    = {pw_bi_js};

const names=['Ernesto','Karla','Rossana','Diego','Ilse'];
const fmt=n=>n>=1000000?'$'+(n/1000000).toFixed(2)+'M':'$'+(n/1000).toFixed(0)+'K';
const fmtP=n=>Math.round(n)+'%';
const ac=p=>p>=70?'var(--green)':p>=30?'var(--amber)':'var(--red)';
const acBg=p=>p>=70?'var(--green-bg)':p>=30?'var(--amber-bg)':'var(--red-bg)';
const attPill=(p,l)=>`<span class="att-pill" style="background:${{acBg(p)}};color:${{ac(p)}};">${{l}}</span>`;

function switchTab(id){{
  document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active',['general','reps','forecast','okr','planweb'][i]===id));
  document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id==='view-'+id));
}}

const totalCw   = names.reduce((a,n)=>a+CW[n],0);
const totalSqo  = names.reduce((a,n)=>a+SQO[n],0);
const totalNeg  = names.reduce((a,n)=>a+NEG[n],0);
const totalDemo = names.reduce((a,n)=>a+DEMO[n],0);
const totalVerb = names.reduce((a,n)=>a+VERB[n],0);
const totalSign = names.reduce((a,n)=>a+SIGN[n],0);
const totalFc   = totalVerb+totalSign;
const totalPipe = totalSqo+totalNeg+totalDemo+totalVerb+totalSign;
const totalSqoQ1c = names.reduce((a,n)=>a+SQO_Q1_COUNT[n],0);
const totalSqoQ1a = names.reduce((a,n)=>a+SQO_Q1_ARR[n],0);
const attA = Math.round(totalCw/META_EA*100);
const attQ1= Math.round(totalCw/META_EQ1*100);

// ── GENERAL dynamic cards ──
const q1color=ac(attQ1);
document.getElementById('q1-val').textContent=fmt(totalCw);
document.getElementById('q1-val').style.color=q1color;
document.getElementById('q1-sub').textContent=fmtP(attQ1)+' de '+fmt(META_EQ1)+' meta Q';
document.getElementById('q1-sub').style.color=q1color;
document.getElementById('q1-bar').style.width=Math.min(attQ1,100)+'%';
document.getElementById('q1-bar').style.background=q1color;
document.getElementById('ab-left-txt').textContent='Acumulado: '+fmt(totalCw);
document.getElementById('ab-right-txt').textContent=fmtP(attA)+' de $12M';
document.getElementById('ab-right-txt').style.color=q1color;
document.getElementById('ab-fill-bar').style.width=Math.min(attA,100)+'%';
document.getElementById('g-cw-val').textContent=fmt(totalCw);
document.getElementById('g-cw-sub').innerHTML='<span style="color:'+ac(attA)+';">'+fmtP(attA)+' del año · Q1 en curso</span>';
document.getElementById('g-fc-val').textContent=fmt(totalFc);
document.getElementById('g-fc-sub').innerHTML='CW+F = <strong>'+fmt(totalCw+totalFc)+' ('+fmtP(Math.round((totalCw+totalFc)/META_EA*100))+')</strong>';
document.getElementById('g-pipe-val').textContent=fmt(totalPipe);
document.getElementById('g-pipe-sub').textContent='Cobertura '+(totalPipe/META_EA).toFixed(1)+'x meta anual';

// ── GENERAL progress bars ──
const gp=document.getElementById('g-prog');
names.forEach(n=>{{
  const meta=METAS_ANUAL[n],val=CW[n],pct=meta?Math.round(val/meta*100):null;
  const q1pct=meta&&METAS_Q1[n]?Math.round(METAS_Q1[n]/meta*100):null;
  const badge=n==='Diego'?'<span style="font-size:10px;background:var(--bg4);color:var(--text3);padding:1px 7px;border-radius:10px;margin-left:5px;border:1px solid var(--border);">salió</span>':n==='Ilse'?'<span style="font-size:10px;background:var(--amber-bg);color:var(--amber);padding:1px 7px;border-radius:10px;margin-left:5px;">rampa</span>':'';
  gp.innerHTML+=`<div class="prog-row"><div class="prog-top"><span class="prog-name">${{n}}${{badge}}</span><span class="prog-nums">${{fmt(val)}} vendido · ${{meta?fmt(meta):'—'}} meta · <span style="color:${{pct!==null?ac(pct):'var(--text3)'}}">${{pct!==null?fmtP(pct):''}}</span></span></div><div class="prog-bg"><div class="prog-fill" style="width:${{pct?Math.min(pct,100):0}}%;background:${{pct!==null?ac(pct):'#bbb'}};"></div>${{q1pct?`<div class="prog-marker" style="left:${{q1pct}}%;"></div>`:''}}</div><div class="prog-hint">Línea roja = dónde deberías estar al cierre de Q1</div></div>`;
}});

// ── REPS TABLE ──
const rt=document.getElementById('reps-tbl');
names.forEach(n=>{{
  const mq=METAS_Q1[n],ma=METAS_ANUAL[n],v=CW[n];
  const attQ=mq?Math.round(v/mq*100):null, attAn=ma?Math.round(v/ma*100):null;
  const tp=SQO[n]+NEG[n]+DEMO[n]+VERB[n]+SIGN[n];
  const badge=n==='Diego'?' <span style="font-size:10px;color:var(--text3);">(salió)</span>':n==='Ilse'?' <span style="font-size:10px;color:var(--amber);">(rampa)</span>':'';
  rt.innerHTML+=`<tr><td>${{n}}${{badge}}</td><td>${{mq?fmt(mq):'—'}}</td><td style="color:var(--green);">${{v>0?fmt(v):'—'}}</td><td>${{attQ!==null?attPill(attQ,fmtP(attQ)):'—'}}</td><td><div class="sqo-cell"><span class="sqo-n">${{SQO_Q1_COUNT[n]}} SQOs</span><span class="sqo-v">${{fmt(SQO_Q1_ARR[n])}}</span></div></td><td>${{fmt(tp)}}</td><td>${{ma?fmt(ma):'—'}}</td><td>${{attAn!==null?attPill(attAn,fmtP(attAn)):'—'}}</td></tr>`;
}});
rt.innerHTML+=`<tr class="tot"><td>Total equipo</td><td>${{fmt(META_EQ1)}}</td><td style="color:var(--green);">${{fmt(totalCw)}}</td><td>${{attPill(attQ1,fmtP(attQ1))}}</td><td><div class="sqo-cell"><span class="sqo-n">${{totalSqoQ1c}} SQOs</span><span class="sqo-v">${{fmt(totalSqoQ1a)}}</span></div></td><td>${{fmt(totalPipe)}}</td><td>$12.0M</td><td>${{attPill(attA,fmtP(attA))}}</td></tr>`;

// ── PIPE TABLE ──
const pt=document.getElementById('pipe-tbl');
names.forEach(n=>{{
  const badge=n==='Diego'?' <span style="font-size:10px;color:var(--text3);">(salió)</span>':n==='Ilse'?' <span style="font-size:10px;color:var(--amber);">(rampa)</span>':'';
  const tot=SQO[n]+NEG[n]+DEMO[n]+VERB[n]+SIGN[n]+CW[n];
  pt.innerHTML+=`<tr><td>${{n}}${{badge}}</td><td><div class="sqo-cell"><span class="sqo-n">${{fmt(SQO[n])}}</span></div></td><td style="color:var(--amber);">${{NEG[n]>0?fmt(NEG[n]):'—'}}</td><td style="color:#e07820;">${{DEMO[n]>0?fmt(DEMO[n]):'—'}}</td><td style="color:var(--purple);">${{VERB[n]>0?fmt(VERB[n]):'—'}}</td><td style="color:var(--teal);">${{SIGN[n]>0?fmt(SIGN[n]):'—'}}</td><td style="color:var(--green);">${{CW[n]>0?fmt(CW[n]):'—'}}</td><td style="font-weight:700;">${{fmt(tot)}}</td></tr>`;
}});
pt.innerHTML+=`<tr class="tot"><td>Total</td><td>${{fmt(totalSqo)}}</td><td style="color:var(--amber);">${{fmt(totalNeg)}}</td><td style="color:#e07820;">${{fmt(totalDemo)}}</td><td style="color:var(--purple);">${{fmt(totalVerb)}}</td><td style="color:var(--teal);">${{fmt(totalSign)}}</td><td style="color:var(--green);">${{fmt(totalCw)}}</td><td>${{fmt(totalPipe+totalCw)}}</td></tr>`;

// ── FORECAST ──
document.getElementById('f-total').textContent=fmt(totalFc);
document.getElementById('f-cwf').textContent=fmt(totalCw+totalFc);
document.getElementById('f-cwf-sub').textContent=fmtP(Math.round((totalCw+totalFc)/META_EA*100))+' de meta anual';
document.getElementById('f-count').textContent=FC_DEALS.length;
document.getElementById('f-avg').textContent=FC_DEALS.length?fmt(Math.round(totalFc/FC_DEALS.length)):'—';

// Commitment table
const ct=document.getElementById('commit-tbl');
names.filter(n=>n!=='Diego').forEach(n=>{{
  const v=VERB[n],s=SIGN[n],fc=v+s,cw2=CW[n],mq=METAS_Q1[n];
  const falt=Math.max(0,mq-cw2);
  const ramp=n==='Ilse';
  const faltLabel=ramp?'<span style="color:var(--text3);">en rampa</span>':falt>0?'-'+fmt(falt):'✓ meta alcanzada';
  const faltColor=ramp?'var(--text3)':falt>0?'var(--red)':'var(--green)';
  ct.innerHTML+=`<tr><td>${{n}}${{ramp?' <span style="font-size:10px;color:var(--amber);">(rampa)</span>':''}}</td><td style="text-align:right;color:var(--purple);">${{v>0?fmt(v):'—'}}</td><td style="text-align:right;color:var(--teal);">${{s>0?fmt(s):'—'}}</td><td style="text-align:right;font-weight:700;">${{fmt(fc)}}</td><td style="text-align:right;color:var(--text3);">${{mq?fmt(mq):'—'}}</td><td style="text-align:right;color:var(--green);">${{cw2>0?fmt(cw2):'—'}}</td><td style="text-align:right;color:${{faltColor}};font-weight:600;">${{faltLabel}}</td></tr>`;
}});
const totV=names.reduce((a,n)=>a+VERB[n],0),totS=names.reduce((a,n)=>a+SIGN[n],0);
const totFalt=Math.max(0,META_EQ1-totalCw);
ct.innerHTML+=`<tr class="tot"><td>Total equipo</td><td style="text-align:right;color:var(--purple);">${{fmt(totV)}}</td><td style="text-align:right;color:var(--teal);">${{fmt(totS)}}</td><td style="text-align:right;">${{fmt(totV+totS)}}</td><td style="text-align:right;color:var(--text3);">${{fmt(META_EQ1)}}</td><td style="text-align:right;color:var(--green);">${{fmt(totalCw)}}</td><td style="text-align:right;color:var(--red);font-weight:600;">-${{fmt(totFalt)}}</td></tr>`;

// Forecast deals table
const ft=document.getElementById('forecast-tbl');
FC_DEALS.forEach(d=>{{
  const ma=METAS_ANUAL[d.ae],rc=CW[d.ae]||0;
  const pct=ma?fmtP(Math.round((rc+d.a)/ma*100)):'—';
  const pill=d.stage==='sign'?'<span class="pill pill-s">Sign</span>':'<span class="pill pill-v">Verbal</span>';
  ft.innerHTML+=`<tr><td title="${{d.d}}">${{d.d}}</td><td style="text-align:right;font-weight:700;">${{fmt(d.a)}}</td><td style="text-align:center;">${{pill}}</td><td>${{d.ae}}</td><td style="text-align:right;font-size:11px;color:var(--text2);">${{pct}}</td></tr>`;
}});
document.getElementById('forecast-foot').innerHTML=`<tr class="tot"><td>Total forecast</td><td style="text-align:right;">${{fmt(totalFc)}}</td><td></td><td></td><td style="text-align:right;font-size:11px;">CW+F = ${{fmt(totalCw+totalFc)}}</td></tr>`;

// ── OKR ──
document.getElementById('o-sqos').textContent=totalSqoQ1c;
document.getElementById('o-arr').textContent=fmt(totalSqoQ1a);
document.getElementById('o-pipe').textContent=fmt(totalPipe);
document.getElementById('o-avg').textContent=totalSqoQ1c?fmt(Math.round(totalSqoQ1a/totalSqoQ1c)):'—';
const ot=document.getElementById('okr-tbl');
names.forEach(n=>{{
  const cnt=SQO_Q1_COUNT[n],arr=SQO_Q1_ARR[n],avg=cnt?Math.round(arr/cnt):0;
  const tp=SQO[n]+NEG[n]+DEMO[n]+VERB[n]+SIGN[n];
  const badge=n==='Diego'?' <span style="font-size:10px;color:var(--text3);">(salió)</span>':n==='Ilse'?' <span style="font-size:10px;color:var(--amber);">(rampa)</span>':'';
  ot.innerHTML+=`<tr><td>${{n}}${{badge}}</td><td style="text-align:right;font-weight:700;">${{cnt}}</td><td style="text-align:right;color:var(--blue);">${{fmt(arr)}}</td><td style="text-align:right;">${{avg?fmt(avg):'—'}}</td><td style="text-align:right;">${{fmt(tp)}}</td></tr>`;
}});
ot.innerHTML+=`<tr class="tot"><td>Total</td><td style="text-align:right;">${{totalSqoQ1c}}</td><td style="text-align:right;color:var(--blue);">${{fmt(totalSqoQ1a)}}</td><td style="text-align:right;">${{fmt(Math.round(totalSqoQ1a/totalSqoQ1c))}}</td><td style="text-align:right;">${{fmt(totalPipe)}}</td></tr>`;

// ── PLAN WEB TABLES ──
const pwNlT=document.getElementById('pw-nl-tbl');
PW_NL.forEach(d=>{{ pwNlT.innerHTML+=`<tr><td>${{d.d}}</td><td style="text-align:right;color:var(--text3);">${{d.m}}</td><td style="text-align:right;color:var(--blue);font-weight:600;">${{fmt(d.a)}}</td></tr>`; }});
pwNlT.innerHTML+=`<tr class="tot"><td>Total New Logo</td><td></td><td style="text-align:right;color:var(--blue);">${{fmt(PW_NL.reduce((a,d)=>a+d.a,0))}}</td></tr>`;
const pwBiT=document.getElementById('pw-bi-tbl');
PW_BI.forEach(d=>{{ pwBiT.innerHTML+=`<tr><td>${{d.d}}</td><td style="text-align:right;color:var(--text3);">${{d.m}}</td><td style="text-align:right;color:var(--purple);font-weight:600;">${{fmt(d.a)}}</td></tr>`; }});
pwBiT.innerHTML+=`<tr class="tot"><td>Total Base Instalada</td><td></td><td style="text-align:right;color:var(--purple);">${{fmt(PW_BI.reduce((a,d)=>a+d.a,0))}}</td></tr>`;

// ── CHARTS ──
const cd={{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}}}};
const xA={{ticks:{{font:{{size:11}},color:'#6b8aaa'}},grid:{{display:false}}}};
const yA=cb=>({{ticks:{{font:{{size:10}},color:'#6b8aaa',callback:cb}},grid:{{color:'rgba(30,80,140,0.06)'}}}});
const cb=v=>v>=1000000?'$'+(v/1e6).toFixed(1)+'M':'$'+(v/1000)+'K';

new Chart(document.getElementById('cwFChart'),{{type:'bar',data:{{labels:names,datasets:[{{label:'CW',data:names.map(n=>CW[n]),backgroundColor:'#0e8a5f',borderRadius:4}},{{label:'Verbal',data:names.map(n=>VERB[n]),backgroundColor:'#5b3fb5',borderRadius:4}},{{label:'Sign',data:names.map(n=>SIGN[n]),backgroundColor:'#0b7a6a',borderRadius:4}}]}},options:{{...cd,scales:{{x:{{...xA,stacked:true}},y:{{...yA(cb),stacked:true}}}}}}}});
new Chart(document.getElementById('pipeDonut'),{{type:'doughnut',data:{{labels:['SQO','Negotiation','Demo','Verbal','Sign','CW'],datasets:[{{data:[totalSqo,totalNeg,totalDemo,totalVerb,totalSign,totalCw],backgroundColor:['#1a56c4','#b86e00','#e07820','#5b3fb5','#0b7a6a','#0e8a5f'],borderWidth:0,hoverOffset:4}}]}},options:{{...cd,cutout:'64%'}}}});
new Chart(document.getElementById('fcChart'),{{type:'bar',data:{{labels:names,datasets:[{{label:'Verbal',data:names.map(n=>VERB[n]),backgroundColor:'#5b3fb5',borderRadius:4}},{{label:'Sign',data:names.map(n=>SIGN[n]),backgroundColor:'#0b7a6a',borderRadius:4}}]}},options:{{...cd,scales:{{x:{{...xA,stacked:true}},y:{{...yA(cb),stacked:true}}}}}}}});
new Chart(document.getElementById('sqoCntChart'),{{type:'bar',data:{{labels:names,datasets:[{{label:'SQOs',data:names.map(n=>SQO_Q1_COUNT[n]),backgroundColor:'#1a56c4',borderRadius:4}}]}},options:{{...cd,scales:{{x:xA,y:yA(v=>v)}}}}}});
new Chart(document.getElementById('sqoArrChart'),{{type:'bar',data:{{labels:names,datasets:[{{label:'ARR',data:names.map(n=>SQO_Q1_ARR[n]),backgroundColor:'#7aaee8',borderRadius:4}}]}},options:{{...cd,scales:{{x:xA,y:yA(cb)}}}}}});

const meses=['Ene','Feb','Mar'];
const allPw=[...PW_NL,...PW_BI];
const nlMes=meses.map(m=>PW_NL.filter(d=>d.m===m).reduce((s,d)=>s+d.a,0));
const biMes=meses.map(m=>PW_BI.filter(d=>d.m===m).reduce((s,d)=>s+d.a,0));
new Chart(document.getElementById('pwMonthChart'),{{type:'bar',data:{{labels:meses,datasets:[{{label:'New Logo',data:nlMes,backgroundColor:'#1a56c4',borderRadius:4}},{{label:'Base Instalada',data:biMes,backgroundColor:'#5b3fb5',borderRadius:4}}]}},options:{{...cd,scales:{{x:{{...xA,stacked:true}},y:{{...yA(cb),stacked:true}}}}}}}});
const pwNlTot=PW_NL.reduce((a,d)=>a+d.a,0), pwBiTot=PW_BI.reduce((a,d)=>a+d.a,0);
new Chart(document.getElementById('pwDonut'),{{type:'doughnut',data:{{labels:['New Logo','Base Instalada'],datasets:[{{data:[pwNlTot,pwBiTot],backgroundColor:['#1a56c4','#5b3fb5'],borderWidth:0,hoverOffset:4}}]}},options:{{...cd,cutout:'64%'}}}});
</script>
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"✅ index.html generado exitosamente ({len(html):,} chars)")
