<div align="center">

<img src="docs/assets/lifeos-banner.png" alt="LifeOS AI Banner" width="100%" />

<br/><br/>

<img src="docs/assets/lifeos-logo.png" alt="LifeOS AI Logo" width="80" height="80" />

# LifeOS AI
### Autonomous Productivity Platform & Multi-Agent Collaboration Engine

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js%2016-black?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org/)
[![TypeScript](https://img.shields.io/badge/Language-TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Python](https://img.shields.io/badge/Language-Python%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Tailwind CSS](https://img.shields.io/badge/Styling-Tailwind%20CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite%20%2B%20SQLAlchemy-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org/)
[![Tests](https://img.shields.io/badge/Pytest-19%2F19%20Passing-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/)

<p align="center">
  <b>A real multi-agent productivity platform coordinating specialized AI agents through Switch, delivering synthesized planning and task intelligence with mandatory human approval.</b>
</p>

[Key Features](#key-features) • [AI Team](#meet-the-ai-team) • [System Architecture](#system-architecture) • [Getting Started](#getting-started) • [API Documentation](#api-documentation) • [Testing](#testing)

---

</div>

## 📌 Overview & Problem Statement

Modern productivity systems force users into a single bottleneck: manual planning, scheduling, risk assessment, and technical prioritization. When attempting to use AI for productivity, users are commonly offered generic single-prompt chatbots that provide hallucinated schedules, lack specialized domain reasoning, and cannot safely bridge planning directly into persistent task management.

**LifeOS AI** solves this through **specialized multi-agent orchestration**:
1. **Domain Division of Labor:** Instead of one generalist LLM guessing everything, five distinct agents deliberate across scheduling, technical architecture, academic learning, and cognitive workload safeguards.
2. **Real Agent Communication via Switch:** Orchestrates real inter-agent messaging over Mattermost channels (`#lifeos-planning`) via the Switch multi-agent runtime.
3. **Mandatory Human-in-the-Loop:** Agents can propose schedules, subtasks, and architectural blueprints, but **nothing is written to persistent SQLite storage without explicit user confirmation**.

---

## ⚡ Key Features

- 🧠 **Autonomous Planning Orchestrator:** Send high-level execution goals directly to Nova to trigger cross-agent deliberation and generate consolidated time-blocked master schedules.
- 🎯 **Real AI Task Intelligence:** Instant "Analyze with AI Team" workflow directly in task creation that synthesizes subtasks, research references, architectural recommendations, timeline estimates, and risk assessments.
- 👥 **Real-Time Agent Status Tracker:** Live tracking of completed, processing, failed, and pending states across all 5 specialist agents without fabricated statuses.
- 🛡️ **Guardian Cognitive Safeguards:** Automated review of schedule proposals to identify cognitive fatigue, missing buffer time, and strict dependency bottlenecks.
- ⚡ **Resilient Switch Integration:** Non-blocking asynchronous polling, automatic retry with exponential backoff on 502/timeout errors, and backend health-check (`GET /api/planning/health`).
- 💾 **Graceful Fallback & Persistence:** Automatic cached state preservation when Switch is offline, coupled with clear Docker/Switch recovery guidance.
- 🗄️ **Full Task & Subtask Management:** Complete CRUD support persisted in SQLite with subtask hierarchies and real-time dashboard analytics.

---

## 👥 Meet the AI Team

<div align="center">
  <img src="docs/assets/agent-team.png" alt="LifeOS AI Agent Team" width="85%" />
</div>

<br/>

| Agent | Role | Specialization & Focus | Room Handle |
| :--- | :--- | :--- | :--- |
| **Nova** | **Central Coordinator** | Deconstructs requests, coordinates specialist hand-offs, resolves conflicts, and compiles consolidated proposals. | `@nova-anant` |
| **Scholar** | **Academic Assistant** | Provides learning roadmaps, active recall intervals, algorithm research, and conceptual references. | `@scholar-anant` |
| **Builder** | **Project Specialist** | Formulates technical architectures, data schemas, API contracts, and implementation blueprints. | `@builder-anant` |
| **Planner** | **Scheduling Specialist** | Calculates duration estimates, balances workloads, and constructs realistic time-blocked schedules. | `@planner-anant` |
| **Guardian** | **Workload & Risk Reviewer** | Inspects schedules for cognitive overload, enforces break distribution, and identifies critical single-points-of-failure. | `@guardian-anant` |

---

## 🏗️ System Architecture

mermaid
graph TD
    User([User / Operator]) -->|Interacts| UI[Next.js 16 + React Dark Dashboard]
    
    subgraph Frontend [Frontend Client :3000]
        UI --> TaskView[Tasks & Subtasks Section]
        UI --> PlanView[Planning Orchestrator]
        UI --> IntelModal[Task Intelligence Modal]
        UI --> HealthMonitor[Switch Health Poller 30s]
    end

    Frontend -->|REST HTTP / JSON| FastAPI[FastAPI Backend :8000]

    subgraph Backend [FastAPI Application]
        FastAPI --> CRUD[Task & Subtask CRUD APIs]
        FastAPI --> HealthEP[/api/planning/health]
        FastAPI --> PlanEP[/api/planning/submit & session]
        FastAPI --> IntelEP[/api/tasks/analyze]
        FastAPI --> ApproveEP[/api/planning/approve & /api/tasks/analyze/approve]
        FastAPI --> SwitchService[SwitchClient Async Service]
        FastAPI --> CacheLayer[(In-Memory Resilient Fallback Cache)]
    end

    subgraph DataStore [Application Database]
        ApproveEP -->|Commit on Approval ONLY| SQLite[(lifeos.db SQLite)]
        CRUD <--> SQLite
    end

    subgraph SwitchInfra [Switch Multi-Agent Runtime]
        SwitchService <-->|REST v4 Auth Bearer| Mattermost[Mattermost Server :49375]
        Mattermost <--> SwitchCore[Switch Core Engine :49374]
        Mattermost <--> PostgreSQL[(Switch PostgreSQL :49376)]
        
        subgraph Channel [Channel: #lifeos-planning]
            Nova[Nova - Coordinator]
            Scholar[Scholar - Research]
            Builder[Builder - Architecture]
            Planner[Planner - Scheduling]
            Guardian[Guardian - Risk & Safeguards]
        end

        SwitchCore --> Channel
    end


---

## 🔄 Agent Collaboration Workflow

mermaid
sequenceDiagram
    autonumber
    actor User as Operator
    participant UI as Next.js Dashboard
    participant API as FastAPI Backend
    participant Switch as Switch Room (#lifeos-planning)
    participant Agents as Nova & Specialist Agents
    participant DB as SQLite DB

    User->>UI: Request plan or click "Analyze with AI Team"
    UI->>API: POST /api/planning/submit or POST /api/tasks/analyze
    API->>Switch: Post formatted deliberation prompt to Nova
    Note over Switch,Agents: Real deliberation in Switch Room
    Switch->>Agents: Nova assigns sub-goals to Scholar, Builder, Planner
    Agents->>Switch: Specialists submit recommendations & timelines
    Switch->>Agents: Guardian reviews proposed workload & breaks
    Switch->>Agents: Nova synthesizes consolidated proposal
    API->>Switch: Non-blocking async poll for new responses
    Switch-->>API: Deliberation messages & structured proposals
    API-->>UI: Consolidated proposal + subtasks + agent statuses
    Note over User,UI: Human-in-the-Loop Decision Gate
    alt User Rejects
        User->>UI: Click "Reject Plan"
        UI-->>User: Plan discarded, nothing saved to database
    else User Approves
        User->>UI: Click "Approve & Save to SQLite"
        UI->>API: POST /api/planning/approve or /api/tasks/analyze/approve
        API->>DB: INSERT tasks & subtasks into SQLite
        DB-->>API: Confirm committed records
        API-->>UI: Return saved tasks
        UI-->>User: Updated task list & dashboard metrics
    end


---

## 💻 Technology Stack

| Layer | Technologies | Role in LifeOS AI |
| :--- | :--- | :--- |
| **Frontend** | **Next.js 16.4 (Turbopack), React 19, TypeScript** | Client-side reactive dark UI, state management, and real-time streaming view. |
| **Styling & UI** | **Tailwind CSS, Lucide React** | Premium dark-tech aesthetic, responsive glassmorphism, animated status chips. |
| **Backend** | **Python 3.13, FastAPI, Uvicorn, Pydantic v2** | High-performance asynchronous API layer, schemas, validation, and multi-agent gateway. |
| **Database** | **SQLite, SQLAlchemy 2.0** | Relational persistence for tasks and subtask hierarchies (`lifeos.db`). |
| **Multi-Agent Runtime** | **Switch Core, Switch Console, Mattermost REST v4, ACP** | Local multi-agent orchestration, agent process controllers, and inter-agent message buses. |
| **Container & Storage** | **Docker, PostgreSQL 16** | Infrastructure hosting the local Switch Mattermost container and agent states. |
| **Testing** | **Pytest, AnyIO, Starlette TestClient** | Automated regression testing covering CRUD, timeouts, agent parsing, and approvals. |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+** (Python 3.13 tested)
- **Node.js 18+** & **npm**
- **Docker Desktop** (running)
- **Switch Console** with configured agents (`nova-anant`, `scholar-anant`, `builder-anant`, `planner-anant`, `guardian-anant`)

### 1. Clone the Repository

```bash
git clone https://github.com/sanant456/lifeos-ai.git
cd lifeos-ai
```

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

Ensure `.env` matches your local Switch deployment:
```ini
SWITCH_MATTERMOST_URL=http://localhost:49375
SWITCH_BOT_TOKEN=your_switch_token
SWITCH_CHANNEL_ID=bk7165is4bb6ugqtr3fcer1hur
SWITCH_ROOM_NAME=lifeos-planning
SWITCH_NOVA_HANDLE=@nova-anant
```

Start the FastAPI server:
```bash
uvicorn app.main:app --reload --port 8000
```
Backend will be live at `http://localhost:8000`.

### 3. Frontend Setup

In a separate terminal:
```bash
cd frontend

# Install dependencies
npm install

# Start Next.js development server
npm run dev
```
Open your browser at `http://localhost:3000`.

---

## 📖 API Documentation

FastAPI provides interactive Swagger documentation out of the box:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Key Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Basic application health check. |
| `GET` | `/api/tasks` | List all tasks with their subtasks. |
| `POST` | `/api/tasks` | Create a new task (with optional subtasks). |
| `PATCH` | `/api/tasks/{id}` | Update task title, description, priority, or status. |
| `DELETE` | `/api/tasks/{id}` | Delete a task and cascade its subtasks. |
| `GET` | `/api/planning/health` | Live Switch & Mattermost connectivity diagnostic. |
| `GET` | `/api/planning/session` | Fetch recent room messages, Nova proposal, and Guardian review. |
| `POST` | `/api/planning/submit` | Deliver user planning prompt to Nova in Switch room. |
| `POST` | `/api/planning/approve` | **Human-Approval Gate:** Persist proposed plan tasks into SQLite. |
| `POST` | `/api/tasks/analyze` | Request 5-agent deliberation for a specific task. |
| `POST` | `/api/tasks/analyze/approve` | **Human-Approval Gate:** Save analyzed task and subtasks to SQLite. |

---

## 🧪 Testing

The backend includes a comprehensive automated test suite with **19 test cases** covering CRUD operations, multi-agent parsing, Switch error handling, connection dropouts, fallback preservation, and human-approval gates.

### Run Backend Tests

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

**Results:**
```text
======================== 19 passed, 1 warning in 0.08s =========================
tests/test_api.py::test_health PASSED
tests/test_api.py::test_create_task PASSED
tests/test_api.py::test_list_tasks PASSED
tests/test_api.py::test_update_task PASSED
tests/test_api.py::test_update_task_not_found PASSED
tests/test_api.py::test_delete_task PASSED
tests/test_api.py::test_delete_task_not_found PASSED
tests/test_intelligence.py::test_analyze_task_with_ai PASSED
tests/test_intelligence.py::test_approve_analyzed_task_saves_to_sqlite PASSED
tests/test_intelligence.py::test_analyze_task_empty_title_rejected PASSED
tests/test_intelligence.py::test_approve_analyzed_task_empty_title_rejected PASSED
tests/test_planning.py::test_planning_session_endpoint PASSED
tests/test_planning.py::test_planning_session_switch_down PASSED
tests/test_planning.py::test_planning_session_fallback_preserves_data PASSED
tests/test_planning.py::test_planning_health_endpoint_up PASSED
tests/test_planning.py::test_planning_health_endpoint_down PASSED
tests/test_planning.py::test_planning_approve_saves_to_sqlite PASSED
tests/test_planning.py::test_planning_approve_empty_rejected PASSED
tests/test_planning.py::test_planning_submit_empty_rejected PASSED
```

### Run Frontend Production Verification

```bash
cd frontend
npm run build
```
Compiles successfully with **0 TypeScript and ESLint errors**.

---

## 📁 Project Folder Structure

```text
lifeos-ai/
├── README.md                           # Main project documentation
├── docs/
│   └── assets/                         # Generated branding and architecture assets
│       ├── lifeos-banner.png           # 16:9 Hero banner
│       ├── lifeos-logo.png             # Logo mark
│       └── agent-team.png              # 5-Agent team diagram
├── backend/
│   ├── .env.example                    # Template for backend secrets and Switch ports
│   ├── requirements.txt                # Python backend dependencies
│   ├── lifeos.db                       # Local SQLite application database
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI application setup & CORS configuration
│   │   ├── database.py                 # SQLAlchemy engine and session factory
│   │   ├── models.py                   # Task and Subtask database models
│   │   ├── schemas.py                  # Pydantic v2 validation models
│   │   ├── routes.py                   # CRUD and multi-agent endpoints
│   │   └── switch_service.py           # SwitchClient HTTP integration service
│   └── tests/
│       ├── conftest.py                 # Shared test database fixtures
│       ├── test_api.py                 # Task CRUD API tests
│       ├── test_planning.py            # Switch planning & resiliency tests
│       └── test_intelligence.py        # Real AI Task Intelligence tests
└── frontend/
    ├── package.json                    # Frontend dependencies and scripts
    ├── tsconfig.json                   # TypeScript configuration
    ├── next.config.ts                  # Next.js configuration
    ├── .env.local                      # Frontend API base URL configuration
    └── src/
        ├── app/
        │   ├── layout.tsx              # Root HTML wrapper and fonts
        │   ├── page.tsx                # Dynamic multi-tab application orchestrator
        │   └── globals.css             # Tailwind dark-mode styles
        ├── components/
        │   ├── Sidebar.tsx             # Collapsible navigation drawer with task counters
        │   ├── DashboardView.tsx       # Real-time statistics, progress bars, and priorities
        │   ├── TasksSection.tsx        # Task filterable list and subtask rendering
        │   ├── TaskModal.tsx           # Create/edit task modal with AI analysis trigger
        │   ├── PlanningInterface.tsx   # Autonomous planning view with status chips
        │   ├── AITeamSection.tsx       # Live cards detailing the 5 Switch agents
        │   └── OtherSections.tsx       # Project milestones and productivity insights
        ├── lib/
        │   └── api.ts                  # Fetch client for backend endpoints
        └── types/
            └── task.ts                 # TypeScript interfaces for tasks, health, and proposals
```

---

## ⚠️ Known Limitations & Future Roadmap

### Current Limitations
1. **Local Daemon Dependency:** Communication relies on a local Switch runtime (Mattermost on port 49375 and Docker). If Docker is suspended, the frontend enters cached fallback mode until restarted.
2. **Channel Polling:** Agent message collection relies on asynchronous HTTP polling loops. Webhook or WebSocket events will offer lower latency once exposed in Switch core.

### Future Roadmap
- [ ] Direct WebSocket push streaming for real-time token-by-token deliberation display.
- [ ] Automated subtask execution runners via Antigravity Agent Controller Protocol (ACP).
- [ ] Calendar integration (Google Calendar / iCal export) for one-click approved schedule syncing.
- [ ] Multi-room support for separating personal, engineering, and academic life domains.

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/amazing-feature`).
3. Ensure backend tests pass (`pytest tests/`) and frontend compiles (`npm run build`).
4. Commit your changes (`git commit -m 'Add amazing feature'`).
5. Push to the branch (`git push origin feature/amazing-feature`).
6. Open a Pull Request.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  <sub>Built with ❤️ for the Google Antigravity &amp; Switch Multi-Agent Hackathon.</sub>
</div>

