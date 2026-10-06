# ResumeLens — AI-Powered Resume Screener and ATS Optimizer

A small MCA Semester III project prototype. It compares a resume with a job description, estimates keyword and skill alignment, checks for common resume sections, and gives practical ATS readability suggestions. The app is a decision-support demo; it does not make hiring decisions.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

On macOS or Linux, you can also start it without activating the environment:

```bash
.venv/bin/python app.py
```

Open http://127.0.0.1:5000. Upload up to 10 text-based PDF, DOCX, or TXT resumes (maximum 8 MB each), paste a job description, and select **Shortlist resumes**. The app ranks readable resumes by the existing role-alignment score and shows a detailed review for the top match; select another ranked resume to review it. Unreadable or unsupported files are reported and skipped when other resumes can be analyzed. Scanned PDFs need OCR and are not supported by this prototype.

## How the score works

The prototype extracts job terms and known skills once per job description, then reuses that profile while comparing every resume. When known skills are found in the job description, the score combines 55% job-term overlap and 45% skill overlap. Otherwise it uses job-term overlap. Results are sorted by score, matched skill count, and matched keyword count. This transparent baseline is not a trained hiring model, and scores can miss context, synonyms, and equivalent experience.

## Project structure

- `app.py` — Flask routes, document text extraction, and analysis logic
- `templates/index.html` — responsive interface
- `static/style.css` and `static/shortlist.css` — visual styling
- `static/app.js` — upload interaction and results rendering
