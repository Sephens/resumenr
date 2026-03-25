# 🧠 ResumeNER — Resume Intelligence Platform

A production-grade NLP resume analyzer built with **spaCy**, **Streamlit**, and **Plotly**.

## Features

- **spaCy NER** — Named Entity Recognition (ORG, PERSON, GPE, DATE)
- **noun_chunks** — Key phrase extraction
- **PhraseMatcher** — 150+ tech skills across 7 categories
- **ATS Score** — Resume readability scoring (0–100)
- **Batch Mode** — Compare multiple resumes side-by-side with radar charts
- **Analytics** — Aggregate trends across all analyzed resumes
- **Export** — JSON + CSV download of all extracted keywords

## Project Structure

```
resumenr/
├── app.py                  ← Streamlit entry point
├── requirements.txt
├── packages.txt
├── setup.sh                ← Downloads spaCy model
├── .streamlit/
│   └── config.toml         ← Dark theme + server config
├── pages/
│   ├── analyzer.py         ← Single resume analysis
│   ├── batch.py            ← Multi-resume comparison
│   └── analytics.py        ← Session-wide analytics
└── utils/
    └── nlp_engine.py       ← Core NLP pipeline
```

## Local Setup

```bash
# 1. Clone / download the project
cd resumenr

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download spaCy model (choose one)
python -m spacy download en_core_web_lg   # Best accuracy (~750MB)
python -m spacy download en_core_web_sm   # Lightweight (~12MB)

# 5. Run
streamlit run app.py
```

## Deploy to Streamlit Community Cloud (Free)

1. Push this folder to a **GitHub repo**
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **New app**
4. Select your repo, branch `main`, file `app.py`
5. Click **Deploy**

Streamlit Cloud will automatically run `setup.sh` to install the spaCy model.

## NLP Pipeline Details

```
PDF upload
  └─► pdfplumber → raw text
        └─► clean_text() → normalized text
              ├─► spaCy NER      → ORG, PERSON, GPE, DATE entities
              ├─► noun_chunks    → key phrases
              ├─► PhraseMatcher  → 150+ tech skills (exact match)
              ├─► regex          → emails, phones, LinkedIn, GitHub
              ├─► heuristics     → education lines, job titles
              └─► ATS scorer     → 0-100 readability score
```

## spaCy Models

| Model | Size | NER Quality | Recommended For |
|-------|------|-------------|-----------------|
| `en_core_web_sm` | 12 MB | Good | Streamlit Cloud (free tier) |
| `en_core_web_md` | 43 MB | Better | VPS / paid hosting |
| `en_core_web_lg` | 750 MB | Best | Local / GPU server |

The app auto-detects whichever model is installed and falls back to
regex-only mode if none is found.
