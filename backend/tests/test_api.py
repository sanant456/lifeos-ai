def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_task(client):
    r = client.post("/api/tasks", json={"title": "Test task", "priority": "high"})
    assert r.status_code == 201
    data = r.json()
    assert data["title"] == "Test task"
    assert data["priority"] == "high"
    assert data["status"] == "todo"
    assert "id" in data


def test_list_tasks(client):
    client.post("/api/tasks", json={"title": "Task 1"})
    client.post("/api/tasks", json={"title": "Task 2"})
    r = client.get("/api/tasks")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_update_task(client):
    r = client.post("/api/tasks", json={"title": "Old title"})
    task_id = r.json()["id"]
    r = client.patch(f"/api/tasks/{task_id}", json={"title": "New title", "status": "done"})
    assert r.status_code == 200
    assert r.json()["title"] == "New title"
    assert r.json()["status"] == "done"


def test_update_task_not_found(client):
    r = client.patch("/api/tasks/999", json={"title": "Nope"})
    assert r.status_code == 404


def test_delete_task(client):
    r = client.post("/api/tasks", json={"title": "To delete"})
    task_id = r.json()["id"]
    r = client.delete(f"/api/tasks/{task_id}")
    assert r.status_code == 204
    r = client.get("/api/tasks")
    assert len(r.json()) == 0


def test_delete_task_not_found(client):
    r = client.delete("/api/tasks/999")
    assert r.status_code == 404
