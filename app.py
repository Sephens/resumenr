import streamlit as st

st.set_page_config(
    page_title="ResumeNER — Resume Intelligence Platform",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=DM+Mono&display=swap');

html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0f0f17;
    border-right: 1px solid rgba(255,255,255,0.06);
}
[data-testid="stSidebar"] * { color: #c0c0d8 !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.08); }

/* Main bg */
.stApp { background: #0a0a12; }
.main .block-container { padding-top: 2rem; padding-bottom: 4rem; }

/* Cards */
.ner-card {
    background: #13131e;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px;
    padding: 22px 24px;
    margin-bottom: 16px;
}
.ner-card-accent { border-top: 3px solid #7c6af7; }
.metric-card {
    background: #13131e;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 18px 20px;
    text-align: center;
}
.metric-num {
    font-size: 42px;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 4px;
}
.metric-label {
    font-size: 12px;
    color: #6060a0;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Tags */
.tag-wrap { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.tag {
    display: inline-block;
    padding: 5px 13px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    font-family: 'Space Grotesk', sans-serif;
}
.tag-skill   { background: rgba(124,106,247,0.15); color: #a594ff; border: 1px solid rgba(124,106,247,0.25); }
.tag-title   { background: rgba(45,212,191,0.12);  color: #2dd4bf; border: 1px solid rgba(45,212,191,0.22); }
.tag-company { background: rgba(251,191,36,0.12);  color: #fbbf24; border: 1px solid rgba(251,191,36,0.22); }
.tag-tech    { background: rgba(74,222,128,0.12);  color: #4ade80; border: 1px solid rgba(74,222,128,0.22); }
.tag-edu     { background: rgba(244,114,182,0.12); color: #f472b6; border: 1px solid rgba(244,114,182,0.22); }
.tag-noun    { background: rgba(34,211,238,0.10);  color: #22d3ee; border: 1px solid rgba(34,211,238,0.18); }
.tag-loc     { background: rgba(251,146,60,0.12);  color: #fb923c; border: 1px solid rgba(251,146,60,0.22); }

/* Section headers */
.section-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: #5050a0;
    margin-bottom: 12px;
}

/* Highlighted text entity spans */
.ent-ORG    { background: rgba(251,191,36,0.18); border-radius: 4px; padding: 1px 6px; color: #fbbf24; }
.ent-PERSON { background: rgba(244,114,182,0.15); border-radius: 4px; padding: 1px 6px; color: #f472b6; }
.ent-GPE    { background: rgba(251,146,60,0.15); border-radius: 4px; padding: 1px 6px; color: #fb923c; }
.ent-DATE   { background: rgba(45,212,191,0.12); border-radius: 4px; padding: 1px 6px; color: #2dd4bf; }
.ent-SKILL  { background: rgba(124,106,247,0.15); border-radius: 4px; padding: 1px 6px; color: #a594ff; }
.ent-default{ background: rgba(148,163,184,0.12); border-radius: 4px; padding: 1px 6px; color: #94a3b8; }

/* Upload area */
[data-testid="stFileUploader"] {
    border: 1.5px dashed rgba(124,106,247,0.4) !important;
    border-radius: 16px !important;
    background: rgba(124,106,247,0.04) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: transparent;
    border-bottom: 1px solid rgba(255,255,255,0.07);
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border-radius: 8px 8px 0 0;
    color: #6060a0;
    font-size: 13px;
    font-weight: 500;
    padding: 8px 18px;
}
.stTabs [aria-selected="true"] {
    background: rgba(124,106,247,0.1) !important;
    color: #a594ff !important;
    border-bottom: 2px solid #7c6af7 !important;
}

/* Progress */
.stProgress > div > div > div { background: linear-gradient(90deg, #7c6af7, #2dd4bf) !important; }

/* Buttons */
.stButton > button {
    background: #7c6af7;
    color: #fff;
    border: none;
    border-radius: 10px;
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    font-size: 14px;
    padding: 10px 24px;
    transition: all 0.2s;
}
.stButton > button:hover { background: #a594ff; transform: translateY(-1px); }

/* Expander */
.streamlit-expanderHeader {
    background: #13131e;
    border-radius: 10px;
    color: #c0c0d8;
    font-weight: 500;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0a0a12; }
::-webkit-scrollbar-thumb { background: #2a2a4a; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 ResumeNER")
    st.markdown("*Resume Intelligence Platform*")
    st.markdown("---")
    st.markdown("""
    **Navigation**
    - 🏠 [Analyzer](#) — Upload & analyze
    - 📊 [Batch Mode](#) — Multiple resumes  
    - 📈 [Analytics](#) — Trends & insights
    """)
    st.markdown("---")
    st.markdown("""
    **NLP Pipeline**
    
    `spaCy` `en_core_web_lg`  
    `NER` → entities  
    `noun_chunks` → phrases  
    `matcher` → tech skills  
    `pdfplumber` → PDF text  
    """)
    st.markdown("---")
    st.markdown("""
    <div style='font-size:11px;color:#404060'>
    Built with spaCy · Streamlit · Python 3.12
    </div>
    """, unsafe_allow_html=True)

# ── Import pages ────────────────────────────────────────────────────────────
from pages import analyzer, batch, analytics

# ── Router ──────────────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "analyzer"

col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    if st.button("🔍 Analyzer", use_container_width=True):
        st.session_state.page = "analyzer"
with col2:
    if st.button("📦 Batch Mode", use_container_width=True):
        st.session_state.page = "batch"
with col3:
    if st.button("📈 Analytics", use_container_width=True):
        st.session_state.page = "analytics"

st.markdown("---")

# Route to selected page
if st.session_state.page == "analyzer":
    analyzer.render()
elif st.session_state.page == "batch":
    batch.render()
elif st.session_state.page == "analytics":
    analytics.render()
