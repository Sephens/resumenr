"""
pages/analytics.py
───────────────────
Aggregate analytics across all analyzed resumes in the session.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter

from utils.nlp_engine import TECH_SKILLS


def render():
    st.markdown("""
    <h2 style="font-size:32px;font-weight:700;letter-spacing:-0.5px;color:#e8e8f0;margin-bottom:4px">
        Analytics
    </h2>
    <p style="color:#6060a0;font-size:15px;margin-bottom:28px">
        Aggregate insights across all resumes analyzed this session.
    </p>
    """, unsafe_allow_html=True)

    # Gather all results from session state
    all_results = []
    for key, val in st.session_state.items():
        if isinstance(val, dict) and "entities" in val and "ats" in val:
            all_results.append(val)
        elif isinstance(val, list) and all(isinstance(r, dict) and "entities" in r for r in val):
            all_results.extend(val)

    if not all_results:
        st.markdown("""
        <div style="text-align:center;padding:60px 0;color:#404060">
            <div style="font-size:48px;margin-bottom:12px">📈</div>
            <div style="font-size:15px">No resumes analyzed yet.</div>
            <div style="font-size:12px;margin-top:6px;color:#303050">
                Go to the Analyzer or Batch Mode tab and upload some resumes first.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Aggregate data ────────────────────────────────────────────────────────
    all_tech      = Counter()
    all_skills    = Counter()
    all_companies = Counter()
    all_edu       = Counter()
    ats_scores    = []
    seniority_counts = Counter()
    cat_coverage  = {cat: 0 for cat in TECH_SKILLS}

    for r in all_results:
        e = r["entities"]
        all_tech.update(e.get("tech_flat", []))
        all_skills.update(e.get("skills", []))
        all_companies.update(e.get("companies", []))
        all_edu.update(e.get("education", []))
        ats_scores.append(r["ats"]["total"])
        seniority_counts[r.get("seniority", "Unknown")] += 1
        for cat in TECH_SKILLS:
            if e.get("technologies", {}).get(cat):
                cat_coverage[cat] += 1

    total = len(all_results)

    # ── Top metrics ───────────────────────────────────────────────────────────
    avg_ats = round(sum(ats_scores) / len(ats_scores)) if ats_scores else 0
    c1, c2, c3, c4 = st.columns(4)
    for col, num, label, color in [
        (c1, total, "Resumes Analyzed", "#7c6af7"),
        (c2, avg_ats, "Avg ATS Score", "#4ade80" if avg_ats>=70 else "#fbbf24"),
        (c3, len(all_tech), "Unique Tech Skills", "#2dd4bf"),
        (c4, len(all_skills), "Unique Soft Skills", "#f472b6"),
    ]:
        with col:
            st.markdown(
                f'<div class="metric-card"><div class="metric-num" style="color:{color}">{num}</div>'
                f'<div class="metric-label">{label}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts row 1 ──────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### 🔧 Top 15 Technologies")
        top_tech = dict(all_tech.most_common(15))
        if top_tech:
            df = pd.DataFrame({"skill": list(top_tech.keys()), "count": list(top_tech.values())})
            fig = px.bar(df, x="count", y="skill", orientation="h",
                         color="count", color_continuous_scale=["#1a1040", "#7c6af7", "#a594ff"])
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                height=400, margin=dict(t=10, b=10, l=10, r=10),
                xaxis=dict(showgrid=False, zeroline=False, color="#606080"),
                yaxis=dict(showgrid=False, color="#9090a8", tickfont={"size": 11}),
                coloraxis_showscale=False,
                font={"family": "Space Grotesk"},
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("No data yet")

    with c2:
        st.markdown("#### 🧩 Seniority Distribution")
        if seniority_counts:
            labels = list(seniority_counts.keys())
            values = list(seniority_counts.values())
            colors = ["#7c6af7", "#2dd4bf", "#fbbf24", "#f472b6", "#4ade80", "#fb923c", "#94a3b8"]
            fig2 = go.Figure(go.Pie(
                labels=labels, values=values,
                marker=dict(colors=colors[:len(labels)], line=dict(color="#0a0a12", width=2)),
                textfont=dict(size=13, family="Space Grotesk"),
                hole=0.55,
            ))
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                height=400, margin=dict(t=10, b=10, l=10, r=10),
                legend=dict(font={"color": "#9090a8", "size": 12}, bgcolor="rgba(0,0,0,0)"),
                font={"family": "Space Grotesk"},
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.caption("No data yet")

    # ── Charts row 2 ──────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### ⚡ Top Soft Skills")
        top_soft = dict(all_skills.most_common(12))
        if top_soft:
            df2 = pd.DataFrame({"skill": list(top_soft.keys()), "count": list(top_soft.values())})
            fig3 = px.bar(df2, x="skill", y="count",
                          color="count", color_continuous_scale=["#0d1a2e", "#2dd4bf", "#4ade80"])
            fig3.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                height=320, margin=dict(t=10, b=10, l=10, r=10),
                xaxis=dict(showgrid=False, color="#9090a8", tickangle=-30, tickfont={"size": 10}),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)", color="#606080"),
                coloraxis_showscale=False,
                font={"family": "Space Grotesk"},
            )
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.caption("No data yet")

    with c2:
        st.markdown("#### 🏢 Top Companies Mentioned")
        top_cos = dict(all_companies.most_common(10))
        if top_cos:
            df3 = pd.DataFrame({"company": list(top_cos.keys()), "count": list(top_cos.values())})
            fig4 = px.bar(df3, x="count", y="company", orientation="h",
                          color="count", color_continuous_scale=["#2a1000", "#fbbf24", "#fb923c"])
            fig4.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                height=320, margin=dict(t=10, b=10, l=10, r=10),
                xaxis=dict(showgrid=False, zeroline=False, color="#606080"),
                yaxis=dict(showgrid=False, color="#9090a8", tickfont={"size": 11}),
                coloraxis_showscale=False,
                font={"family": "Space Grotesk"},
            )
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.caption("No data yet")

    # ── ATS distribution histogram ────────────────────────────────────────────
    if len(ats_scores) >= 2:
        st.markdown("#### 📊 ATS Score Distribution")
        fig5 = px.histogram(
            x=ats_scores, nbins=10,
            color_discrete_sequence=["#7c6af7"],
            labels={"x": "ATS Score", "y": "Count"},
        )
        fig5.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=260, margin=dict(t=10, b=10, l=10, r=10),
            xaxis=dict(showgrid=False, color="#9090a8", range=[0, 100]),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)", color="#606080"),
            bargap=0.1, font={"family": "Space Grotesk"},
        )
        st.plotly_chart(fig5, use_container_width=True)

    # ── Tech category coverage heatmap ────────────────────────────────────────
    if total >= 2:
        st.markdown("#### 🗂️ Tech Category Coverage (% of resumes)")
        cat_pct = {cat: round((count / total) * 100) for cat, count in cat_coverage.items() if count > 0}
        if cat_pct:
            df4 = pd.DataFrame({"Category": list(cat_pct.keys()), "Coverage %": list(cat_pct.values())})
            df4 = df4.sort_values("Coverage %", ascending=False)
            fig6 = px.bar(df4, x="Coverage %", y="Category", orientation="h",
                          color="Coverage %", color_continuous_scale=["#0d1a2e", "#2dd4bf"])
            fig6.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                height=300, margin=dict(t=10, b=10, l=10, r=40),
                xaxis=dict(showgrid=False, range=[0, 105], color="#606080"),
                yaxis=dict(showgrid=False, color="#9090a8", tickfont={"size": 12}),
                coloraxis_showscale=False,
                font={"family": "Space Grotesk"},
            )
            st.plotly_chart(fig6, use_container_width=True)

    # ── Clear session ─────────────────────────────────────────────────────────
    st.markdown("---")
    if st.button("🗑️ Clear All Session Data"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
