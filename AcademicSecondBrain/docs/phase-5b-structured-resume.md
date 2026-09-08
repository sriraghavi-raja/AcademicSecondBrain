# Phase 5b: Structured Resume Inputs and Template

## What Changed

- `student_profile` stores factual identity and education fields through `PUT/GET /api/profile/{student_id}`.
- `projects` stores manual and GitHub project records with grounded descriptions.
- GitHub sync now upserts project title, language stack, and repository description alongside language evidence.
- Certifications are extracted into `achievements` and their explicitly mentioned skills become certification evidence.
- Skills are grouped through the additive `skill_categories.json` lookup.
- Project bullets are the only LLM-generated resume content. Empty descriptions produce no bullets, and invented numeric claims are rejected.
- The DOCX is assembled once using profile, education, categorized skills, projects, certifications, and achievements.

## Live Test Order

Start the backend:

```powershell
uv run uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

1. Create the factual profile with `PUT /api/career/profile/demo-student`:

```json
{
  "full_name": "Sri Raghavi N",
  "email": "sriraghavi2811@gmail.com",
  "phone": "7305968818",
  "location": "Coimbatore, Tamil Nadu",
  "college_name": "Sri Krishna College of Engineering and Technology",
  "degree": "B.Tech",
  "branch": "Artificial Intelligence and Data Science",
  "college_start": "September 2023",
  "college_end": "May 2027",
  "cgpa": "9.02",
  "school_name": "The TVS School",
  "school_detail": "Higher Secondary (12th Standard)",
  "school_dates": "June 2022 - April 2023",
  "school_score": "95.83%"
}
```

2. Add a manually described project with `POST /api/career/projects/demo-student`:

```json
{
  "title": "RAG Academic Assistant",
  "tech_stack": "Python, FastAPI, Flutter, RAG",
  "description_text": "Built a cross-platform AI document assistant using Python, FastAPI, Flutter, ChromaDB, and BM25 hybrid search. Added local RAG retrieval and citation-grounded responses."
}
```

3. Confirm profile with `GET /api/career/profile/demo-student`.
4. Confirm the skill graph contains at least one taxonomy skill with manual or GitHub evidence. Quiz-only topics will not appear in the resume skills section.
5. Call `POST /api/career/resume`:

```json
{
  "student_id": "demo-student",
  "target_role": "Python Developer"
}
```

The response downloads a DOCX. Check that the document has one name header, one education section, categorized skills, one project section, and no duplicate project bullets.

6. Upload a real PDF/DOCX certificate through `POST /api/career/certifications/demo-student`. The certificate parser writes an achievement and returns unmatched skill terms without failing the whole upload.

## Automated Validation

```powershell
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q main.py src tests
```

The project bullet tests verify that unsupported numbers are rejected and empty source descriptions never reach the LLM. Existing Phase 1-5 tests remain part of the same suite.