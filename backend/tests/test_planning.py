from unittest.mock import patch, AsyncMock
import httpx


def test_planning_session_endpoint(client):
    with patch("app.switch_service.switch_client.fetch_recent_messages", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [
            {
                "id": "p1",
                "username": "nova-anant",
                "message": "### Master Schedule (9:00 AM – 1:30 PM)\n| 09:00 AM – 09:45 AM | 45m | **Java DSA Practice** | Array concepts |\n| 09:45 AM – 09:55 AM | 10m | *Break* | Rest |",
                "created_at": 1793987461000,
            },
            {
                "id": "p2",
                "username": "guardian-anant",
                "message": "Guardian review: schedule looks sound and break intervals are respected.",
                "created_at": 1793987450000,
            },
            {
                "id": "p3",
                "username": "sanant71",
                "message": "@nova-anant Schedule session",
                "created_at": 1793987440000,
            }
        ]

        res = client.get("/api/planning/session")
        assert res.status_code == 200
        data = res.json()
        assert data["room_name"] == "lifeos-planning"
        assert data["status"] == "ready"
        assert data["is_complete"] is True
        assert data["agent_status"]["nova"] == "completed"
        assert data["agent_status"]["guardian"] == "completed"
        assert "Java DSA Practice" in data["nova_proposal"]
        assert "Guardian review" in data["guardian_review"]
        assert len(data["proposed_tasks"]) == 1
        assert data["proposed_tasks"][0]["title"] == "Java DSA Practice"


def test_planning_session_switch_down(client):
    # Reset cached session
    import app.routes
    app.routes._cached_session = None

    with patch("app.switch_service.switch_client.fetch_recent_messages", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = httpx.ConnectError("Connection refused")

        res = client.get("/api/planning/session")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "disconnected"
        assert data["is_complete"] is False
        assert data["agent_status"]["nova"] == "failed"
        assert "Cannot reach Switch" in data["error_message"]
        assert "Docker" in data["restart_instructions"]


def test_planning_session_fallback_preserves_data(client):
    import app.routes
    app.routes._cached_session = {
        "room_name": "lifeos-planning",
        "channel_id": "bk7165is4bb6ugqtr3fcer1hur",
        "user_request": "Sample plan",
        "nova_proposal": "Cached proposal",
        "guardian_review": "Cached review",
        "proposed_tasks": [{"title": "Cached Task", "description": "", "priority": "high", "status": "todo"}],
        "agent_responses": [],
    }

    with patch("app.switch_service.switch_client.fetch_recent_messages", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = httpx.ConnectError("Connection refused")

        res = client.get("/api/planning/session")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "disconnected"
        assert data["is_fallback"] is True
        assert data["nova_proposal"] == "Cached proposal"
        assert len(data["proposed_tasks"]) == 1


def test_planning_health_endpoint_up(client):
    with patch("app.switch_service.switch_client.health_check", new_callable=AsyncMock) as mock_health:
        mock_health.return_value = {
            "switch_available": True,
            "mattermost_available": True,
            "channel_accessible": True,
            "agents_configured": ["nova", "scholar", "builder", "planner", "guardian"],
            "error_message": None,
            "restart_instructions": None,
        }

        res = client.get("/api/planning/health")
        assert res.status_code == 200
        data = res.json()
        assert data["switch_available"] is True
        assert data["mattermost_available"] is True
        assert data["channel_accessible"] is True


def test_planning_health_endpoint_down(client):
    with patch("app.switch_service.switch_client.health_check", new_callable=AsyncMock) as mock_health:
        mock_health.return_value = {
            "switch_available": False,
            "mattermost_available": False,
            "channel_accessible": False,
            "agents_configured": ["nova", "scholar", "builder", "planner", "guardian"],
            "error_message": "Connection refused",
            "restart_instructions": "Check if Docker is running",
        }

        res = client.get("/api/planning/health")
        assert res.status_code == 200
        data = res.json()
        assert data["switch_available"] is False
        assert "Docker" in data["restart_instructions"]


def test_planning_approve_saves_to_sqlite(client):
    body = {
        "tasks": [
            {
                "title": "Approved Switch Task 1",
                "description": "09:00-09:45 Practice",
                "priority": "high",
                "status": "todo",
            },
            {
                "title": "Approved Switch Task 2",
                "description": "09:55-10:55 Implementation",
                "priority": "medium",
                "status": "todo",
            }
        ]
    }
    res = client.post("/api/planning/approve", json=body)
    assert res.status_code == 200
    created = res.json()
    assert len(created) == 2
    assert created[0]["title"] == "Approved Switch Task 1"

    # Verify tasks are in SQLite via standard GET /api/tasks
    get_res = client.get("/api/tasks")
    assert get_res.status_code == 200
    titles = [t["title"] for t in get_res.json()]
    assert "Approved Switch Task 1" in titles
    assert "Approved Switch Task 2" in titles


def test_planning_approve_empty_rejected(client):
    res = client.post("/api/planning/approve", json={"tasks": []})
    assert res.status_code == 400
    assert "No tasks provided" in res.json()["detail"]


def test_planning_submit_empty_rejected(client):
    res = client.post("/api/planning/submit", json={"request": "   "})
    assert res.status_code == 400
    assert "cannot be empty" in res.json()["detail"]
