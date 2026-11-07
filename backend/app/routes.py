from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from datetime import datetime, timezone

from app.database import get_db
from app.models import Task, Subtask
from app.schemas import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    PlanningSubmitRequest,
    PlanningSessionResponse,
    PlanningApproveRequest,
    AgentResponseItem,
    ProposedTaskItem,
    SwitchHealthResponse,
    TaskAnalyzeRequest,
    TaskIntelligenceProposal,
    TaskAnalyzeApproveRequest,
)
from app.switch_service import (
    switch_client,
    SWITCH_ROOM_NAME,
    SWITCH_CHANNEL_ID,
    KNOWN_AGENTS,
    DOCKER_RESTART_INSTRUCTIONS,
)

router = APIRouter(prefix="/api")

# In-memory cached session to preserve previously retrieved/approved state if Switch goes down
_cached_session: Optional[Dict] = None


# --- Standard Task CRUD Endpoints ---

@router.get("/tasks", response_model=List[TaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    return db.query(Task).order_by(Task.created_at.desc()).all()


@router.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    subtasks_data = task.subtasks or []
    task_dict = task.model_dump(exclude={"subtasks"})
    db_task = Task(**task_dict)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    for st in subtasks_data:
        db_subtask = Subtask(task_id=db_task.id, title=st.title, status=st.status or "todo")
        db.add(db_subtask)
    if subtasks_data:
        db.commit()
        db.refresh(db_task)

    return db_task


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, task: TaskUpdate, db: Session = Depends(get_db)):
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    for key, value in task.model_dump(exclude_unset=True).items():
        setattr(db_task, key, value)
    db.commit()
    db.refresh(db_task)
    return db_task


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(db_task)
    db.commit()


# --- Switch Multi-Agent Orchestration Endpoints ---

def _extract_tasks_from_markdown(text: str) -> List[ProposedTaskItem]:
    """Parse actionable table lines or bullet points from Nova's consolidated proposal."""
    extracted = []
    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        # Parse markdown schedule tables
        if line.startswith("|") and not line.startswith("|---") and "Time Window" not in line and "Clock Time" not in line:
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 3:
                time_w = parts[0].replace("*", "").strip()
                dur = parts[1].replace("*", "").strip()
                act = parts[2].replace("*", "").strip()
                deliverable = parts[3].replace("*", "").strip() if len(parts) > 3 else ""

                # Filter out pure rest intervals
                if any(k in act.lower() for k in ["break", "buffer", "stretch", "hydration"]):
                    continue

                priority = "high" if any(w in act.lower() for w in ["backend", "dashboard", "api", "core"]) else "medium"
                desc = f"{time_w} ({dur}) - {deliverable}" if deliverable else f"{time_w} ({dur})"
                extracted.append(ProposedTaskItem(
                    title=act,
                    description=desc,
                    priority=priority,
                    status="todo",
                ))
    return extracted


@router.get("/planning/health", response_model=SwitchHealthResponse)
async def get_switch_health():
    """Health-check endpoint for local Switch and Mattermost services."""
    res = await switch_client.health_check()
    return SwitchHealthResponse(**res)


@router.get("/planning/session", response_model=PlanningSessionResponse)
async def get_planning_session():
    """Retrieve real messages from Switch room, calculating accurate per-agent statuses."""
    global _cached_session

    try:
        messages = await switch_client.fetch_recent_messages(limit=50)
    except Exception as e:
        # Fallback handling: If Switch is down, preserve previously cached state if available, clearly flagged
        if _cached_session:
            return PlanningSessionResponse(
                room_name=_cached_session.get("room_name", SWITCH_ROOM_NAME),
                channel_id=_cached_session.get("channel_id", SWITCH_CHANNEL_ID),
                status="disconnected",
                is_complete=False,
                agent_status={k: "failed" for k in KNOWN_AGENTS},
                user_request=_cached_session.get("user_request"),
                nova_proposal=_cached_session.get("nova_proposal"),
                guardian_review=_cached_session.get("guardian_review"),
                agent_responses=_cached_session.get("agent_responses", []),
                proposed_tasks=_cached_session.get("proposed_tasks", []),
                error_message=f"Switch connection lost: {str(e)}",
                restart_instructions=DOCKER_RESTART_INSTRUCTIONS,
                is_fallback=True,
            )

        return PlanningSessionResponse(
            room_name=SWITCH_ROOM_NAME,
            channel_id=SWITCH_CHANNEL_ID,
            status="disconnected",
            is_complete=False,
            agent_status={k: "failed" for k in KNOWN_AGENTS},
            agent_responses=[],
            proposed_tasks=[],
            error_message=f"Cannot reach Switch: {str(e)}",
            restart_instructions=DOCKER_RESTART_INSTRUCTIONS,
            is_fallback=False,
        )

    user_req = None
    nova_prop = None
    guardian_rev = None
    agent_items: List[AgentResponseItem] = []

    # Map roles based on known usernames
    role_map = {
        "nova-anant": "Nova (Coordinator)",
        "scholar-anant": "Scholar (Study Specialist)",
        "builder-anant": "Builder (Project Specialist)",
        "planner-anant": "Planner (Scheduling Specialist)",
        "guardian-anant": "Guardian (Workload Reviewer)",
        "sanant71": "User",
        "user": "User",
        "admin": "Admin",
    }

    # Track which agents have actually responded
    responded_agents = set()

    for m in messages:
        uname = m.get("username", "")
        msg = m.get("message", "")
        msg_id = m.get("id", "")
        created_at = m.get("created_at")

        # User request
        if not user_req and uname in ["sanant71", "user", "admin"] and not msg.endswith("joined the channel."):
            user_req = msg

        # Nova proposal
        if not nova_prop and uname == "nova-anant" and ("Master Schedule" in msg or "consolidated" in msg.lower() or "schedule for" in msg.lower()):
            nova_prop = msg

        # Guardian review
        if not guardian_rev and uname == "guardian-anant" and ("review" in msg.lower() or "safeguards" in msg.lower() or "assessment" in msg.lower()):
            guardian_rev = msg

        # Collect distinct agent contributions
        if uname in role_map and uname not in ["sanant71", "user", "admin"]:
            prefix = uname.split("-")[0]
            responded_agents.add(prefix)
            agent_items.append(AgentResponseItem(
                id=msg_id,
                agent=uname,
                role=role_map.get(uname, uname),
                message=msg,
                created_at=created_at,
            ))

    proposed_tasks = _extract_tasks_from_markdown(nova_prop) if nova_prop else []

    # Compute accurate per-agent statuses (never fabricated)
    agent_status_map: Dict[str, str] = {}
    for ag in KNOWN_AGENTS:
        if ag in responded_agents:
            agent_status_map[ag] = "completed"
        elif user_req and not nova_prop:
            agent_status_map[ag] = "processing"
        elif user_req and nova_prop and ag not in responded_agents:
            agent_status_map[ag] = "failed"
        else:
            agent_status_map[ag] = "pending"

    is_complete = bool(nova_prop and guardian_rev and len(proposed_tasks) > 0)
    session_status = "ready" if is_complete else ("partial" if nova_prop else "pending")

    session_data = {
        "room_name": SWITCH_ROOM_NAME,
        "channel_id": SWITCH_CHANNEL_ID,
        "status": session_status,
        "is_complete": is_complete,
        "agent_status": agent_status_map,
        "user_request": user_req,
        "nova_proposal": nova_prop,
        "guardian_review": guardian_rev,
        "agent_responses": agent_items[:15],
        "proposed_tasks": proposed_tasks,
        "error_message": None,
        "restart_instructions": None,
        "is_fallback": False,
    }

    _cached_session = session_data
    return PlanningSessionResponse(**session_data)


@router.post("/planning/submit", response_model=PlanningSessionResponse)
async def submit_planning_request(req: PlanningSubmitRequest):
    """Post user request to Nova in Switch room and wait for agent responses."""
    if not req.request.strip():
        raise HTTPException(status_code=400, detail="Planning request cannot be empty")

    post_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    try:
        await switch_client.send_planning_request(req.request)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send request to Switch: {str(e)}")

    # Wait for agents with non-blocking async poll
    try:
        await switch_client.wait_for_agent_responses(after_timestamp=post_time_ms, timeout_seconds=12, poll_interval=2.0)
    except Exception:
        pass

    return await get_planning_session()


@router.post("/planning/approve", response_model=List[TaskResponse])
def approve_planning_session(body: PlanningApproveRequest, db: Session = Depends(get_db)):
    """User-approved action: commit proposed tasks into SQLite only after explicit user approval."""
    if not body.tasks:
        raise HTTPException(status_code=400, detail="No tasks provided for approval")

    created_records = []
    for t in body.tasks:
        db_task = Task(
            title=t.title,
            description=t.description,
            priority=t.priority or "medium",
            status="todo",
            due_date=None,
        )
        db.add(db_task)
        created_records.append(db_task)

    db.commit()
    for record in created_records:
        db.refresh(record)

    return created_records


# --- Real AI Task Intelligence Endpoints ---

def _parse_task_intelligence(
    messages: List[Dict],
    title: str,
    orig_desc: str,
    orig_priority: str,
) -> TaskIntelligenceProposal:
    """Parse real contributions from Nova, Scholar, Builder, Planner, and Guardian for a task."""
    subtasks = []
    research_notes = None
    tech_rec = None
    schedule_sugg = None
    risk_assessment = None
    priority = orig_priority
    deadline = None
    raw_responses = []

    role_map = {
        "nova-anant": "Nova (Coordinator)",
        "scholar-anant": "Scholar (Study Specialist)",
        "builder-anant": "Builder (Project Specialist)",
        "planner-anant": "Planner (Scheduling Specialist)",
        "guardian-anant": "Guardian (Workload Reviewer)",
    }

    agent_status = {k: "pending" for k in KNOWN_AGENTS}

    for m in messages:
        uname = m.get("username", "")
        msg = m.get("message", "").strip()
        uid = m.get("id", "")
        cat = m.get("created_at")

        if uname in role_map:
            prefix = uname.split("-")[0]
            agent_status[prefix] = "completed"
            raw_responses.append(AgentResponseItem(
                id=uid,
                agent=uname,
                role=role_map[uname],
                message=msg,
                created_at=cat,
            ))

            # Nova: Subtasks breakdown & categorization / priority
            if prefix == "nova":
                for line in msg.split("\n"):
                    l = line.strip()
                    if l.startswith("- [ ]") or l.startswith("- ") or l.startswith("* "):
                        clean_item = l.lstrip("-* [ ]").strip()
                        if clean_item and not clean_item.lower().startswith("priority") and clean_item not in subtasks:
                            subtasks.append(clean_item)
                    if "high priority" in l.lower():
                        priority = "high"
                    elif "low priority" in l.lower():
                        priority = "low"
                    elif "medium priority" in l.lower():
                        priority = "medium"

            # Scholar: Research notes & references
            elif prefix == "scholar":
                research_notes = msg

            # Builder: Technical recommendations
            elif prefix == "builder":
                tech_rec = msg

            # Planner: Schedule suggestions & deadlines
            elif prefix == "planner":
                schedule_sugg = msg
                # Extract suggested deadline or duration if present
                for line in msg.split("\n"):
                    if any(k in line.lower() for k in ["deadline", "due", "schedule:", "time:"]):
                        deadline = line.strip()
                        break

            # Guardian: Risks & blockers
            elif prefix == "guardian":
                risk_assessment = msg

    # Fallback subtasks extraction from schedule tables or bullet lists if Nova didn't format as markdown bullets
    if not subtasks:
        for m in raw_responses:
            if m.agent.startswith("planner") or m.agent.startswith("builder"):
                for line in m.message.split("\n"):
                    l = line.strip()
                    if l.startswith("|") and not l.startswith("|---") and not "Clock Time" in l and not "Duration" in l:
                        parts = [p.strip() for p in l.split("|")[1:-1]]
                        if len(parts) >= 3 and not any(k in parts[2].lower() for k in ["break", "buffer"]):
                            subtasks.append(f"{parts[0]}: {parts[2]}")

    is_complete = any(status == "completed" for status in agent_status.values())

    return TaskIntelligenceProposal(
        title=title,
        description=orig_desc,
        priority=priority,
        suggested_deadline=deadline,
        subtasks=subtasks[:8],
        research_notes=research_notes,
        technical_recommendations=tech_rec,
        schedule_suggestion=schedule_sugg,
        risk_assessment=risk_assessment,
        agent_status=agent_status,
        is_complete=is_complete,
        raw_responses=raw_responses[:10],
    )


@router.post("/tasks/analyze", response_model=TaskIntelligenceProposal)
async def analyze_task_with_ai(req: TaskAnalyzeRequest):
    """Send task analysis request to Nova in Switch room and collect multi-agent intelligence."""
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="Task title cannot be empty")

    prompt = (
        f"@nova-anant Please analyze and break down this task with the AI team:\n"
        f"Task: {req.title.strip()}\n"
        f"Details: {req.description.strip() if req.description else 'None provided'}\n"
        f"Initial Priority: {req.priority}\n\n"
        f"Please coordinate:\n"
        f"1. Nova: Categorize, prioritize, and break down into 3-5 actionable subtasks.\n"
        f"2. Scholar: Provide research notes and reference patterns.\n"
        f"3. Builder: Recommend technical implementation details.\n"
        f"4. Planner: Suggest schedule and realistic deadline.\n"
        f"5. Guardian: Identify risks, bottlenecks, and safeguards."
    )

    post_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    try:
        await switch_client.send_planning_request(prompt)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach Switch multi-agent room: {str(e)}")

    # Non-blocking async poll for specialist replies
    try:
        await switch_client.wait_for_agent_responses(after_timestamp=post_time_ms, timeout_seconds=14, poll_interval=2.0)
    except Exception:
        pass

    try:
        messages = await switch_client.fetch_recent_messages(limit=40)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch agent responses: {str(e)}")

    return _parse_task_intelligence(messages, req.title, req.description or "", req.priority or "medium")


@router.post("/tasks/analyze/approve", response_model=TaskResponse, status_code=201)
def approve_analyzed_task(body: TaskAnalyzeApproveRequest, db: Session = Depends(get_db)):
    """User-approved action: commit the AI-analyzed task and its subtasks to SQLite."""
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Task title cannot be empty")

    db_task = Task(
        title=body.title.strip(),
        description=body.description.strip() if body.description else "",
        priority=body.priority or "medium",
        status=body.status or "todo",
        due_date=body.due_date,
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    for st_title in body.subtasks:
        if st_title.strip():
            db_subtask = Subtask(
                task_id=db_task.id,
                title=st_title.strip(),
                status="todo",
            )
            db.add(db_subtask)

    if body.subtasks:
        db.commit()
        db.refresh(db_task)

    return db_task
