from fastapi.testclient import TestClient

from app.main import app

client=TestClient(app)
def test_root_and_version():
    assert client.get("/").status_code == 200
    assert client.get("/version").json()["version"] == "0.1.0"
def test_validation_error(): assert client.post("/api/v1/chat",json={"question":""}).status_code == 422
def test_query_plan(): assert client.post("/api/v1/query-plan",json={"question":"Which vendor supplies Project Atlas?"}).status_code == 200
def test_reset_authorization(): assert client.post("/api/v1/ingestion/reset").status_code == 403

