"""
pages/batch.py
──────────────
Batch upload and compare multiple resumes side-by-side.
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
)


def _process_file(f) -> dict:
    raw, pages = extract_pdf_text(f)
    ents = extract_entities(raw)
    seniority, est_years = infer_seniority(raw, ents)
    ats = compute_ats_score(ents, raw)
    return {
        "name": f.name,
        "pages": pages,
        "entities": ents,
        "seniority": seniority,
        "est_years": est_years,
        "ats": ats,
        "raw": raw,
    }


def render():
    st.markdown("""
    <h2 style="font-size:32px;font-weight:700;letter-spacing:-0.5px;color:#e8e8f0;margin-bottom:4px">
        Batch Analyzer
    </h2>
    <p style="color:#6060a0;font-size:15px;margin-bottom:28px">
        Upload multiple résumés and get a comparative breakdown side-by-side.
    </p>
    """, unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "Upload multiple PDF resumes",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if not uploaded_files:
        st.markdown("""
        <div style="text-align:center;padding:40px 0;color:#404060">
            <div style="font-size:48px;margin-bottom:12px">📦</div>
            <div style="font-size:15px">Upload 2–10 PDF resumes to compare them</div>
            <div style="font-size:12px;margin-top:6px;color:#303050">Great for screening candidates side-by-side</div>
        </div>
        """, unsafe_allow_html=True)
        return

    if len(uploaded_files) > 10:
        st.warning("Please upload at most 10 resumes at once.")
        uploaded_files = uploaded_files[:10]

    # ── Process all files ────────────────────────────────────────────────────
    cache_key = "batch_" + "_".join(f"{f.name}_{f.size}" for f in uploaded_files)
    if cache_key not in st.session_state:
        results = []
        prog = st.progress(0, text="Processing resumes…")
        for i, f in enumerate(uploaded_files):
            prog.progress(int((i / len(uploaded_files)) * 100), text=f"Processing {f.name}…")
            results.append(_process_file(f))
        prog.progress(100, text="Done!")
        prog.empty()
        st.session_state[cache_key] = results
        st.success(f"✅ Processed {len(results)} resume(s)")

    results = st.session_state[cache_key]

    # ── Summary table ─────────────────────────────────────────────────────────
    st.markdown("### 📊 Comparison Table")
    table_data = []
    for r in results:
        e = r["entities"]
        table_data.append({
            "Resume": r["name"],
            "ATS Score": r["ats"]["total"],
            "Seniority": r["seniority"],
            "~Years": r["est_years"],
            "Tech Skills": len(e["tech_flat"]),
            "Soft Skills": len(e["skills"]),
            "Companies": len(e["companies"]),
            "Education": len(e["education"]),
            "Words": e["word_count"],
            "Pages": r["pages"],
        })
    df = pd.DataFrame(table_data)

    # Highlight ATS score column
    def color_ats(val):
        if val >= 75: return "color: #4ade80; font-weight: 600"
        elif val >= 50: return "color: #fbbf24; font-weight: 600"
        return "color: #f97474; font-weight: 600"

    styled = df.style.applymap(color_ats, subset=["ATS Score"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── ATS comparison bar chart ──────────────────────────────────────────────
    st.markdown("### 🏆 ATS Score Comparison")
    names  = [r["name"].replace(".pdf", "") for r in results]
    scores = [r["ats"]["total"] for r in results]
    colors = ["#4ade80" if s >= 75 else "#fbbf24" if s >= 50 else "#f97474" for s in scores]

    fig = go.Figure(go.Bar(
        x=names, y=scores,
        marker_color=colors,
        text=scores, textposition="outside",
        textfont={"color": "#c0c0d8"},
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=320, margin=dict(t=20, b=20, l=10, r=10),
        xaxis=dict(showgrid=False, color="#9090a8", tickfont={"size": 12}),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)", range=[0, 110], color="#606080"),
        font={"family": "Space Grotesk"},
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Tech skills overlap radar ─────────────────────────────────────────────
    if len(results) >= 2:
        st.markdown("### 🕸️ Tech Category Coverage")
        all_cats = ["Languages", "Frontend", "Backend", "Databases", "Cloud & DevOps", "AI & Data", "Tools"]
        fig2 = go.Figure()
        palette = ["#7c6af7", "#2dd4bf", "#fbbf24", "#f472b6", "#4ade80", "#22d3ee", "#fb923c", "#a594ff", "#f97474"]
        for i, r in enumerate(results):
            tech = r["entities"]["technologies"]
            vals = [len(tech.get(c, [])) for c in all_cats]
            vals.append(vals[0])  # close the polygon
            fig2.add_trace(go.Scatterpolar(
                r=vals,
                theta=all_cats + [all_cats[0]],
                fill="toself",
                name=r["name"].replace(".pdf", ""),
                line_color=palette[i % len(palette)],
                fillcolor=palette[i % len(palette)].replace("#", "rgba(") + ",0.08)",
                opacity=0.9,
            ))
        fig2.update_layout(
            polar=dict(
                bgcolor="rgba(0,0,0,0)",
                radialaxis=dict(visible=True, range=[0, 10], color="#404060", gridcolor="rgba(255,255,255,0.06)"),
                angularaxis=dict(color="#7070a0", gridcolor="rgba(255,255,255,0.06)"),
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=400,
            margin=dict(t=20, b=20),
            legend=dict(font={"color": "#9090a8", "size": 12}, bgcolor="rgba(0,0,0,0)"),
            font={"family": "Space Grotesk"},
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Tech skill overlap (shared skills) ───────────────────────────────────
    if len(results) >= 2:
        st.markdown("### 🔁 Shared Tech Skills")
        all_skill_sets = [set(r["entities"]["tech_flat"]) for r in results]
        shared = set.intersection(*all_skill_sets)
        if shared:
            tags = "".join(f'<span class="tag tag-tech">{s}</span>' for s in sorted(shared))
            st.markdown(
                f'<div style="background:#13131e;border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:18px">'
                f'<div class="section-label">Skills present in ALL resumes</div>'
                f'<div class="tag-wrap">{tags}</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="color:#404060;font-size:13px;padding:12px">No tech skills found in common across all resumes.</div>',
                unsafe_allow_html=True,
            )

    # ── Per-resume detail cards ───────────────────────────────────────────────
    st.markdown("### 📋 Individual Summaries")
    for r in results:
        with st.expander(f"📄 {r['name']} — ATS: {r['ats']['total']}/100 | {r['seniority']}"):
            e = r["entities"]
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**💻 Top Technologies**")
                if e["tech_flat"]:
                    tags = "".join(f'<span class="tag tag-tech">{t}</span>' for t in e["tech_flat"][:10])
                    st.markdown(f'<div class="tag-wrap">{tags}</div>', unsafe_allow_html=True)
                else:
                    st.caption("None detected")
                st.markdown("**🏢 Companies**")
                if e["companies"]:
                    tags = "".join(f'<span class="tag tag-company">{c}</span>' for c in e["companies"][:8])
                    st.markdown(f'<div class="tag-wrap">{tags}</div>', unsafe_allow_html=True)
                else:
                    st.caption("None detected")
            with c2:
                st.markdown("**🎓 Education**")
                if e["education"]:
                    for edu in e["education"][:3]:
                        st.markdown(f'<span class="tag tag-edu">{edu[:80]}</span>', unsafe_allow_html=True)
                else:
                    st.caption("None detected")
                st.markdown("**⚡ Soft Skills**")
                if e["skills"]:
                    tags = "".join(f'<span class="tag tag-skill">{s}</span>' for s in e["skills"][:8])
                    st.markdown(f'<div class="tag-wrap">{tags}</div>', unsafe_allow_html=True)

    # ── Export all ────────────────────────────────────────────────────────────
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        all_rows = []
        for r in results:
            e = r["entities"]
            for cat in ["tech_flat", "skills", "companies", "education"]:
                for item in e.get(cat, []):
                    all_rows.append({"resume": r["name"], "category": cat, "keyword": item})
        df_export = pd.DataFrame(all_rows)
        st.download_button(
            "⬇️ Export All Keywords (CSV)",
            data=df_export.to_csv(index=False),
            file_name="batch_keywords.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with c2:
        if st.button("🔄 Clear & Upload New", use_container_width=True):
            del st.session_state[cache_key]
            st.rerun()
