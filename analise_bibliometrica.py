#!/usr/bin/env python3
"""
analise_bibliometrica.py
Análise bibliométrica do corpus UML (235 artigos, 2010–2024)
Gera: dados_processados.json + dashboard_uml.html
"""

import csv
import json
import re
from collections import Counter
from pathlib import Path
import pandas as pd

BASE   = Path(__file__).parent
ANALISE = BASE / "ANÁLISE"
OUTPUT_JSON = BASE / "dados_processados.json"
OUTPUT_HTML = BASE / "dashboard_uml.html"

STOPWORDS = {
    "a","an","and","are","as","at","be","been","being","but","by","do","does",
    "for","from","has","have","he","her","his","how","i","if","in","into","is",
    "it","its","not","of","on","or","our","out","s","she","so","than","that",
    "the","their","them","then","there","these","they","this","those","through",
    "to","under","up","use","used","using","via","was","we","were","what","when",
    "where","which","while","who","with","you","your","based","new","two",
    "approach","method","framework","study","analysis","survey","review","work",
    "paper","research","case","results","system","systems","data","tool","tools",
    "applied","application","applications","approaches","methods","techniques",
    "technique","towards","within","toward","across","between","among","over",
    "um","uma","de","do","da","dos","das","em","para","com","por","se","ao",
    "na","no","nos","nas","e","o","a","os","as","ou","seu","sua","seus","suas",
    "como","mais","ser",
}

SOURCE_MAP = {
    "scispace_uml_results.csv":         "SciSpace",
    "scispace_fulltext_uml_results.csv":"SciSpace Full-Text",
    "google_scholar_uml_results.csv":   "Google Scholar",
    "pubmed_uml_results.csv":           "PubMed",
}

PHASE_RANGES = [
    ("Fase 1 — Consolidação (2010–2014)",  2010, 2014),
    ("Fase 2 — Expansão MDE (2015–2019)", 2015, 2019),
    ("Fase 3 — Especialização (2020–2024)", 2020, 2024),
]


# ── Carregamento ───────────────────────────────────────────────────────────────
def load_csvs() -> pd.DataFrame:
    frames = []
    for fname, source in SOURCE_MAP.items():
        path = ANALISE / fname
        if not path.exists():
            print(f"  [aviso] arquivo não encontrado: {fname}")
            continue
        df = pd.read_csv(path, dtype=str)
        df.columns = [c.strip() for c in df.columns]
        df["_source"] = source
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    for col in ["Paper Title","Publication Year","Publication Type",
                "Publication Title","Author Names","DOI","Abstract"]:
        if col not in combined.columns:
            combined[col] = ""
    return combined


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["_title_norm"] = (
        df["Paper Title"].fillna("").str.lower()
        .str.replace(r"[^a-z0-9\s]", " ", regex=True)
        .str.split().apply(lambda w: " ".join(w[:8]) if isinstance(w, list) else "")
    )
    df["_abstract_len"] = df["Abstract"].fillna("").str.len()
    df = df.sort_values("_abstract_len", ascending=False)
    df = df.drop_duplicates(subset=["_title_norm"], keep="first")

    df["Year"] = pd.to_numeric(df["Publication Year"], errors="coerce")
    df = df[df["Year"].notna() & (df["Year"] >= 2010) & (df["Year"] <= 2024)]
    df["Year"] = df["Year"].astype(int)

    def phase(y):
        if y <= 2014: return "Fase 1 — Consolidação (2010–2014)"
        if y <= 2019: return "Fase 2 — Expansão MDE (2015–2019)"
        return "Fase 3 — Especialização (2020–2024)"

    df["Phase"] = df["Year"].apply(phase)
    df["Paper Title"]       = df["Paper Title"].fillna("").str.strip()
    df["Publication Title"] = df["Publication Title"].fillna("").str.strip()
    df["Author Names"]      = df["Author Names"].fillna("")
    df["DOI"]               = df["DOI"].fillna("")
    df["Abstract"]          = df["Abstract"].fillna("")
    df["Publication Type"]  = df["Publication Type"].fillna("Unknown").str.strip()
    return df.reset_index(drop=True)


def parse_authors(raw: str) -> list:
    return [p.strip() for p in re.split(r"[\n,;]+", raw) if len(p.strip()) > 2]


def extract_title_keywords(titles: pd.Series, n: int = 30) -> list:
    words = []
    for title in titles:
        for w in re.findall(r"[a-zA-Z]{3,}", str(title).lower()):
            if w not in STOPWORDS:
                words.append(w)
    return Counter(words).most_common(n)


def build_stats(df: pd.DataFrame) -> dict:
    by_year = {str(y): int(df[df["Year"] == y].shape[0]) for y in range(2010, 2025)}
    by_type = df["Publication Type"].value_counts().head(8).to_dict()
    by_source = df["_source"].value_counts().to_dict()
    by_phase  = df["Phase"].value_counts().to_dict()

    all_authors = []
    for raw in df["Author Names"]:
        all_authors.extend(parse_authors(raw))
    top_authors = Counter(all_authors).most_common(25)

    # Normalize venue names case-insensitively before counting
    df["_venue_norm"] = df["Publication Title"].str.strip().str.lower()
    mask_v = df["_venue_norm"].str.len() > 2
    norm_counts = df[mask_v]["_venue_norm"].value_counts().head(20)
    # Map each normalized key back to its most common original capitalization
    _norm_to_orig = (df[mask_v].groupby("_venue_norm")["Publication Title"]
                     .agg(lambda s: s.value_counts().index[0]))
    top_venues = {_norm_to_orig[k]: int(v) for k, v in norm_counts.items()}
    top_keywords = extract_title_keywords(df["Paper Title"], n=30)

    # evolução por fase
    top8_words = [w for w, _ in top_keywords[:8]]
    kw_evolution = {}
    for word in top8_words:
        kw_evolution[word] = []
        for _, y1, y2 in PHASE_RANGES:
            subset = df[(df["Year"] >= y1) & (df["Year"] <= y2)]
            count = int(subset["Paper Title"].str.lower()
                        .str.count(r"\b" + re.escape(word) + r"\b").sum())
            kw_evolution[word].append(count)

    # lista de papers para a tabela (dados já sanitizados no Python)
    papers_list = []
    for _, row in df.iterrows():
        authors = parse_authors(row["Author Names"])
        author_str = "; ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
        doi = row["DOI"].strip()
        if doi and not doi.startswith("http"):
            doi_url = "https://doi.org/" + doi
        elif doi.startswith("http"):
            doi_url = doi
        else:
            doi_url = ""
        papers_list.append({
            "title":   row["Paper Title"],
            "year":    int(row["Year"]),
            "type":    row["Publication Type"],
            "venue":   row["Publication Title"],
            "authors": author_str,
            "source":  row["_source"],
            "phase":   row["Phase"],
            "doi":     doi_url,
            "abstract": row["Abstract"][:100] + ("…" if len(row["Abstract"]) > 100 else ""),
        })

    return {
        "total":           len(df),
        "authors_unique":  len(set(all_authors)),
        "venues_unique":   int(df[mask_v]["_venue_norm"].nunique()),
        "year_min":        int(df["Year"].min()),
        "year_max":        int(df["Year"].max()),
        "by_year":         by_year,
        "by_type":         {str(k): int(v) for k, v in by_type.items()},
        "by_source":       {str(k): int(v) for k, v in by_source.items()},
        "by_phase":        {str(k): int(v) for k, v in by_phase.items()},
        "top_authors":     [[a, int(c)] for a, c in top_authors],
        "top_venues":      [[str(v), int(c)] for v, c in top_venues.items()],
        "top_keywords":    [[w, int(c)] for w, c in top_keywords],
        "kw_evolution":    kw_evolution,
        "phase_labels":    [p for p, _, _ in PHASE_RANGES],
        "papers":          papers_list,
    }


def print_report(stats: dict):
    print("\n" + "═" * 62)
    print("  ANÁLISE BIBLIOMÉTRICA — UML em Modelagem de Software")
    print("  Corpus: 2010–2024  |  SciSpace · Google Scholar · PubMed")
    print("═" * 62)
    print(f"\n  Total (pós-deduplicação): {stats['total']}")
    print(f"  Autores únicos:           {stats['authors_unique']}")
    print(f"  Venues únicos:            {stats['venues_unique']}")

    print("\n  Publicações por ano:")
    for y, c in stats["by_year"].items():
        bar = "█" * min(c, 40)
        print(f"    {y}  {c:3d}  {bar}")

    print("\n  Por fase:")
    for ph, cnt in stats["by_phase"].items():
        print(f"    {ph}: {cnt}")

    print("\n  Top 10 autores:")
    for author, count in stats["top_authors"][:10]:
        print(f"    {author}: {count}")

    print("\n  Top 10 keywords (títulos):")
    for kw, count in stats["top_keywords"][:10]:
        print(f"    {kw}: {count}")
    print()


# ── HTML ───────────────────────────────────────────────────────────────────────
# Dynamic content comes from JSON-serialized Python data (json.dumps escapes all
# strings). All CSV values inserted into the DOM use textContent or DOM methods —
# never innerHTML — preventing XSS from untrusted CSV content.
# Performance: charts update in-place (chart.update('none')), filters are
# debounced (180 ms), and the table is paginated (80 rows per page).
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>UML — Dashboard Bibliométrico</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
<style>
:root{
  --bg:#f0f4f9;--surface:#fff;--surface-2:#f8fafc;
  --border:#e2e8f0;--shadow:0 1px 4px rgba(0,0,0,.07);
  --text:#0f172a;--text-2:#475569;--muted:#94a3b8;
  --brand:#6366f1;--brand-h:#4f46e5;--brand-bg:rgba(99,102,241,.09);
  --p1:#f59e0b;--p2:#6366f1;--p3:#0ea5e9;
  --p1-bg:rgba(245,158,11,.1);--p2-bg:rgba(99,102,241,.1);--p3-bg:rgba(14,165,233,.1);
  --pos:#059669;--neg:#ef4444;
  --font:'Segoe UI',system-ui,sans-serif;
}
[data-theme=dark]{
  --bg:#0f172a;--surface:#1e293b;--surface-2:#162032;
  --border:#334155;--shadow:0 2px 8px rgba(0,0,0,.3);
  --text:#f1f5f9;--text-2:#94a3b8;--muted:#475569;
  --brand:#818cf8;--brand-h:#a5b4fc;--brand-bg:rgba(129,140,248,.12);
  --p1:#fbbf24;--p2:#818cf8;--p3:#38bdf8;
  --p1-bg:rgba(251,191,36,.12);--p2-bg:rgba(129,140,248,.12);--p3-bg:rgba(56,189,248,.12);
  --pos:#34d399;--neg:#f87171;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--font);background:var(--bg);color:var(--text);font-size:14px;transition:background .2s,color .2s}
a{color:var(--brand);text-decoration:none}
a:hover{text-decoration:underline}

/* Topbar */
.topbar{background:var(--surface);border-bottom:1px solid var(--border);padding:.8rem 2rem;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:200;box-shadow:var(--shadow);min-height:62px}
.topbar-brand .topbar-title{font-size:.95rem;font-weight:700;color:var(--brand)}
.topbar-brand .topbar-sub{font-size:.73rem;color:var(--text-2);margin-top:2px}
.topbar-right{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:.35rem;padding:.42rem .85rem;border-radius:8px;font-size:.78rem;font-weight:600;text-decoration:none;border:1px solid var(--border);background:var(--surface);color:var(--text);cursor:pointer;transition:.15s;white-space:nowrap}
.btn:hover{background:var(--surface-2);border-color:var(--brand);text-decoration:none;color:var(--brand)}
.btn-primary{background:var(--brand);color:#fff;border-color:var(--brand)}
.btn-primary:hover{opacity:.88}
#theme-btn{background:none;border:none;cursor:pointer;font-size:1.05rem;padding:.3rem .5rem;color:var(--text-2)}
#theme-btn:hover{color:var(--brand)}
/* Hero */
.hero{background:linear-gradient(135deg,#1e3a5f,#312e81,#4338ca);color:#fff;padding:20px 32px 18px}
.hero h1{font-size:1.35rem;font-weight:700;margin-bottom:4px}
.hero .sub{font-size:.82rem;opacity:.85;margin-bottom:2px}

/* Filters */
.filters{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px;align-items:center}
.filters label{font-size:.78rem;opacity:.85;display:flex;align-items:center;gap:6px}
.filters select,.yr-input{
  background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);
  color:#fff;border-radius:6px;padding:5px 9px;font-size:.78rem;cursor:pointer}
.yr-input{width:48px;text-align:center;cursor:text}
.yr-input::-webkit-inner-spin-button{-webkit-appearance:none}
.filters input[type=range]{padding:2px 0;width:100px;accent-color:#a5b4fc}
.phase-tab-btns{display:flex;gap:4px;flex-wrap:wrap}
.ph-btn{border:1px solid rgba(255,255,255,.3);background:rgba(255,255,255,.1);
  color:#fff;padding:4px 12px;border-radius:16px;font-size:.74rem;cursor:pointer;font-weight:500}
.ph-btn:hover{background:rgba(255,255,255,.25)}
.ph-btn.active{background:rgba(255,255,255,.9);color:#312e81;font-weight:700}

/* Layout */
main{max-width:1380px;margin:0 auto;padding:20px 20px 48px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}
.kpi{background:var(--surface);border-radius:12px;padding:16px 20px;
     border:1px solid var(--border);box-shadow:var(--shadow)}
.kpi-value{font-size:2rem;font-weight:700;color:var(--brand);line-height:1}
.kpi-label{font-size:.73rem;color:var(--muted);margin-top:5px}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.grid-3{display:grid;grid-template-columns:2fr 1fr 1fr;gap:14px;margin-bottom:14px}
.card{background:var(--surface);border-radius:12px;padding:16px;
      border:1px solid var(--border);box-shadow:var(--shadow)}
.card h2{font-size:.88rem;font-weight:600;color:var(--text);margin-bottom:12px;
         padding-bottom:8px;border-bottom:1px solid var(--border)}

/* Chart containers */
.ch{position:relative;width:100%}
.ch-sm{height:185px}.ch-md{height:245px}.ch-lg{height:310px}.ch-tl{height:210px}

/* Phase badges */
.phase-badges{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:10px}
.badge{padding:3px 10px;border-radius:20px;font-size:.7rem;font-weight:600;color:#fff}
.badge.p1{background:var(--p1)}.badge.p2{background:var(--p2)}.badge.p3{background:var(--p3)}

/* Table */
.table-controls{display:flex;gap:8px;margin-bottom:9px;flex-wrap:wrap;align-items:center}
.search-box{flex:1;min-width:160px;padding:6px 10px;border:1px solid var(--border);
            border-radius:7px;font-size:.8rem;outline:none;background:var(--surface);color:var(--text)}
.search-box:focus{border-color:var(--brand)}
select.tf{padding:6px 8px;border:1px solid var(--border);border-radius:7px;
          font-size:.8rem;background:var(--surface);color:var(--text);cursor:pointer}
.tbl-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.76rem;table-layout:fixed}
th{position:sticky;top:0;background:var(--surface-2);padding:7px 8px;text-align:left;
   border-bottom:2px solid var(--border);color:var(--muted);font-weight:600;
   white-space:nowrap;cursor:pointer;user-select:none;overflow:hidden;position:relative}
th:hover{color:var(--brand)}
td{padding:6px 8px;border-bottom:1px solid var(--border);vertical-align:top;color:var(--text);
   overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.td-t{white-space:normal;word-break:break-word}
.td-s{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rh{position:absolute;right:0;top:0;bottom:0;width:6px;cursor:col-resize;
    background:transparent;z-index:2;border-right:2px solid transparent;transition:border-color .15s}
.rh:hover,.rh.active{border-right-color:var(--brand)}
tr:hover td{background:var(--surface-2)}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:4px}
.dot.p1{background:var(--p1)}.dot.p2{background:var(--p2)}.dot.p3{background:var(--p3)}
#count-label{font-size:.76rem;color:var(--muted);margin-left:auto}
#load-more{display:none;width:100%;margin-top:8px;padding:8px;background:var(--surface-2);
  border:1px solid var(--border);border-radius:7px;color:var(--brand);
  font-size:.8rem;cursor:pointer;font-weight:500}
#load-more:hover{background:var(--brand-bg)}
@media(max-width:900px){.kpis{grid-template-columns:1fr 1fr}.grid-2,.grid-3{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="topbar">
  <div class="topbar-brand">
    <div class="topbar-title">UML em Modelagem de Software</div>
    <div class="topbar-sub">Marcos Antonio Barbosa Stingher · UNOESC Sistemas de Informação · 2025</div>
  </div>
  <div class="topbar-right">
    <a href="resumo_executivo.html" class="btn">&#128197; Resumo Executivo</a>
    <a href="insights_uml.html" class="btn btn-primary">&#128202; Insights Aprofundados</a>
    <button id="theme-btn" onclick="toggleTheme()">&#9790; Modo Escuro</button>
  </div>
</div>
<div class="hero">
  <h1>Dashboard Bibliométrico</h1>
  <p class="sub">SciSpace · SciSpace Full-Text · Google Scholar · PubMed &nbsp;|&nbsp; 2010–2024</p>
  <div class="filters">
    <label>Período:</label>
    <input class="yr-input" type="number" id="year-start-txt" min="2010" max="2024" value="2010">
    <input type="range" id="year-start" min="2010" max="2024" value="2010">
    <span style="opacity:.7">–</span>
    <input type="range" id="year-end" min="2010" max="2024" value="2024">
    <input class="yr-input" type="number" id="year-end-txt" min="2010" max="2024" value="2024">
    <label>Fonte:<select id="fs"><option value="">Todas</option>
      <option>SciSpace</option><option>SciSpace Full-Text</option>
      <option>Google Scholar</option><option>PubMed</option></select></label>
    <label>Tipo:<select id="ft"><option value="">Todos</option></select></label>
    <div class="phase-tab-btns">
      <button class="ph-btn active" data-ph="">Todas as Fases</button>
      <button class="ph-btn" data-ph="Fase 1 — Consolidação (2010–2014)">F1</button>
      <button class="ph-btn" data-ph="Fase 2 — Expansão MDE (2015–2019)">F2</button>
      <button class="ph-btn" data-ph="Fase 3 — Especialização (2020–2024)">F3</button>
    </div>
  </div>
</div>

<main>
<div class="kpis">
  <div class="kpi"><div class="kpi-value" id="kv-total">–</div>
    <div class="kpi-label">Artigos analisados</div></div>
  <div class="kpi"><div class="kpi-value">15</div>
    <div class="kpi-label">Anos de cobertura (2010–2024)</div></div>
  <div class="kpi"><div class="kpi-value" id="kv-authors">–</div>
    <div class="kpi-label">Autores únicos</div></div>
  <div class="kpi"><div class="kpi-value" id="kv-venues">–</div>
    <div class="kpi-label">Periódicos / Conferências</div></div>
</div>

<div class="card" style="margin-bottom:14px">
  <h2>Evolução Temporal das Publicações (2010–2024)</h2>
  <div class="phase-badges">
    <span class="badge p1">Fase 1 · Consolidação (2010–2014)</span>
    <span class="badge p2">Fase 2 · Expansão MDE (2015–2019)</span>
    <span class="badge p3">Fase 3 · Especialização (2020–2024)</span>
  </div>
  <div class="ch ch-tl"><canvas id="c-timeline"></canvas></div>
</div>

<div class="grid-3">
  <div class="card"><h2>Publicações por Fase</h2>
    <div class="ch ch-sm"><canvas id="c-phase"></canvas></div></div>
  <div class="card"><h2>Tipo de Publicação</h2>
    <div class="ch ch-sm"><canvas id="c-type"></canvas></div></div>
  <div class="card"><h2>Base de Dados</h2>
    <div class="ch ch-sm"><canvas id="c-source"></canvas></div></div>
</div>

<div class="grid-2">
  <div class="card"><h2>Top 20 Autores</h2>
    <div class="ch ch-md"><canvas id="c-authors"></canvas></div></div>
  <div class="card"><h2>Top 15 Periódicos e Conferências</h2>
    <div class="ch ch-md"><canvas id="c-venues"></canvas></div></div>
</div>

<div class="grid-2">
  <div class="card"><h2>Palavras-Chave dos Títulos (Top 25)</h2>
    <div class="ch ch-lg"><canvas id="c-keywords"></canvas></div></div>
  <div class="card"><h2>Evolução Temática por Fase</h2>
    <div class="ch ch-lg"><canvas id="c-evolution"></canvas></div></div>
</div>

<div class="card">
  <h2>Corpus Completo</h2>
  <div class="table-controls">
    <input class="search-box" id="ts" type="text" placeholder="Buscar título, autor, periódico…" autocomplete="off">
    <select class="tf" id="tp">
      <option value="">Todas as fases</option>
      <option>Fase 1 — Consolidação (2010–2014)</option>
      <option>Fase 2 — Expansão MDE (2015–2019)</option>
      <option>Fase 3 — Especialização (2020–2024)</option>
    </select>
    <select class="tf" id="tt"><option value="">Todos os tipos</option></select>
    <span id="count-label"></span>
  </div>
  <div class="tbl-wrap">
    <table>
      <thead><tr>
        <th data-col="year" style="width:52px">Ano<span class="rh"></span></th>
        <th data-col="title" style="width:280px">Título<span class="rh"></span></th>
        <th data-col="authors" style="width:160px">Autores<span class="rh"></span></th>
        <th data-col="venue" style="width:170px">Venue<span class="rh"></span></th>
        <th data-col="type" style="width:120px">Tipo<span class="rh"></span></th>
        <th data-col="phase" style="width:55px">Fase<span class="rh"></span></th>
        <th style="width:44px">DOI</th>
      </tr></thead>
      <tbody id="tb"></tbody>
    </table>
  </div>
  <button id="load-more"></button>
</div>
</main>
<footer style="text-align:center;color:var(--muted);font-size:.7rem;padding:16px;border-top:1px solid var(--border)">
  Análise bibliométrica — UML em Modelagem de Software (2010–2024) &nbsp;|&nbsp;
  Marcos Antonio Barbosa Stingher &nbsp;|&nbsp; UNOESC Chapecó, 2025
</footer>

<script>
Chart.defaults.animation = false;
Chart.defaults.plugins.legend.labels.boxWidth = 11;
Chart.defaults.plugins.legend.labels.font = {size:9};

const R = __DATA__;

// ── CSS variable reader ────────────────────────────────────────────────────────
function C(v){ return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }

// ── Theme ─────────────────────────────────────────────────────────────────────
(function(){
  var saved = localStorage.getItem('theme') || 'light';
  if(saved === 'dark') document.documentElement.setAttribute('data-theme','dark');
  updateThemeBtn();
})();
function updateThemeBtn(){
  var btn = document.getElementById('theme-btn');
  if(!btn) return;
  var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  btn.textContent = isDark ? '☀ Modo Claro' : '☾ Modo Escuro';
}
function toggleTheme(){
  var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  if(isDark){
    document.documentElement.removeAttribute('data-theme');
    localStorage.setItem('theme','light');
  } else {
    document.documentElement.setAttribute('data-theme','dark');
    localStorage.setItem('theme','dark');
  }
  updateThemeBtn();
  // Destroy and recreate all charts so they use new CSS variables
  Object.values(CH).forEach(function(c){ c.destroy(); });
  for(var k in CH) delete CH[k];
  Chart.defaults.color = C('--text-2');
  Chart.defaults.borderColor = C('--border');
  requestAnimationFrame(function(){
    drawEvolution();
    updateAll();
  });
}

// ── State ─────────────────────────────────────────────────────────────────────
let Y0=2010,Y1=2024,fSrc="",fType="",fPhase="";
let tQ="",tPhase="",tType="",sCol="year",sDir=-1;
let _rows=[],_shown=80;
const PAGE=300;

const PDOT={"Fase 1 — Consolidação (2010–2014)":"p1",
  "Fase 2 — Expansão MDE (2015–2019)":"p2",
  "Fase 3 — Especialização (2020–2024)":"p3"};
const PNUM={"Fase 1 — Consolidação (2010–2014)":"1",
  "Fase 2 — Expansão MDE (2015–2019)":"2",
  "Fase 3 — Especialização (2020–2024)":"3"};

// ── Helpers ───────────────────────────────────────────────────────────────────
function debounce(fn,ms){let t;return(...a)=>{clearTimeout(t);t=setTimeout(()=>fn(...a),ms);};}
function countBy(arr,k){const m={};arr.forEach(p=>{const v=p[k]||"?";m[v]=(m[v]||0)+1;});return m;}
function topN(obj,n){return Object.entries(obj).sort((a,b)=>b[1]-a[1]).slice(0,n);}
function filtered(){
  return R.papers.filter(p=>{
    if(p.year<Y0||p.year>Y1)return false;
    if(fSrc&&p.source!==fSrc)return false;
    if(fType&&p.type!==fType)return false;
    if(fPhase&&p.phase!==fPhase)return false;
    return true;
  });
}

// ── Chart registry — update data in-place, never destroy after first render ───
const CH={};
function ch(id,cfg){
  if(CH[id]){CH[id].data=cfg.data;CH[id].update('none');return;}
  CH[id]=new Chart(document.getElementById(id),cfg);
}

// Axis presets
function gridX(){
  var dark=document.documentElement.getAttribute('data-theme')==='dark';
  return {color: dark ? 'rgba(148,163,184,0.12)' : '#e2e8f0'};
}
const noGridY={grid:{display:false},ticks:{font:{size:9}}};
function linX(){return {beginAtZero:true,grid:gridX(),ticks:{font:{size:9}}};}
function logX(){return {
  type:'logarithmic',min:0.5,grid:gridX(),
  ticks:{font:{size:9},maxTicksLimit:6,
    callback:v=>{const n=Number(v);
      return[1,2,3,5,10,20,30,50,100,200].includes(n)?n:null;}}
};}
function xScale(vals){
  const mx=Math.max(...vals),mn=Math.min(...vals.filter(v=>v>0));
  return mx/mn>5?logX():linX();
}

// ── Chart renderers ───────────────────────────────────────────────────────────
function drawTimeline(papers){
  const by=countBy(papers,"year"),labs=[],vals=[],cols=[];
  const c1=C('--p1'),c2=C('--p2'),c3=C('--p3');
  for(let y=Y0;y<=Y1;y++){
    labs.push(y);vals.push(by[y]||0);
    cols.push(y<=2014?c1:y<=2019?c2:c3);
  }
  const ma=vals.map((_,i)=>{
    const w=vals.slice(Math.max(0,i-1),i+2);
    return+(w.reduce((a,b)=>a+b,0)/w.length).toFixed(1);
  });
  ch("c-timeline",{type:"bar",data:{labels:labs,datasets:[
    {label:"Publicações",data:vals,backgroundColor:cols,borderRadius:4,borderSkipped:false},
    {label:"Média móvel",data:ma,type:"line",borderColor:"#f59e0b",
     borderWidth:2,pointRadius:2.5,tension:.35,fill:false}
  ]},options:{responsive:true,maintainAspectRatio:false,
    interaction:{mode:"index",intersect:false},
    plugins:{legend:{position:"top",labels:{font:{size:10},boxWidth:12}}},
    scales:{y:{beginAtZero:true,grid:gridX(),ticks:{font:{size:10}},
               title:{display:true,text:"Artigos",font:{size:10}}},
            x:{grid:{display:false},ticks:{font:{size:10}}}}}});
}

function drawPhase(papers){
  const bp=countBy(papers,"phase");
  const keys=["Fase 1 — Consolidação (2010–2014)",
               "Fase 2 — Expansão MDE (2015–2019)",
               "Fase 3 — Especialização (2020–2024)"];
  ch("c-phase",{type:"bar",data:{
    labels:["Fase 1\n(2010–14)","Fase 2\n(2015–19)","Fase 3\n(2020–24)"],
    datasets:[{data:keys.map(k=>bp[k]||0),
      backgroundColor:[C('--p1'),C('--p2'),C('--p3')],borderRadius:5}]
  },options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},
    scales:{y:{beginAtZero:true,grid:gridX(),ticks:{font:{size:9}}},
            x:{grid:{display:false},ticks:{font:{size:9}}}}}});
}

// Categorical palette — distinct from the phase colors (amber/indigo/cyan)
const CAT=['#4f86c6','#e07855','#5bac9e','#9d63c7','#e8b84b','#4caa72','#e04c8e'];

function drawType(papers){
  const raw=topN(countBy(papers,"type"),7);
  ch("c-type",{type:"doughnut",data:{
    labels:raw.map(r=>r[0]),
    datasets:[{data:raw.map(r=>r[1]),
      backgroundColor:raw.map((_,i)=>CAT[i%CAT.length]),
      borderColor:C('--surface'),borderWidth:2}]
  },options:{responsive:true,maintainAspectRatio:false,cutout:"58%",
    plugins:{legend:{position:"right"}}}});
}

function drawSource(papers){
  const raw=topN(countBy(papers,"source"),5);
  ch("c-source",{type:"doughnut",data:{
    labels:raw.map(r=>r[0]),
    datasets:[{data:raw.map(r=>r[1]),
      backgroundColor:raw.map((_,i)=>CAT[i%CAT.length]),
      borderColor:C('--surface'),borderWidth:2}]
  },options:{responsive:true,maintainAspectRatio:false,cutout:"58%",
    plugins:{legend:{position:"right"}}}});
}

function drawAuthors(papers){
  const cnt={};
  papers.forEach(p=>p.authors.split(";").forEach(a=>{
    const k=a.replace(/ et al\./,"").trim();
    if(k.length>2)cnt[k]=(cnt[k]||0)+1;
  }));
  const top=topN(cnt,20).reverse();
  const vals=top.map(r=>r[1]);
  ch("c-authors",{type:"bar",data:{
    labels:top.map(r=>r[0]),
    datasets:[{data:vals,backgroundColor:'#4f86c6',borderRadius:3}]
  },options:{indexAxis:"y",responsive:true,maintainAspectRatio:false,
    plugins:{legend:{display:false}},
    scales:{x:{...xScale(vals),ticks:{...xScale(vals).ticks,stepSize:1}},y:noGridY}}});
}

function drawVenues(papers){
  const cnt={};
  papers.forEach(p=>{if(p.venue&&p.venue.trim().length>2)
    cnt[p.venue.trim()]=(cnt[p.venue.trim()]||0)+1;});
  const top=topN(cnt,15).reverse();
  const vals=top.map(r=>r[1]);
  ch("c-venues",{type:"bar",data:{
    labels:top.map(r=>r[0].length>34?r[0].slice(0,31)+"…":r[0]),
    datasets:[{data:vals,backgroundColor:'#5bac9e',borderRadius:3}]
  },options:{indexAxis:"y",responsive:true,maintainAspectRatio:false,
    plugins:{legend:{display:false}},
    scales:{x:xScale(vals),y:noGridY}}});
}

function drawKeywords(papers){
  const STOP=new Set(["a","an","and","are","as","at","be","been","but","by","do","does",
    "for","from","has","have","in","into","is","it","its","not","of","on","or","out","s",
    "so","than","that","the","their","them","this","those","to","up","use","used","using",
    "via","was","we","were","with","based","new","two","approach","method","framework",
    "study","analysis","survey","review","work","paper","research","case","results",
    "system","systems","data","tool","tools","applied","towards","within",
    "uma","de","do","da","em","para","com","por","se","ao","na","no","e","o","a","ou"]);
  const cnt={};
  papers.forEach(p=>{
    (p.title||"").toLowerCase().replace(/[^a-z\s]/g," ")
      .split(/\s+/).forEach(w=>{if(w.length>=3&&!STOP.has(w))cnt[w]=(cnt[w]||0)+1;});
  });
  const top=topN(cnt,25).reverse();
  const vals=top.map(r=>r[1]);
  const UML=new Set(["uml","modeling","model","diagram","class","sequence","design","unified"]);
  const MDE=new Set(["driven","mde","mda","transformation","metamodel","dsl","generation","language"]);
  ch("c-keywords",{type:"bar",data:{
    labels:top.map(r=>r[0]),
    datasets:[{data:vals,borderRadius:3,
      backgroundColor:'#e07855'}]
  },options:{indexAxis:"y",responsive:true,maintainAspectRatio:false,
    plugins:{legend:{display:false},
      tooltip:{callbacks:{label:ctx=>" "+ctx.raw+" ocorrências"}}},
    scales:{x:xScale(vals),y:noGridY}}});
}

function drawEvolution(){
  const COLS=['#4f86c6','#e07855','#5bac9e','#9d63c7','#e8b84b','#4caa72','#e04c8e','#b06b3c'];
  const datasets=Object.entries(R.kw_evolution).map(([word,counts],i)=>({
    label:word,data:counts,borderColor:COLS[i%COLS.length],
    backgroundColor:COLS[i%COLS.length]+"22",borderWidth:2,
    pointRadius:4,pointHoverRadius:6,tension:.3,fill:false
  }));
  ch("c-evolution",{type:"line",data:{
    labels:["F1 (2010–14)","F2 (2015–19)","F3 (2020–24)"],datasets
  },options:{responsive:true,maintainAspectRatio:false,
    interaction:{mode:"index",intersect:false},
    plugins:{legend:{position:"right"}},
    scales:{y:{beginAtZero:true,grid:gridX(),ticks:{font:{size:9}},
               title:{display:true,text:"Ocorrências nos títulos",font:{size:9}}},
            x:{grid:{display:false},ticks:{font:{size:9}}}}}});
}

// ── Table ─────────────────────────────────────────────────────────────────────
function computeRows(papers){
  const q=tQ.toLowerCase();
  let rows=papers.filter(p=>{
    if(q&&!p.title.toLowerCase().includes(q)
        &&!p.authors.toLowerCase().includes(q)
        &&!p.venue.toLowerCase().includes(q))return false;
    if(tPhase&&p.phase!==tPhase)return false;
    if(tType&&p.type!==tType)return false;
    return true;
  });
  rows.sort((a,b)=>{
    const av=a[sCol]??"",bv=b[sCol]??"";
    if(typeof av==="number")return sDir*(av-bv);
    return sDir*String(av).localeCompare(String(bv));
  });
  return rows;
}

function mkTd(cls,val){
  const el=document.createElement("td");
  if(cls)el.className=cls;el.textContent=val||"–";return el;
}

function renderSlice(slice,replace){
  const frag=document.createDocumentFragment();
  slice.forEach(p=>{
    const tr=document.createElement("tr");
    if(p.abstract)tr.title=p.abstract;
    tr.appendChild(mkTd("",p.year));
    tr.appendChild(mkTd("td-t",p.title));
    tr.appendChild(mkTd("td-s",p.authors));
    tr.appendChild(mkTd("td-s",p.venue));
    tr.appendChild(mkTd("",p.type));
    const phTd=document.createElement("td");
    const dot=document.createElement("span");
    dot.className="dot "+(PDOT[p.phase]||"p1");
    phTd.appendChild(dot);
    phTd.appendChild(document.createTextNode(PNUM[p.phase]||"?"));
    tr.appendChild(phTd);
    const doiTd=document.createElement("td");
    if(p.doi&&p.doi.startsWith("https://")){
      const a=document.createElement("a");
      a.href=p.doi;a.target="_blank";a.rel="noopener noreferrer";a.textContent="↗";
      doiTd.appendChild(a);
    }else doiTd.textContent="–";
    tr.appendChild(doiTd);
    frag.appendChild(tr);
  });
  const tb=document.getElementById("tb");
  if(replace)tb.replaceChildren(frag);else tb.appendChild(frag);
}

function syncMoreBtn(){
  const btn=document.getElementById("load-more"),rem=_rows.length-_shown;
  if(rem>0){
    btn.textContent="Mostrar mais "+Math.min(PAGE,rem)+" artigos ("+rem+" restantes)";
    btn.style.display="";
  }else btn.style.display="none";
}

function updateTable(papers){
  _rows=computeRows(papers);_shown=PAGE;
  document.getElementById("count-label").textContent=
    _rows.length+" artigo"+(_rows.length!==1?"s":"");
  renderSlice(_rows.slice(0,_shown),true);
  syncMoreBtn();
}

// ── Master update ─────────────────────────────────────────────────────────────
function updateAll(){
  const papers=filtered();
  document.getElementById("kv-total").textContent=papers.length;
  document.getElementById("kv-authors").textContent=R.authors_unique;
  document.getElementById("kv-venues").textContent=R.venues_unique;
  updateTable(papers);
  requestAnimationFrame(()=>{
    drawTimeline(papers);drawPhase(papers);drawType(papers);drawSource(papers);
    drawAuthors(papers);drawVenues(papers);drawKeywords(papers);
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded",()=>{
  const types=[...new Set(R.papers.map(p=>p.type))].sort();
  ["ft","tt"].forEach(id=>{
    const sel=document.getElementById(id);
    types.forEach(t=>{const o=document.createElement("option");o.value=o.textContent=t;sel.appendChild(o);});
  });

  // Year sliders + text inputs (synced)
  const sEl=document.getElementById("year-start"),eEl=document.getElementById("year-end");
  const sTxt=document.getElementById("year-start-txt"),eTxt=document.getElementById("year-end-txt");
  const dAll=debounce(updateAll,200);
  function syncSliders(){
    if(+sEl.value>+eEl.value){const t=sEl.value;sEl.value=eEl.value;eEl.value=t;}
    Y0=+sEl.value;Y1=+eEl.value;
    sTxt.value=Y0;eTxt.value=Y1;
    dAll();
  }
  sEl.addEventListener("input",syncSliders);eEl.addEventListener("input",syncSliders);
  sTxt.addEventListener("change",function(){
    var v=Math.max(2010,Math.min(2024,+this.value||2010));
    this.value=v;sEl.value=v;syncSliders();
  });
  eTxt.addEventListener("change",function(){
    var v=Math.max(2010,Math.min(2024,+this.value||2024));
    this.value=v;eEl.value=v;syncSliders();
  });

  document.getElementById("fs").addEventListener("change",function(){fSrc=this.value;updateAll();});
  document.getElementById("ft").addEventListener("change",function(){fType=this.value;updateAll();});

  // Phase tab buttons in header
  document.querySelectorAll('.ph-btn').forEach(function(btn){
    btn.addEventListener('click',function(){
      fPhase=this.getAttribute('data-ph');
      document.querySelectorAll('.ph-btn').forEach(function(b){
        b.classList.toggle('active', b.getAttribute('data-ph') === fPhase);
      });
      // Sync year range if phase selected
      if(fPhase==="Fase 1 — Consolidação (2010–2014)"){Y0=2010;Y1=2014;sEl.value=2010;eEl.value=2014;sTxt.value=2010;eTxt.value=2014;}
      else if(fPhase==="Fase 2 — Expansão MDE (2015–2019)"){Y0=2015;Y1=2019;sEl.value=2015;eEl.value=2019;sTxt.value=2015;eTxt.value=2019;}
      else if(fPhase==="Fase 3 — Especialização (2020–2024)"){Y0=2020;Y1=2024;sEl.value=2020;eEl.value=2024;sTxt.value=2020;eTxt.value=2024;}
      else{Y0=2010;Y1=2024;sEl.value=2010;eEl.value=2024;sTxt.value=2010;eTxt.value=2024;}
      updateAll();
    });
  });

  const dTbl=debounce(()=>updateTable(filtered()),150);
  document.getElementById("ts").addEventListener("input",function(){tQ=this.value;dTbl();});
  document.getElementById("tp").addEventListener("change",function(){tPhase=this.value;updateTable(filtered());});
  document.getElementById("tt").addEventListener("change",function(){tType=this.value;updateTable(filtered());});

  document.querySelectorAll("th[data-col]").forEach(th=>{
    th.addEventListener("click",e=>{
      if(e.target.classList.contains('rh')) return;
      if(sCol===th.dataset.col)sDir*=-1;else{sCol=th.dataset.col;sDir=-1;}
      updateTable(filtered());
    });
  });

  // Column resize
  document.querySelectorAll("th .rh").forEach(rh=>{
    const th = rh.parentElement;
    let startX, startW;
    rh.addEventListener("mousedown",e=>{
      e.preventDefault(); e.stopPropagation();
      startX = e.clientX; startW = th.offsetWidth;
      rh.classList.add("active");
      const onMove = e2=>{
        const w = Math.max(40, startW + e2.clientX - startX);
        th.style.width = w+"px"; th.style.minWidth = w+"px";
      };
      const onUp = ()=>{
        rh.classList.remove("active");
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  });

  document.getElementById("load-more").addEventListener("click",()=>{
    renderSlice(_rows.slice(_shown,_shown+PAGE),false);
    _shown+=PAGE;syncMoreBtn();
  });

  Chart.defaults.color = C('--text-2');
  Chart.defaults.borderColor = C('--border');
  drawEvolution();
  updateAll();
});
</script>
</body>
</html>
"""


def generate_html(stats: dict) -> str:
    data_json = json.dumps(stats, ensure_ascii=False, separators=(",", ":"))
    return HTML_TEMPLATE.replace("__DATA__", data_json)


def main():
    print("\nCarregando CSVs...")
    df_raw = load_csvs()
    print(f"  Registros brutos: {len(df_raw)}")

    print("Limpando e deduplicando...")
    df = clean(df_raw)
    print(f"  Corpus final: {len(df)} artigos (2010–2024)")

    print("Calculando estatísticas...")
    stats = build_stats(df)

    print_report(stats)

    print(f"Salvando {OUTPUT_JSON.name}...")
    OUTPUT_JSON.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Gerando {OUTPUT_HTML.name}...")
    html = generate_html(stats)
    OUTPUT_HTML.write_text(html, encoding="utf-8")

    size_kb = OUTPUT_HTML.stat().st_size // 1024
    print(f"\n  ✓ Dashboard: {OUTPUT_HTML}  ({size_kb} KB)")
    print("  Abra o arquivo no navegador para visualizar.\n")


if __name__ == "__main__":
    main()
