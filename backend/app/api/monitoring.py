import asyncio
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends

from app.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])
NETWORK_SAMPLES: dict[str, tuple[float, int, int]] = {}

SERVICE_PROBES = {
    "frontend": "http://frontend:8080/healthz",
    "backend": "http://backend:8000/health",
    "fuseki": "http://fuseki:3030/$/ping",
    "etcd": "http://etcd:2379/health",
    "minio": "http://minio:9000/minio/health/live",
    "milvus": "http://milvus:9091/healthz",
    "attu": "http://attu:3000/",
    "ollama": "http://ollama:11434/api/tags",
    "prometheus": "http://prometheus:9090/-/healthy",
    "grafana": "http://grafana:3000/api/health",
    "cadvisor": "http://cadvisor:8080/healthz",
}


async def _query(client: httpx.AsyncClient, base_url: str, expression: str) -> list[dict[str, Any]]:
    response = await client.get(f"{base_url}/api/v1/query", params={"query": expression})
    response.raise_for_status()
    return response.json().get("data", {}).get("result", [])


async def _probe(client: httpx.AsyncClient, name: str, url: str) -> dict[str, object]:
    try:
        response = await client.get(url)
        return {"name": name, "running": response.status_code < 500}
    except httpx.HTTPError:
        return {"name": name, "running": False}


def _container_load(container: dict[str, Any], stats: dict[str, Any], probe: dict[str, object] | None) -> dict[str, object]:
    cpu, previous = stats.get("cpu_stats", {}), stats.get("precpu_stats", {})
    cpu_delta = float(cpu.get("cpu_usage", {}).get("total_usage", 0)) - float(previous.get("cpu_usage", {}).get("total_usage", 0))
    system_delta = float(cpu.get("system_cpu_usage", 0)) - float(previous.get("system_cpu_usage", 0))
    cpus = int(cpu.get("online_cpus") or len(cpu.get("cpu_usage", {}).get("percpu_usage", [])) or 1)
    cpu_percent = max(0.0, cpu_delta / system_delta * cpus * 100) if system_delta > 0 else 0.0
    memory = stats.get("memory_stats", {})
    memory_usage = max(0, int(memory.get("usage", 0)) - int(memory.get("stats", {}).get("inactive_file", 0)))
    networks = stats.get("networks", {}).values()
    received = sum(int(item.get("rx_bytes", 0)) for item in networks)
    transmitted = sum(int(item.get("tx_bytes", 0)) for item in stats.get("networks", {}).values())
    container_id = str(container.get("Id", ""))
    now, receive_bps, transmit_bps = time.monotonic(), 0.0, 0.0
    if container_id in NETWORK_SAMPLES:
        sampled_at, old_received, old_transmitted = NETWORK_SAMPLES[container_id]
        elapsed = max(now - sampled_at, 0.001)
        receive_bps = max(0.0, (received - old_received) / elapsed)
        transmit_bps = max(0.0, (transmitted - old_transmitted) / elapsed)
    NETWORK_SAMPLES[container_id] = (now, received, transmitted)
    labels = container.get("Labels", {})
    state, status = str(container.get("State", "unknown")), str(container.get("Status", ""))
    health = "healthy" if "(healthy)" in status else "unhealthy" if "(unhealthy)" in status else "none"
    engine_running = state == "running"
    return {
        "name": str(container.get("Names", [container_id[:12]])[0]).lstrip("/"),
        "service": labels.get("com.docker.compose.service", "unknown"),
        "state": state,
        "status": status,
        "health": health,
        "running": engine_running and (bool(probe.get("running")) if probe else True),
        "cpu_percent": round(cpu_percent, 2),
        "memory_bytes": memory_usage,
        "memory_limit_bytes": int(memory.get("limit", 0)),
        "network_receive_bps": round(receive_bps, 2),
        "network_transmit_bps": round(transmit_bps, 2),
        "network_receive_bytes": received,
        "network_transmit_bytes": transmitted,
    }


async def _docker_containers(client: httpx.AsyncClient, base_url: str, probes: list[dict[str, object]]) -> list[dict[str, object]]:
    filters = '{"label":["com.docker.compose.project=ontology-ai-pilot"]}'
    response = await client.get(f"{base_url}/containers/json", params={"all": "true", "filters": filters})
    response.raise_for_status()
    containers: list[dict[str, Any]] = response.json()
    stats_responses = await asyncio.gather(*(client.get(f"{base_url}/containers/{item['Id']}/stats", params={"stream": "false"}) for item in containers))
    by_service = {str(item["name"]): item for item in probes}
    return [_container_load(container, response.json(), by_service.get(str(container.get("Labels", {}).get("com.docker.compose.service", "")))) for container, response in zip(containers, stats_responses, strict=True) if response.status_code == 200]


@router.get("/overview")
async def overview(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    expressions = {
        "cpu_cores": 'sum by (id) (rate(container_cpu_usage_seconds_total{id="/docker"}[2m]))',
        "memory_bytes": 'sum by (id) (container_memory_working_set_bytes{id="/docker"})',
        "network_receive_bps": 'sum(rate(container_network_receive_bytes_total{id="/docker"}[2m]))',
        "network_transmit_bps": 'sum(rate(container_network_transmit_bytes_total{id="/docker"}[2m]))',
    }
    async with httpx.AsyncClient(timeout=8) as client:
        probes = await asyncio.gather(*(_probe(client, name, url) for name, url in SERVICE_PROBES.items()))
        try:
            results = await asyncio.gather(*(_query(client, settings.prometheus_base_url, query) for query in expressions.values()))
            targets = await _query(client, settings.prometheus_base_url, "up")
            available = True
        except (httpx.HTTPError, ValueError):
            results, targets, available = [[] for _ in expressions], [], False
        try:
            docker_containers = await _docker_containers(client, settings.docker_proxy_base_url, probes)
        except (httpx.HTTPError, ValueError, KeyError):
            docker_containers = probes
    containers = {str(item["name"]): item for item in docker_containers}
    runtime: dict[str, object] = {"name": "docker runtime", "running": available}
    for metric_name, rows in zip(expressions, results, strict=True):
        if rows:
            runtime[metric_name] = round(float(rows[0]["value"][1]), 4)
    containers["docker runtime"] = runtime
    target_rows = [{"job": row.get("metric", {}).get("job", "unknown"), "instance": row.get("metric", {}).get("instance", ""), "up": row.get("value", [0, "0"])[1] == "1"} for row in targets]
    return {"available": available, "containers": list(containers.values()), "targets": target_rows, "load_scope": "Per-container state and resource usage from the read-only Docker API; aggregate runtime load from cAdvisor."}
