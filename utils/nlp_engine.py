"""
utils/nlp_engine.py
Core NLP extraction engine.
Uses spaCy NER + noun_chunks + custom PhraseMatcher for tech skills.
Auto-downloads en_core_web_sm on first run if no model is installed.
"""

import re
import sys
import subprocess
import unicodedata
from collections import Counter
from typing import Any

import pdfplumber


# ---------------------------------------------------------------------------
# spaCy bootstrap — auto-download model if not present
# ---------------------------------------------------------------------------

def _try_download(model: str) -> bool:
    """Download a spaCy model via pip. Returns True on success."""
    try:
        subprocess.check_call(
            [sys.executable, "-m", "spacy", "download", model, "--quiet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=300,
        )
        return True
    except Exception:
        return False


SPACY_AVAILABLE = False
_nlp = None
_model_name = None
PhraseMatcher = None

try:
    import spacy
    from spacy.matcher import PhraseMatcher as _PhraseMatcher
    PhraseMatcher = _PhraseMatcher

    _MODELS = ["en_core_web_lg", "en_core_web_md", "en_core_web_sm"]

    # Pass 1: load whatever is already installed
    for _m in _MODELS:
        try:
            _nlp = spacy.load(_m)
            _model_name = _m
            break
        except OSError:
            continue

    # Pass 2: nothing found — auto-download the small model
    if _nlp is None:
        if _try_download("en_core_web_sm"):
            try:
                _nlp = spacy.load("en_core_web_sm")
                _model_name = "en_core_web_sm"
            except OSError:
                pass

    SPACY_AVAILABLE = _nlp is not None

except ImportError:
    pass  # spaCy not installed at all — stay in regex-fallback mode

# ── Tech skills knowledge base ───────────────────────────────────────────────
TECH_SKILLS = {
    "Languages": [
        "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust",
        "Kotlin", "Swift", "PHP", "Ruby", "Scala", "R", "MATLAB", "Bash",
        "Shell", "Perl", "Lua", "Haskell", "Elixir", "Clojure", "Dart",
    ],
    "Frontend": [
        "React", "Vue", "Angular", "Next.js", "Nuxt.js", "Svelte", "Redux",
        "GraphQL", "HTML", "CSS", "Sass", "Tailwind CSS", "Bootstrap",
        "Webpack", "Vite", "jQuery", "Gatsby", "React Native", "Flutter",
    ],
    "Backend": [
        "Node.js", "Django", "Flask", "FastAPI", "Spring Boot", "Express",
        "Rails", "Laravel", "ASP.NET", "NestJS", "Gin", "Fiber", "Phoenix",
        "Tornado", "Celery", "gRPC", "REST API", "GraphQL API",
    ],
    "Databases": [
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "Cassandra",
        "DynamoDB", "Elasticsearch", "Neo4j", "InfluxDB", "Firebase",
        "Supabase", "PlanetScale", "CockroachDB", "Snowflake", "BigQuery",
    ],
    "Cloud & DevOps": [
        "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Ansible",
        "Jenkins", "GitHub Actions", "CircleCI", "GitLab CI", "Helm",
        "Prometheus", "Grafana", "Datadog", "New Relic", "Nginx", "Apache",
        "Cloudflare", "Vercel", "Netlify", "Heroku", "DigitalOcean",
    ],
    "AI & Data": [
        "TensorFlow", "PyTorch", "scikit-learn", "Keras", "Hugging Face",
        "OpenCV", "NLTK", "spaCy", "Pandas", "NumPy", "Matplotlib",
        "Seaborn", "Plotly", "Spark", "Hadoop", "Airflow", "dbt",
        "MLflow", "Weights & Biases", "LangChain", "OpenAI API",
    ],
    "Tools": [
        "Git", "GitHub", "GitLab", "Bitbucket", "Jira", "Confluence",
        "Slack", "Figma", "Postman", "VS Code", "IntelliJ", "Linux",
        "macOS", "Windows", "Jupyter", "Notion", "Asana", "Trello",
    ],
}

ALL_TECH_TERMS = [term for terms in TECH_SKILLS.values() for term in terms]

# Soft skills keywords
SOFT_SKILLS = [
    "leadership", "communication", "teamwork", "problem solving",
    "critical thinking", "time management", "adaptability", "creativity",
    "attention to detail", "collaboration", "mentoring", "project management",
    "agile", "scrum", "kanban", "cross-functional", "stakeholder management",
    "product management", "strategic planning", "data-driven",
]

# Degree keywords
DEGREE_KEYWORDS = [
    "bachelor", "master", "phd", "doctorate", "b.sc", "m.sc", "b.e", "m.e",
    "b.tech", "m.tech", "mba", "associate", "diploma", "certificate",
    "b.a", "m.a", "b.s", "m.s", "honours", "honors",
]


# ── PDF text extraction ──────────────────────────────────────────────────────
def extract_pdf_text(uploaded_file) -> tuple[str, int]:
    """Extract raw text and page count from a PDF using pdfplumber."""
    text_parts = []
    page_count = 0
    with pdfplumber.open(uploaded_file) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            txt = page.extract_text()
            if txt:
                text_parts.append(txt)
    return "\n".join(text_parts), page_count


# ── Text cleaning ────────────────────────────────────────────────────────────
def clean_text(text: str) -> str:
    """Normalize unicode, collapse whitespace, remove junk characters."""
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^\x00-\x7F]+", " ", text)   # drop non-ASCII
    text = re.sub(r"\s+", " ", text)               # collapse whitespace
    text = re.sub(r"[|•►▪▸◦‣⁃]", " ", text)      # bullet chars → space
    return text.strip()


# ── spaCy PhraseMatcher for tech terms ──────────────────────────────────────
def _build_tech_matcher(nlp):
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    patterns = [nlp.make_doc(t.lower()) for t in ALL_TECH_TERMS]
    matcher.add("TECH", patterns)
    return matcher


# ── Core extraction ──────────────────────────────────────────────────────────
def extract_entities(text: str) -> dict[str, Any]:
    """
    Full NLP pipeline:
      1. spaCy NER  → ORG, PERSON, GPE, DATE, MONEY, ...
      2. noun_chunks → key phrases
      3. PhraseMatcher → tech stack
      4. Regex patterns → emails, phone, LinkedIn, GitHub
      5. Heuristic classifiers → education, soft skills
    """
    result = {
        "skills": [],
        "job_titles": [],
        "companies": [],
        "technologies": {},    # {category: [terms]}
        "tech_flat": [],
        "education": [],
        "locations": [],
        "noun_chunks": [],
        "emails": [],
        "phones": [],
        "linkedin": [],
        "github": [],
        "ner_entities": [],    # raw NER hits for visualization
        "word_freq": {},
        "sentence_count": 0,
        "word_count": 0,
        "model_used": _model_name or "regex-fallback",
        "spacy_available": SPACY_AVAILABLE,
    }

    if not text.strip():
        return result

    cleaned = clean_text(text)

    # ── Word / sentence count (always) ──────────────────────────────────────
    words = re.findall(r"\b[a-zA-Z]{2,}\b", cleaned)
    result["word_count"] = len(words)

    # ── Regex extractions (always run, no spaCy needed) ─────────────────────
    result["emails"]   = list(set(re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)))
    result["phones"]   = list(set(re.findall(r"(\+?\d[\d\s\-().]{7,}\d)", text)))[:5]
    result["linkedin"] = list(set(re.findall(r"linkedin\.com/in/[\w\-]+", text, re.I)))
    result["github"]   = list(set(re.findall(r"github\.com/[\w\-]+", text, re.I)))

    # ── Regex tech detection (fallback if no spaCy) ─────────────────────────
    text_lower = cleaned.lower()
    tech_hits: dict[str, list[str]] = {}
    for category, terms in TECH_SKILLS.items():
        found = []
        for term in terms:
            pattern = r"\b" + re.escape(term.lower()) + r"\b"
            if re.search(pattern, text_lower):
                found.append(term)
        if found:
            tech_hits[category] = found

    result["technologies"] = tech_hits
    result["tech_flat"] = [t for terms in tech_hits.values() for t in terms]

    # ── Soft skills (regex) ──────────────────────────────────────────────────
    soft = []
    for skill in SOFT_SKILLS:
        if re.search(r"\b" + re.escape(skill) + r"\b", text_lower):
            soft.append(skill.title())
    result["skills"] = soft

    # ── Education heuristics (regex) ─────────────────────────────────────────
    edu_lines = []
    for line in cleaned.split("\n"):
        line_lower = line.lower()
        if any(kw in line_lower for kw in DEGREE_KEYWORDS):
            clean_line = line.strip()
            if 5 < len(clean_line) < 200:
                edu_lines.append(clean_line)
    result["education"] = list(dict.fromkeys(edu_lines))[:10]

    # ── Word frequency (for word cloud) ─────────────────────────────────────
    stopwords = {
        "the","a","an","and","or","but","in","on","at","to","for","of","with",
        "is","are","was","were","be","been","being","have","has","had","do",
        "does","did","will","would","could","should","may","might","shall",
        "i","you","he","she","it","we","they","me","him","her","us","them",
        "my","your","his","its","our","their","this","that","these","those",
        "which","who","whom","whose","when","where","why","how","not","no",
        "as","if","so","but","by","from","up","about","into","through","during",
    }
    freq = Counter(w.lower() for w in words if w.lower() not in stopwords and len(w) > 2)
    result["word_freq"] = dict(freq.most_common(50))

    # ── spaCy NER + noun_chunks (if model available) ─────────────────────────
    if SPACY_AVAILABLE and _nlp:
        _run_spacy_pipeline(cleaned, result)

    return result


def _run_spacy_pipeline(text: str, result: dict):
    """Run full spaCy pipeline and enrich result dict in place."""
    # spaCy has a 1M char default limit — chunk if needed
    max_chunk = 500_000
    chunks = [text[i:i+max_chunk] for i in range(0, len(text), max_chunk)]

    orgs, persons, gpes, dates = [], [], [], []
    noun_chunks_all = []
    ner_entities = []

    tech_matcher = _build_tech_matcher(_nlp)

    for chunk in chunks:
        doc = _nlp(chunk)

        # Sentence count
        result["sentence_count"] += sum(1 for _ in doc.sents)

        # ── NER entities ────────────────────────────────────────────────────
        for ent in doc.ents:
            label = ent.label_
            text_val = ent.text.strip()
            if not text_val or len(text_val) < 2:
                continue
            ner_entities.append({"text": text_val, "label": label, "start": ent.start_char, "end": ent.end_char})
            if label == "ORG":
                orgs.append(text_val)
            elif label == "PERSON":
                persons.append(text_val)
            elif label in ("GPE", "LOC"):
                gpes.append(text_val)
            elif label == "DATE":
                dates.append(text_val)

        # ── noun_chunks ──────────────────────────────────────────────────────
        for chunk in doc.noun_chunks:
            phrase = chunk.text.strip()
            # Keep meaningful phrases: 2–6 tokens, not pure stopwords
            if 1 < len(chunk) <= 6 and not all(t.is_stop or t.is_punct for t in chunk):
                noun_chunks_all.append(phrase)

        # ── PhraseMatcher for tech ───────────────────────────────────────────
        matches = tech_matcher(doc)
        for _, start, end in matches:
            matched_text = doc[start:end].text
            # Reconcile with known terms (case-correct)
            for term in ALL_TECH_TERMS:
                if term.lower() == matched_text.lower():
                    # Add to correct category
                    for cat, terms in TECH_SKILLS.items():
                        if term in terms:
                            if cat not in result["technologies"]:
                                result["technologies"][cat] = []
                            if term not in result["technologies"][cat]:
                                result["technologies"][cat].append(term)
                            if term not in result["tech_flat"]:
                                result["tech_flat"].append(term)
                            break

    # ── Deduplicate + clean ──────────────────────────────────────────────────
    result["companies"]    = _dedupe(orgs, max_len=60)[:20]
    result["locations"]    = _dedupe(gpes, max_len=50)[:15]
    result["ner_entities"] = ner_entities

    # noun_chunks: deduplicate + score by frequency
    chunk_counter = Counter(p.lower() for p in noun_chunks_all)
    seen = set()
    ranked = []
    for phrase, count in chunk_counter.most_common(40):
        canonical = phrase.title()
        if canonical not in seen and count >= 1:
            seen.add(canonical)
            ranked.append(canonical)
    result["noun_chunks"] = ranked

    # Job titles — heuristic: lines near action verbs or "at", short phrases
    result["job_titles"] = _extract_job_titles(result["noun_chunks"], result["ner_entities"])


def _dedupe(items: list[str], max_len: int = 80) -> list[str]:
    """Deduplicate while preserving order, filter by length."""
    seen = set()
    out = []
    for item in items:
        norm = item.strip()
        low = norm.lower()
        if low not in seen and 1 < len(norm) <= max_len:
            seen.add(low)
            out.append(norm)
    return out


# Common job title keywords for heuristic matching
_JOB_TITLE_KW = [
    "engineer", "developer", "architect", "manager", "analyst", "scientist",
    "designer", "director", "lead", "head", "officer", "vp", "president",
    "consultant", "specialist", "coordinator", "administrator", "intern",
    "associate", "senior", "junior", "principal", "staff", "founding",
    "product", "data", "software", "frontend", "backend", "fullstack",
    "devops", "cloud", "security", "ml", "ai", "research",
]

def _extract_job_titles(noun_chunks: list[str], entities: list[dict]) -> list[str]:
    """Heuristically extract job titles from noun chunks + NER."""
    candidates = set()
    for phrase in noun_chunks:
        pl = phrase.lower()
        if any(kw in pl for kw in _JOB_TITLE_KW) and len(phrase.split()) <= 6:
            candidates.add(phrase)
    # Also from NER WORK_OF_ART / TITLE labels if present
    for ent in entities:
        if ent["label"] in ("WORK_OF_ART", "TITLE"):
            candidates.add(ent["text"])
    return sorted(candidates)[:15]


# ── Seniority inference ──────────────────────────────────────────────────────
def infer_seniority(text: str, entities: dict) -> tuple[str, int]:
    """
    Returns (seniority_label, estimated_years).
    Parses year ranges from education/experience sections.
    """
    text_lower = text.lower()

    # Explicit title-based signals
    if any(kw in text_lower for kw in ["chief ", "cto", "ceo", "cfo", "vp of", "vice president"]):
        return "Executive", 15
    if any(kw in text_lower for kw in ["principal", "staff engineer", "distinguished"]):
        return "Principal / Staff", 10
    if any(kw in text_lower for kw in ["senior", "lead ", "lead engineer", "tech lead", "sr."]):
        return "Senior", 7
    if any(kw in text_lower for kw in ["junior", "entry", "graduate", "intern", "trainee"]):
        return "Junior / Entry", 1

    # Try to count years from date ranges (e.g. "2018 – 2023")
    year_matches = re.findall(r"\b(19|20)\d{2}\b", text)
    years_found = sorted(set(int(y) for y in year_matches))
    if len(years_found) >= 2:
        span = max(years_found) - min(years_found)
        if span >= 10:
            return "Senior", span
        elif span >= 5:
            return "Mid-level", span
        elif span >= 2:
            return "Junior / Mid", span
        else:
            return "Entry", span

    return "Mid-level", 3


# ── ATS score ────────────────────────────────────────────────────────────────
def compute_ats_score(result: dict, text: str) -> dict:
    """
    Compute a simple ATS-readability score based on:
    - Contact info present
    - Tech skills found
    - Education detected
    - Word count
    - No excessive special chars
    """
    score = 0
    breakdown = {}

    # Contact info (20 pts)
    contact_pts = 0
    if result["emails"]:      contact_pts += 10
    if result["phones"]:      contact_pts += 5
    if result["linkedin"]:    contact_pts += 5
    score += contact_pts
    breakdown["Contact Info"] = (contact_pts, 20)

    # Skills & tech (25 pts)
    tech_pts = min(25, len(result["tech_flat"]) * 2)
    score += tech_pts
    breakdown["Technical Skills"] = (tech_pts, 25)

    # Education (15 pts)
    edu_pts = min(15, len(result["education"]) * 7)
    score += edu_pts
    breakdown["Education"] = (edu_pts, 15)

    # Word count (20 pts) — sweet spot 400–900 words
    wc = result["word_count"]
    if 400 <= wc <= 900:        wc_pts = 20
    elif 300 <= wc <= 1200:     wc_pts = 14
    elif 200 <= wc:             wc_pts = 8
    else:                       wc_pts = 3
    score += wc_pts
    breakdown["Length & Density"] = (wc_pts, 20)

    # Companies / experience (10 pts)
    exp_pts = min(10, len(result["companies"]) * 3)
    score += exp_pts
    breakdown["Work Experience"] = (exp_pts, 10)

    # Soft skills (10 pts)
    soft_pts = min(10, len(result["skills"]) * 2)
    score += soft_pts
    breakdown["Soft Skills"] = (soft_pts, 10)

    return {"total": min(score, 100), "breakdown": breakdown}
