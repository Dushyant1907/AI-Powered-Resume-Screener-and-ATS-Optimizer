from __future__ import annotations

import io
import re
from collections import Counter

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

app = Flask(__name__)
MAX_RESUME_BYTES = 8 * 1024 * 1024
MAX_RESUMES = 10
app.config["MAX_CONTENT_LENGTH"] = MAX_RESUME_BYTES * MAX_RESUMES + 1024 * 1024

STOP_WORDS = set("""a an the and or but if then than so because as at by for from in into of on onto to up with without is are was were be been being do does did have has had can could should would will may might must i you we they he she it this that these those your our their its job role work experience skills skill knowledge ability abilities responsibilities requirements required preferred candidate candidates strong excellent good plus using use used including across within about""".split())
SKILL_ALIASES = {
    "javascript": ["js", "javascript"], "typescript": ["typescript", "ts"],
    "python": ["python"], "java": ["java"], "sql": ["sql", "mysql", "postgresql", "postgres"],
    "react": ["react", "react.js", "reactjs"], "node.js": ["node.js", "nodejs", "node"],
    "machine learning": ["machine learning", "ml"], "data analysis": ["data analysis", "data analytics"],
    "communication": ["communication", "communicate"], "leadership": ["leadership", "lead"],
    "aws": ["aws", "amazon web services"], "docker": ["docker"], "git": ["git", "github"],
    "html": ["html"], "css": ["css"], "excel": ["excel", "spreadsheet"],
    "project management": ["project management", "project manager"],
}


def extract_text(upload) -> str:
    name = (upload.filename or "").lower()
    if not name.endswith((".txt", ".pdf", ".docx")):
        raise ValueError("Please upload a PDF, DOCX, or TXT resume.")
    data = upload.read(MAX_RESUME_BYTES + 1)
    if len(data) > MAX_RESUME_BYTES:
        raise ValueError("Each resume must be 8 MB or smaller.")
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="replace")
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("PDF support is not installed yet. Run: pip install -r requirements.txt") from exc
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if name.endswith(".docx"):
        try:
            from docx import Document
        except ImportError as exc:
            raise ValueError("DOCX support is not installed yet. Run: pip install -r requirements.txt") from exc
        document = Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs)
    raise ValueError("Please upload a PDF, DOCX, or TXT resume.")


def tokens(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-zA-Z][a-zA-Z+#.\-]{1,}", text.lower())
            if word not in STOP_WORDS and not word.isdigit()]


def prepare_job(job: str) -> dict:
    job_terms = Counter(tokens(job))
    important_terms = [word for word, _ in job_terms.most_common(30) if len(word) > 2]
    job_lower = job.lower()
    skills = [
        {"name": skill.title(), "aliases": aliases}
        for skill, aliases in SKILL_ALIASES.items()
        if any(alias in job_lower for alias in aliases)
    ]
    return {"important_terms": important_terms, "skills": skills}


def analyze_with_profile(resume: str, profile: dict) -> dict:
    resume_terms = set(tokens(resume))
    important_terms = profile["important_terms"]
    matched = [word for word in important_terms if word in resume_terms]
    keywords = [{"term": word, "matched": word in resume_terms} for word in important_terms[:18]]
    term_score = round(100 * len(matched) / max(len(important_terms), 1))

    resume_lower = resume.lower()
    skill_results = [
        {
            "name": skill["name"],
            "matched": any(alias in resume_lower for alias in skill["aliases"]),
        }
        for skill in profile["skills"]
    ]
    skill_score = round(100 * sum(x["matched"] for x in skill_results) / max(len(skill_results), 1))
    score = round(term_score * .55 + skill_score * .45) if skill_results else term_score

    sections = {
        "Contact information": bool(re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", resume)),
        "Work experience": bool(re.search(r"experience|employment|internship|work history", resume_lower)),
        "Education": bool(re.search(r"education|university|college|bachelor|master|degree", resume_lower)),
        "Skills": bool(re.search(r"skills|technologies|technical", resume_lower)),
        "Achievements or projects": bool(re.search(r"projects|achievement|成果", resume_lower)),
    }
    suggestions = []
    missing_skills = [x["name"] for x in skill_results if not x["matched"]]
    if missing_skills:
        suggestions.append("If you have relevant experience, add these job-related skills with specific examples: " + ", ".join(missing_skills[:6]) + ".")
    missing_sections = [name for name, present in sections.items() if not present]
    if missing_sections:
        suggestions.append("Consider adding or clearly labeling: " + ", ".join(missing_sections) + ".")
    if len(resume.split()) < 100:
        suggestions.append("The extracted resume is quite short. Add concrete responsibilities, results, and project details where relevant.")
    if not suggestions:
        suggestions.append("Use concise bullet points and quantify results where possible. Keep the final resume accurate and easy to scan.")
    return {"score": score, "matched_count": len(matched), "keyword_count": len(important_terms),
            "skills": skill_results, "keywords": keywords, "sections": sections,
            "suggestions": suggestions, "word_count": len(resume.split())}


def analyze(resume: str, job: str) -> dict:
    return analyze_with_profile(resume, prepare_job(job))


@app.get("/")
def index():
    return render_template("index.html")


@app.errorhandler(RequestEntityTooLarge)
def handle_upload_too_large(error):
    return jsonify(
        error="The total upload is too large. Limit each resume to 8 MB and upload no more than 10."
    ), error.code


@app.post("/api/analyze")
def api_analyze():
    batch_request = "resumes" in request.files
    uploads = request.files.getlist("resumes" if batch_request else "resume")
    uploads = [upload for upload in uploads if upload.filename]
    job = request.form.get("job_description", "").strip()
    if not uploads:
        return jsonify(error="Choose a resume file to analyze."), 400
    if not job:
        return jsonify(error="Paste a job description to compare against."), 400
    if len(uploads) > MAX_RESUMES:
        return jsonify(error=f"Upload no more than {MAX_RESUMES} resumes at a time."), 400

    profile = prepare_job(job)
    if not batch_request and len(uploads) == 1:
        try:
            resume = extract_text(uploads[0])
            if not resume.strip():
                return jsonify(error="No readable text was found. Try a text-based PDF or DOCX file."), 400
            return jsonify(analyze_with_profile(resume, profile))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except Exception:
            return jsonify(error="The resume could not be read. Check the file and try again."), 400

    candidates = []
    failures = []
    for upload in uploads:
        try:
            resume = extract_text(upload)
            if not resume.strip():
                raise ValueError("No readable text was found.")
            candidates.append({
                "filename": upload.filename,
                **analyze_with_profile(resume, profile),
            })
        except ValueError as exc:
            failures.append({"filename": upload.filename, "error": str(exc)})
        except Exception:
            failures.append({
                "filename": upload.filename,
                "error": "The resume could not be read. Check the file and try again.",
            })

    if not candidates:
        failure_summary = "; ".join(
            f"{failure['filename']}: {failure['error']}" for failure in failures
        )
        return jsonify(
            error=f"None of the uploaded resumes could be analyzed. {failure_summary}",
            failures=failures,
        ), 400

    candidates.sort(
        key=lambda candidate: (
            candidate["score"],
            sum(skill["matched"] for skill in candidate["skills"]),
            candidate["matched_count"],
        ),
        reverse=True,
    )
    for rank, candidate in enumerate(candidates, start=1):
        candidate["rank"] = rank
    return jsonify(candidates=candidates, failures=failures)


if __name__ == "__main__":
    app.run(debug=True)
    