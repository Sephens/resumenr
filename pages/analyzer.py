"""
pages/analyzer.py
─────────────────
Single resume upload + full NLP analysis view.
"""

import json
import io
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from utils.nlp_engine import (
    extract_pdf_text, extract_entities,
    infer_seniority, compute_ats_score,
    SPACY_AVAILABLE, _model_name,
)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _tags_html(items: list[str], css_class: str) -> str:
    if not items:
        return "<span style='color:#404060;font-size:13px'>None detected</span>"
    tags = "".join(f'<span class="tag {css_class}">{item}</span>' for item in items)
    return f'<div class="tag-wrap">{tags}</div>'


def _metric_card(num, label, color="#7c6af7"):
    return f"""
    <div class="metric-card">
        <div class="metric-num" style="color:{color}">{num}</div>
        <div class="metric-label">{label}</div>
    </div>
    """


def _section(title: str, content_html: str, accent=True):
    cls = "ner-card ner-card-accent" if accent else "ner-card"
    st.markdown(f"""
    <div class="{cls}">
        <div class="section-label">{title}</div>
        {content_html}
    </div>
    """, unsafe_allow_html=True)


# ── ATS gauge ────────────────────────────────────────────────────────────────
def _render_ats_gauge(score: int):
    color = "#4ade80" if score >= 75 else "#fbbf24" if score >= 50 else "#f97474"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "ATS Score", "font": {"color": "#c0c0d8", "size": 14, "family": "Space Grotesk"}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#404060", "tickfont": {"color": "#606080"}},
            "bar": {"color": color, "thickness": 0.25},
            "bgcolor": "#1a1a28",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 40],   "color": "rgba(249,116,116,0.08)"},
                {"range": [40, 70],  "color": "rgba(251,191,36,0.08)"},
                {"range": [70, 100], "color": "rgba(74,222,128,0.08)"},
            ],
            "threshold": {"line": {"color": color, "width": 3}, "thickness": 0.75, "value": score},
        },
        number={"font": {"color": color, "size": 40, "family": "Space Grotesk"}, "suffix": "/100"},
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=220, margin=dict(t=30, b=10, l=20, r=20),
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Tech category bar chart ───────────────────────────────────────────────────
def _render_tech_chart(technologies: dict):
    if not technologies:
        st.markdown("<span style='color:#404060;font-size:13px'>No technologies detected</span>", unsafe_allow_html=True)
        return
    cats   = list(technologies.keys())
    counts = [len(v) for v in technologies.values()]
    colors = ["#7c6af7", "#2dd4bf", "#fbbf24", "#4ade80", "#f472b6", "#22d3ee", "#fb923c"]
    fig = go.Figure(go.Bar(
        x=counts, y=cats, orientation="h",
        marker_color=colors[:len(cats)],
        text=counts, textposition="outside",
        textfont={"color": "#c0c0d8", "size": 12},
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=max(180, len(cats) * 44),
        margin=dict(t=10, b=10, l=10, r=40),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, color="#404060"),
        yaxis=dict(showgrid=False, zeroline=False, color="#9090a8", tickfont={"size": 13}),
        font={"family": "Space Grotesk"},
        bargap=0.35,
    )
    st.plotly_chart(fig, use_container_width=True)


# ── NER entity highlighted text ──────────────────────────────────────────────
def _render_ner_text(raw_text: str, entities: list[dict]):
    """Render first 2000 chars of text with NER entities highlighted."""
    snippet = raw_text[:2000]
    # Sort by start position, filter to those within snippet
    ents = sorted(
        [e for e in entities if e["start"] < len(snippet)],
        key=lambda x: x["start"],
    )
    color_map = {
        "ORG": "tag-company", "PERSON": "tag-edu",
        "GPE": "tag-loc",     "LOC": "tag-loc",
        "DATE": "tag-title",  "MONEY": "tag-noun",
    }
    html_parts = []
    cursor = 0
    for ent in ents:
        s, e = ent["start"], min(ent["end"], len(snippet))
        if s < cursor:
            continue
        # Plain text before entity
        html_parts.append(snippet[cursor:s].replace("\n", " "))
        label = ent["label"]
        css = color_map.get(label, "tag-noun")
        html_parts.append(
            f'<span class="tag {css}" title="{label}" style="font-size:12px;padding:1px 7px;margin:0 2px">'
            f'{snippet[s:e]}</span>'
        )
        cursor = e
    html_parts.append(snippet[cursor:].replace("\n", " "))
    html = "".join(html_parts)
    st.markdown(
        f'<div style="background:#0d0d1a;border:1px solid rgba(255,255,255,0.06);border-radius:12px;'
        f'padding:18px;font-size:13px;line-height:1.9;color:#a0a0c0;max-height:280px;overflow-y:auto">'
        f'{html}</div>',
        unsafe_allow_html=True,
    )


# ── Main render ───────────────────────────────────────────────────────────────
def render():
    # ── Header ───────────────────────────────────────────────────────────────
    st.markdown("""
    <h2 style="font-size:32px;font-weight:700;letter-spacing:-0.5px;color:#e8e8f0;margin-bottom:4px">
        Resume Analyzer
    </h2>
    <p style="color:#6060a0;font-size:15px;margin-bottom:28px">
        Upload a PDF résumé — spaCy NER + noun_chunks extracts every professional signal.
    </p>
    """, unsafe_allow_html=True)

    # ── Model status banner ───────────────────────────────────────────────────
    if SPACY_AVAILABLE:
        st.success(f"✅ spaCy model loaded: **{_model_name}** — full NER pipeline active")
    else:
        st.warning(
            "⚠️ spaCy model not found. Running in **regex-fallback mode** — "
            "tech skills and soft skills still work. "
            "Install spaCy to enable full NER: see the Setup tab in the sidebar."
        )
        with st.expander("📦 How to install spaCy"):
            st.code("""pip install spacy
python -m spacy download en_core_web_lg
# or for smaller footprint:
python -m spacy download en_core_web_sm""", language="bash")

    st.markdown("---")

    # ── Upload ────────────────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "Drop your resume PDF here",
        type=["pdf"],
        label_visibility="collapsed",
    )

    if not uploaded:
        st.markdown("""
        <div style="text-align:center;padding:40px 0;color:#404060">
            <div style="font-size:48px;margin-bottom:12px">📄</div>
            <div style="font-size:15px">Upload a PDF resume to begin analysis</div>
            <div style="font-size:12px;margin-top:6px;color:#303050">Supports any resume, CV, or bio in PDF format</div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Extract ───────────────────────────────────────────────────────────────
    cache_key = f"result_{uploaded.name}_{uploaded.size}"
    if cache_key not in st.session_state:
        with st.spinner("🔍 Parsing PDF and running NLP pipeline…"):
            prog = st.progress(0, text="Extracting PDF text…")
            raw_text, page_count = extract_pdf_text(uploaded)
            prog.progress(30, text="Running NER pipeline…")
            entities = extract_entities(raw_text)
            prog.progress(70, text="Computing scores…")
            seniority, est_years = infer_seniority(raw_text, entities)
            ats = compute_ats_score(entities, raw_text)
            prog.progress(100, text="Done!")
            prog.empty()
        st.session_state[cache_key] = {
            "raw_text": raw_text, "page_count": page_count,
            "entities": entities, "seniority": seniority,
            "est_years": est_years, "ats": ats,
        }
        st.success(f"✅ Analysis complete — {page_count} page(s) processed")

    cached = st.session_state[cache_key]
    ents   = cached["entities"]
    raw    = cached["raw_text"]
    ats    = cached["ats"]

    # ── Stats row ─────────────────────────────────────────────────────────────
    cols = st.columns(6)
    stat_data = [
        (len(ents["skills"]),       "Soft Skills",   "#7c6af7"),
        (len(ents["tech_flat"]),    "Technologies",  "#2dd4bf"),
        (len(ents["companies"]),    "Companies",     "#fbbf24"),
        (len(ents["education"]),    "Education",     "#f472b6"),
        (ents["word_count"],        "Words",         "#94a3b8"),
        (ats["total"],              "ATS Score",     "#4ade80" if ats["total"]>=70 else "#fbbf24"),
    ]
    for col, (num, label, color) in zip(cols, stat_data):
        with col:
            st.markdown(_metric_card(num, label, color), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["🏷️ Entities", "💻 Tech Stack", "🔗 Noun Chunks", "📊 ATS Score", "📄 Raw Text"]
    )

    # ── Tab 1: Entities ───────────────────────────────────────────────────────
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            _section("⚡ Soft Skills & Competencies",
                     _tags_html(ents["skills"], "tag-skill"))
            _section("🏢 Companies & Organisations",
                     _tags_html(ents["companies"], "tag-company"))
            _section("📍 Locations & Regions",
                     _tags_html(ents["locations"], "tag-loc"))
        with c2:
            _section("🏷️ Job Titles & Roles",
                     _tags_html(ents["job_titles"], "tag-title"))
            _section("🎓 Education & Certifications",
                     _tags_html(ents["education"], "tag-edu"))
            # Contact info
            contact_html = ""
            for e in ents["emails"][:3]:
                contact_html += f'<span class="tag tag-noun">✉ {e}</span> '
            for p in ents["phones"][:2]:
                contact_html += f'<span class="tag tag-noun">📞 {p}</span> '
            for l in ents["linkedin"][:1]:
                contact_html += f'<span class="tag tag-skill">🔗 {l}</span> '
            for g in ents["github"][:1]:
                contact_html += f'<span class="tag tag-tech">🐙 {g}</span> '
            if not contact_html:
                contact_html = "<span style='color:#404060;font-size:13px'>None detected</span>"
            _section("📬 Contact Information",
                     f'<div class="tag-wrap">{contact_html}</div>')

        # Seniority
        sen_color = {"Executive":"#f472b6","Principal / Staff":"#a594ff",
                     "Senior":"#2dd4bf","Mid-level":"#fbbf24","Junior / Mid":"#fb923c",
                     "Junior / Entry":"#94a3b8","Entry":"#94a3b8"}.get(cached["seniority"], "#94a3b8")
        st.markdown(
            f'<div class="ner-card" style="display:flex;align-items:center;gap:16px">'
            f'<div style="font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:#5050a0">Inferred Seniority</div>'
            f'<span class="tag" style="background:rgba(124,106,247,0.12);color:{sen_color};border:1px solid {sen_color}40;font-size:15px">'
            f'{cached["seniority"]}</span>'
            f'<div style="color:#404060;font-size:13px">~{cached["est_years"]} yrs experience</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # NER highlighted text
        if ents["ner_entities"]:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="section-label">🔬 NER — Highlighted Text Snippet</div>', unsafe_allow_html=True)
            _render_ner_text(raw, ents["ner_entities"])

    # ── Tab 2: Tech Stack ─────────────────────────────────────────────────────
    with tab2:
        if ents["technologies"]:
            c1, c2 = st.columns([1, 1])
            with c1:
                st.markdown('<div class="section-label">Tech categories detected</div>', unsafe_allow_html=True)
                _render_tech_chart(ents["technologies"])
            with c2:
                for cat, terms in ents["technologies"].items():
                    cat_colors = {
                        "Languages": "tag-skill", "Frontend": "tag-tech",
                        "Backend": "tag-title",   "Databases": "tag-company",
                        "Cloud & DevOps": "tag-noun", "AI & Data": "tag-edu",
                        "Tools": "tag-loc",
                    }
                    _section(
                        f"{'⬡'} {cat}",
                        _tags_html(terms, cat_colors.get(cat, "tag-noun")),
                        accent=False,
                    )
        else:
            st.markdown("""
            <div style="text-align:center;padding:40px;color:#404060">
                <div style="font-size:32px">🔧</div>
                <div style="margin-top:8px">No tech stack keywords detected in this resume.</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Tab 3: Noun Chunks ────────────────────────────────────────────────────
    with tab3:
        if ents["noun_chunks"]:
            st.markdown(
                f'<p style="color:#6060a0;font-size:13px;margin-bottom:16px">'
                f'spaCy noun_chunks extracted <strong style="color:#a594ff">{len(ents["noun_chunks"])}</strong> '
                f'key phrases from this resume.</p>',
                unsafe_allow_html=True,
            )
            _section("🔗 Key Phrases (noun_chunks)",
                     _tags_html(ents["noun_chunks"], "tag-noun"))

            # Frequency bar chart for top noun chunks
            if len(ents["word_freq"]) > 5:
                st.markdown('<div class="section-label" style="margin-top:20px">Top Keywords by Frequency</div>', unsafe_allow_html=True)
                top_words = dict(list(ents["word_freq"].items())[:20])
                df = pd.DataFrame({"word": list(top_words.keys()), "count": list(top_words.values())})
                fig = px.bar(df, x="count", y="word", orientation="h",
                             color="count", color_continuous_scale=["#2a1f6e", "#7c6af7", "#2dd4bf"])
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    height=420, margin=dict(t=10, b=10, l=10, r=10),
                    xaxis=dict(showgrid=False, zeroline=False, color="#606080"),
                    yaxis=dict(showgrid=False, color="#9090a8", tickfont={"size": 11}),
                    coloraxis_showscale=False,
                    font={"family": "Space Grotesk"},
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Install spaCy (en_core_web_sm or larger) to enable noun_chunk extraction.")

    # ── Tab 4: ATS Score ──────────────────────────────────────────────────────
    with tab4:
        c1, c2 = st.columns([1, 1])
        with c1:
            _render_ats_gauge(ats["total"])
            grade = "Excellent" if ats["total"] >= 80 else "Good" if ats["total"] >= 65 else "Fair" if ats["total"] >= 45 else "Needs Work"
            st.markdown(
                f'<div style="text-align:center;font-size:14px;color:#6060a0;margin-top:-10px">Grade: '
                f'<strong style="color:#e8e8f0">{grade}</strong></div>',
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown('<div class="section-label" style="margin-bottom:16px">Score Breakdown</div>', unsafe_allow_html=True)
            for category, (pts, max_pts) in ats["breakdown"].items():
                pct = int((pts / max_pts) * 100) if max_pts else 0
                bar_color = "#4ade80" if pct >= 75 else "#fbbf24" if pct >= 40 else "#f97474"
                st.markdown(
                    f'<div style="margin-bottom:14px">'
                    f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#9090a8;margin-bottom:4px">'
                    f'<span>{category}</span><span style="color:#c0c0d8">{pts}/{max_pts}</span></div>'
                    f'<div style="background:#1a1a28;border-radius:4px;height:6px">'
                    f'<div style="background:{bar_color};width:{pct}%;height:6px;border-radius:4px;transition:width 0.4s"></div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

    # ── Tab 5: Raw Text ───────────────────────────────────────────────────────
    with tab5:
        st.markdown(
            f'<div style="background:#0d0d1a;border:1px solid rgba(255,255,255,0.06);border-radius:12px;'
            f'padding:20px;font-family:\'DM Mono\',monospace;font-size:12px;line-height:1.8;'
            f'color:#7070a0;white-space:pre-wrap;max-height:500px;overflow-y:auto">'
            f'{raw[:5000]}{"…[truncated]" if len(raw)>5000 else ""}</div>',
            unsafe_allow_html=True,
        )

    # ── Export ────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-label">Export Results</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)

    export_data = {
        "file": uploaded.name,
        "seniority": cached["seniority"],
        "estimated_years": cached["est_years"],
        "ats_score": ats["total"],
        **{k: v for k, v in ents.items() if k not in ("ner_entities", "word_freq", "spacy_available")},
    }
    with c1:
        st.download_button(
            "⬇️ Download JSON",
            data=json.dumps(export_data, indent=2),
            file_name=uploaded.name.replace(".pdf", "_ner.json"),
            mime="application/json",
            use_container_width=True,
        )
    with c2:
        # Flat CSV of all keywords
        rows = []
        for cat in ["skills", "job_titles", "companies", "tech_flat", "education", "locations", "noun_chunks"]:
            for item in ents.get(cat, []):
                rows.append({"category": cat, "keyword": item})
        df_export = pd.DataFrame(rows)
        st.download_button(
            "⬇️ Download CSV",
            data=df_export.to_csv(index=False),
            file_name=uploaded.name.replace(".pdf", "_keywords.csv"),
            mime="text/csv",
            use_container_width=True,
        )
    with c3:
        if st.button("🔄 Analyze Another", use_container_width=True):
            del st.session_state[cache_key]
            st.rerun()
