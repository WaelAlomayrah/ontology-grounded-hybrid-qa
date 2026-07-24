import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark=pytest.mark.integration
@pytest.mark.skipif(not os.getenv("RUN_INTEGRATION"),reason="Set RUN_INTEGRATION=1 with Compose running")
def test_health_and_stats():
    client=TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/graph/stats").status_code == 200

