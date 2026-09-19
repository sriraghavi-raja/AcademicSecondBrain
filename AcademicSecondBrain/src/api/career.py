import os
import tempfile
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from src.rag.registry.career import get_profile, upsert_profile, upsert_project
from src.rag.registry.sessions import SessionNotFoundError
from src.api.auth import get_current_user
from src.services.career_service import extract_certification, generate_resume, suggest_skill_gaps
from src.services.interview_service import continue_interview, end_interview, start_interview
from src.services.dashboard_service import get_dashboard


router = APIRouter(prefix="/api/career", tags=["Career"])
profile_router = APIRouter(prefix="/api/profile", tags=["Profile"])
dashboard_router = APIRouter(tags=["Dashboard"])


class ResumeRequest(BaseModel):
    target_role: str | None = None


class GapRequest(BaseModel):
    job_description_text: str = Field(min_length=1)


class ProfileRequest(BaseModel):
    full_name: str = Field(min_length=1)
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    college_name: str | None = None
    degree: str | None = None
    branch: str | None = None
    college_start: str | None = None
    college_end: str | None = None
    cgpa: str | None = None
    school_name: str | None = None
    school_detail: str | None = None
    school_dates: str | None = None
    school_score: str | None = None


class ProjectRequest(BaseModel):
    title: str = Field(min_length=1)
    tech_stack: str = Field(min_length=1)
    description_text: str = Field(min_length=1)


class InterviewStartRequest(BaseModel):
    target_role: str = Field(min_length=1)
    mode: str = "technical"


class InterviewContinueRequest(BaseModel):
    session_id: str = Field(min_length=1)
    answer: str = Field(min_length=1)


class InterviewEndRequest(BaseModel):
    session_id: str = Field(min_length=1)


@dashboard_router.get("/api/career/dashboard")
def career_dashboard(current_user: Annotated[dict, Depends(get_current_user)]):
    return get_dashboard(current_user["user_id"])


@dashboard_router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    return HTMLResponse(f"""
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Career Readiness</title><style>
:root {{ --ink:#182230; --muted:#687587; --line:#dfe5eb; --paper:#f6f8fa; --accent:#176b87; --warm:#ee9b4d; }}
* {{ box-sizing:border-box }} body {{ margin:0; background:var(--paper); color:var(--ink); font:14px/1.45 Arial,sans-serif }}
main {{ max-width:1180px; margin:auto; padding:32px 22px }} header {{ display:flex; justify-content:space-between; align-items:end; gap:16px; margin-bottom:24px }}
h1 {{ margin:0; font-size:32px; letter-spacing:-.5px }} h2 {{ margin:0 0 14px; font-size:17px }} .muted {{ color:var(--muted) }}
.grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:16px }} .stat,.panel {{ background:white; border:1px solid var(--line); border-radius:8px; padding:16px }}
.stat strong {{ display:block; font-size:27px; color:var(--accent) }} .layout {{ display:grid; grid-template-columns:1.15fr .85fr; gap:16px }}
.panel {{ margin-bottom:16px }} .skill {{ display:grid; grid-template-columns:145px 1fr 50px; align-items:center; gap:10px; margin:12px 0 }}
.bar {{ height:8px; background:#e9eef2; border-radius:8px; overflow:hidden }} .bar i {{ display:block; height:100%; background:var(--accent); border-radius:8px }}
.topic,.timeline-item,.project {{ border-top:1px solid var(--line); padding:11px 0 }} .topic:first-child,.timeline-item:first-child,.project:first-child {{ border-top:0 }}
.topic {{ display:flex; justify-content:space-between }} .badge {{ color:#9a581e; background:#fff1df; padding:3px 8px; border-radius:99px; font-size:12px }}
@media(max-width:760px) {{ header,.layout {{ display:block }} .grid {{ grid-template-columns:repeat(2,1fr) }} .skill {{ grid-template-columns:105px 1fr 42px }} }}
</style></head><body><main><header><div><div class="muted">Academic Second Brain</div><h1 id="name">Career readiness</h1><div id="subtitle" class="muted">Loading student journey...</div></div></header>
<section class="grid" id="stats"></section><div class="layout"><div><section class="panel"><h2>Skills</h2><div id="skills"></div></section><section class="panel"><h2>Projects</h2><div id="projects"></div></section></div><div><section class="panel"><h2>Weak topics</h2><div id="weak"></div></section><section class="panel"><h2>Achievements</h2><div id="achievements"></div></section><section class="panel"><h2>Recent career activity</h2><div id="runs"></div></section></div></div></main>
<script>fetch('/api/career/dashboard').then(r=>r.json()).then(d=>{{
document.querySelector('#name').textContent=d.profile?.full_name||'Career readiness'; document.querySelector('#subtitle').textContent=[d.profile?.degree,d.profile?.branch,d.profile?.location].filter(Boolean).join(' · ')||'Build your learning journey';
const s=d.summary; document.querySelector('#stats').innerHTML=[['Skills',s.skill_count],['Projects',s.project_count],['Achievements',s.achievement_count],['Weak topics',s.weak_topic_count]].map(x=>`<div class="stat"><span class="muted">${{x[0]}}</span><strong>${{x[1]}}</strong></div>`).join('');
document.querySelector('#skills').innerHTML=d.skills.filter(x=>x.skill_type==='taxonomy').map(x=>`<div class="skill"><span>${{x.skill_name}}</span><div class="bar"><i style="width:${{Math.round((x.confidence||0)*100)}}%"></i></div><span>${{Math.round((x.confidence||0)*100)}}%</span></div>`).join('')||'<span class="muted">Add evidence to see mastery.</span>';
document.querySelector('#weak').innerHTML=d.weak_topics.filter(x=>x.accuracy<.7).map(x=>`<div class="topic"><span>${{x.concept_tag}}</span><span class="badge">${{Math.round(x.accuracy*100)}}% · ${{x.attempts}} attempts</span></div>`).join('')||'<span class="muted">No weak topics yet.</span>';
document.querySelector('#projects').innerHTML=d.projects.map(x=>`<div class="project"><strong>${{x.title}}</strong><div class="muted">${{x.tech_stack}}</div></div>`).join('')||'<span class="muted">No projects added yet.</span>';
document.querySelector('#achievements').innerHTML=d.achievements.map(x=>`<div class="timeline-item"><strong>${{x.name}}</strong><div class="muted">${{x.awarded_at||x.created_at||''}}</div></div>`).join('')||'<span class="muted">No achievements yet.</span>';
document.querySelector('#runs').innerHTML=Object.entries(d.last_runs).map(([k,v])=>`<div class="timeline-item"><strong>${{k}}</strong><div class="muted">${{v.created_at}}</div></div>`).join('')||'<span class="muted">No resume or gap-analysis runs yet.</span>';
}}).catch(()=>document.querySelector('main').innerHTML='<p>Dashboard data could not be loaded.</p>');</script></body></html>""")


@router.post("/interview/start")
async def interview_start(
    data: InterviewStartRequest,
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    try:
        return await start_interview(current_user["user_id"], data.target_role, data.mode, request.app.state.llm)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/interview/continue")
async def interview_continue(
    data: InterviewContinueRequest,
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    try:
        return await continue_interview(
            current_user["user_id"], data.session_id, data.answer, request.app.state.llm
        )
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/interview/end")
def interview_end(data: InterviewEndRequest, current_user: Annotated[dict, Depends(get_current_user)]):
    try:
        return end_interview(current_user["user_id"], data.session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@profile_router.put("")
def put_profile(data: ProfileRequest, current_user: Annotated[dict, Depends(get_current_user)]):
    return upsert_profile(current_user["user_id"], data.model_dump())


@profile_router.get("")
def read_profile(current_user: Annotated[dict, Depends(get_current_user)]):
    profile = get_profile(current_user["user_id"])
    if profile is None:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return profile


@router.post("/projects")
def post_project(data: ProjectRequest, current_user: Annotated[dict, Depends(get_current_user)]):
    student_id = current_user["user_id"]
    return upsert_project(
        student_id,
        data.title,
        data.tech_stack,
        "manual",
        f"manual:{student_id}:{data.title.strip().lower()}",
        data.description_text,
    )


@router.post("/certifications")
async def post_certification(
    request: Request,
    file: UploadFile = File(...),
    current_user: Annotated[dict, Depends(get_current_user)] = None,
):
    student_id = current_user["user_id"]
    suffix = os.path.splitext(file.filename or "certificate.pdf")[1] or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary_file:
        temporary_file.write(await file.read())
        temporary_path = temporary_file.name
    try:
        return await extract_certification(
            temporary_path,
            request.app.state.llm,
            student_id,
            file.filename,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


@router.post("/resume")
async def create_resume(
    data: ResumeRequest,
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    try:
        result = await generate_resume(
            current_user["user_id"],
            request.app.state.retriever,
            request.app.state.llm,
            data.target_role,
        )
        return FileResponse(result["file_path"], filename=f"{current_user['user_id']}_resume.docx")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/gap-analysis")
async def gap_analysis(
    data: GapRequest,
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    try:
        return await suggest_skill_gaps(current_user["user_id"], data.job_description_text, request.app.state.llm)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error