# Phase 5: Resume and Gap Analysis

## Boundary Decision

Only `skill_type: "taxonomy"` entries with at least one non-quiz evidence source (`manual` or `github`) are resume-grade. Quiz-only entries remain available to weak-topic tracking and gap context but are excluded from resume claims unless independently confirmed.

On startup, legacy quiz-only rows created before `skill_type` existed are migrated to `study_topic` when their names are not in the taxonomy. This prevents old quiz data from bypassing the Phase 5 filter.

## Endpoints

- `POST /api/career/resume` returns a downloadable DOCX.
- `POST /api/career/gap-analysis` returns required taxonomy skills and missing gaps.

## Automated Tests

```powershell
uv run python -m unittest discover -s tests -v
```

Tests cover study-topic filtering, grounded evidence references, hallucination rejection, and existing-skill exclusion from gaps.

## Live QA

Start the backend:

```powershell
uv run uvicorn main:app --reload
```

First ensure the student has a taxonomy-backed skill through GitHub or manual evidence, for example `Python`. Then call `POST /api/career/gap-analysis`:

```json
{
  "student_id": "demo-student",
  "job_description_text": "We need Python, Docker, and SQL experience."
}
```

`Python` should be excluded if it already exists in the graph; missing taxonomy skills such as `Docker` and `SQL` should appear as gaps.

Call `POST /api/career/resume`:

```json
{
  "student_id": "demo-student",
  "target_role": "Python Developer"
}
```

Download and read the returned DOCX. Every bullet must have been validated against a source reference before the file is created. A deliberately ungrounded model response returns HTTP 400 instead of producing a hallucinated resume.

The DOCX is created fresh for each request, and identical LLM bullets are emitted only once. The target role is included in the generation prompt so the model can prioritize role-relevant taxonomy-backed evidence.