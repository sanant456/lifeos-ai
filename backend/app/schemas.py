from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any


class SubtaskCreate(BaseModel):
    title: str
    status: str = "todo"


class SubtaskResponse(BaseModel):
    id: int
    task_id: int
    title: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    status: str = "todo"
    due_date: Optional[datetime] = None
    subtasks: Optional[List[SubtaskCreate]] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[datetime] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str
    priority: str
    status: str
    due_date: Optional[datetime]
    created_at: datetime
    subtasks: List[SubtaskResponse] = []

    model_config = {"from_attributes": True}


# Multi-Agent Planning Schemas
class SwitchHealthResponse(BaseModel):
    switch_available: bool
    mattermost_available: bool
    channel_accessible: bool
    agents_configured: List[str]
    error_message: Optional[str] = None
    restart_instructions: Optional[str] = None


class PlanningSubmitRequest(BaseModel):
    request: str
    channel_id: Optional[str] = None


class AgentResponseItem(BaseModel):
    id: str
    agent: str
    role: str
    message: str
    created_at: Optional[int] = None


class ProposedTaskItem(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    status: str = "todo"
    due_date: Optional[str] = None


class PlanningSessionResponse(BaseModel):
    room_name: str
    channel_id: str
    status: str  # ready, pending, disconnected, partial
    is_complete: bool = False
    agent_status: Dict[str, str] = {}  # agent_name -> "completed" | "processing" | "failed" | "pending"
    user_request: Optional[str] = None
    nova_proposal: Optional[str] = None
    guardian_review: Optional[str] = None
    agent_responses: List[AgentResponseItem] = []
    proposed_tasks: List[ProposedTaskItem] = []
    error_message: Optional[str] = None
    restart_instructions: Optional[str] = None
    is_fallback: bool = False


class PlanningApproveRequest(BaseModel):
    tasks: List[ProposedTaskItem]


# AI Task Intelligence Schemas
class TaskAnalyzeRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    priority: Optional[str] = "medium"


class TaskIntelligenceProposal(BaseModel):
    title: str
    description: str
    priority: str
    suggested_deadline: Optional[str] = None
    subtasks: List[str] = []
    research_notes: Optional[str] = None
    technical_recommendations: Optional[str] = None
    schedule_suggestion: Optional[str] = None
    risk_assessment: Optional[str] = None
    agent_status: Dict[str, str] = {}
    is_complete: bool = False
    raw_responses: List[AgentResponseItem] = []


class TaskAnalyzeApproveRequest(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    status: str = "todo"
    due_date: Optional[datetime] = None
    subtasks: List[str] = []
