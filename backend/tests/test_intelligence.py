from unittest.mock import patch, AsyncMock


def test_analyze_task_with_ai(client):
    mock_messages = [
        {
            "id": "m1",
            "username": "nova-anant",
            "message": "Nova Breakdown:\n- [ ] Design SQLite schema\n- [ ] Implement CRUD routes\n- [ ] Add unit tests\nPriority: High priority task",
            "created_at": 1793988000000,
        },
        {
            "id": "m2",
            "username": "scholar-anant",
            "message": "Scholar notes: Review SQLAlchemy 2.0 async paradigms and relationships.",
            "created_at": 1793988001000,
        },
        {
            "id": "m3",
            "username": "builder-anant",
            "message": "Builder recommendation: Use Pydantic v2 schemas and SQLite foreign keys.",
            "created_at": 1793988002000,
        },
        {
            "id": "m4",
            "username": "planner-anant",
            "message": "Planner schedule: Complete in 90 minutes. Deadline: Tomorrow 5 PM.",
            "created_at": 1793988003000,
        },
        {
            "id": "m5",
            "username": "guardian-anant",
            "message": "Guardian review: Guard against missing DB indices and unhandled connection timeouts.",
            "created_at": 1793988004000,
        },
    ]

    with patch("app.switch_service.switch_client.send_planning_request", new_callable=AsyncMock) as mock_send, \
         patch("app.switch_service.switch_client.wait_for_agent_responses", new_callable=AsyncMock) as mock_wait, \
         patch("app.switch_service.switch_client.fetch_recent_messages", new_callable=AsyncMock) as mock_fetch:

        mock_send.return_value = {"id": "post123"}
        mock_wait.return_value = mock_messages
        mock_fetch.return_value = mock_messages

        res = client.post(
            "/api/tasks/analyze",
            json={"title": "Build AI Intelligence Pipeline", "description": "Integrate Switch agents", "priority": "medium"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["title"] == "Build AI Intelligence Pipeline"
        assert data["priority"] == "high"
        assert len(data["subtasks"]) == 3
        assert "Design SQLite schema" in data["subtasks"]
        assert "Scholar notes" in data["research_notes"]
        assert "Builder recommendation" in data["technical_recommendations"]
        assert "Planner schedule" in data["schedule_suggestion"]
        assert "Guardian review" in data["risk_assessment"]
        assert data["agent_status"]["nova"] == "completed"
        assert data["agent_status"]["scholar"] == "completed"
        assert data["is_complete"] is True


def test_approve_analyzed_task_saves_to_sqlite(client):
    body = {
        "title": "Autonomous Agent Core",
        "description": "Multi-agent task breakdown",
        "priority": "high",
        "status": "todo",
        "due_date": None,
        "subtasks": [
            "Setup Switch hooks",
            "Create schema validators",
            "Add frontend approval dialog",
        ]
    }

    res = client.post("/api/tasks/analyze/approve", json=body)
    assert res.status_code == 201
    created = res.json()
    assert created["id"] is not None
    assert created["title"] == "Autonomous Agent Core"
    assert len(created["subtasks"]) == 3
    subtask_titles = [s["title"] for s in created["subtasks"]]
    assert "Setup Switch hooks" in subtask_titles
    assert "Create schema validators" in subtask_titles

    # Verify task and subtasks persisted in SQLite database via standard GET /api/tasks
    get_res = client.get("/api/tasks")
    assert get_res.status_code == 200
    all_tasks = get_res.json()
    matched = [t for t in all_tasks if t["id"] == created["id"]]
    assert len(matched) == 1
    assert len(matched[0]["subtasks"]) == 3


def test_analyze_task_empty_title_rejected(client):
    res = client.post("/api/tasks/analyze", json={"title": "   "})
    assert res.status_code == 400
    assert "cannot be empty" in res.json()["detail"]


def test_approve_analyzed_task_empty_title_rejected(client):
    res = client.post("/api/tasks/analyze/approve", json={"title": ""})
    assert res.status_code == 400
    assert "cannot be empty" in res.json()["detail"]

