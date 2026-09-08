# Phase 4: Flashcards, Quizzes, and Weak Topics

## Scope

Phase 4 adds quiz generation from indexed document leaf nodes, strict structured-output validation, quiz-attempt persistence, rolling accuracy, and weak-topic reporting. It reuses the existing document index and Phase 2 taxonomy/evidence store.

## Automated Tests

```powershell
uv run python -m unittest discover -s tests -v
```

The tests cover valid fixture generation, malformed JSON, duplicate options, invalid answer indexes, rolling accuracy, weak-topic thresholds, fallback topic handling, and clean per-item errors for invalid blank concepts.

## Live Test

Start the backend:

```powershell
uv run uvicorn main:app --reload
```

In Swagger at `http://127.0.0.1:8000/docs`:

1. Call `POST /api/study/quiz` with an existing document filename:

```json
{"document_id":"your-document.pdf","num_questions":2}
```

2. Submit returned answers through `POST /api/study/quiz/submit`. Use the exact `concept_tag` returned by each question. Known tags are taxonomy-canonicalized; unknown specific quiz tags are stored as normalized fallback topics rather than rejected:

```json
{"attempts":[{"student_id":"demo-student","document_id":"your-document.pdf","concept_tag":"python","correct":false}]}
```

3. Call `GET /api/study/weak-topics/demo-student?threshold=0.7`.
4. Call `GET /api/skills/demo-student` and confirm the quiz evidence is present with `source_type: "quiz"`.

The quiz response includes `requested_count` and `generated_count`. A lower generated count means the indexed document had fewer eligible leaf nodes than requested; it is reported explicitly rather than hidden.

Each document node is isolated during generation. A malformed model response is returned in `errors` with its node ID, while valid questions remain in `questions`.

Batch submission is per-item isolated: valid attempts appear in `results`, while invalid attempts appear in `errors` and do not prevent other answers from being saved.

Run a mix of correct and incorrect attempts for the same concept. Accuracy is calculated as a simple rolling mean for v1; no Bayesian knowledge tracing is used.

## Phase 5 Boundary Decision

Skill entries carry `skill_type`: `taxonomy` for taxonomy-backed/manual/GitHub skills and `study_topic` for quiz-generated fallback concepts such as `Algorithms` or `Machine Learning Challenges`. Weak-topic tracking uses both types. Resume generation and gap analysis must filter resume-grade claims to `skill_type: "taxonomy"` unless a study topic is explicitly mapped to the taxonomy later.