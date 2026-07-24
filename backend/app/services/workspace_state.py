import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUNTIME = Path("/app/data/runtime")


def _read(name: str, default: Any) -> Any:
    path = RUNTIME / name
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError): return default


def _write(name: str, value: Any) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    path = RUNTIME / name; temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def workspace() -> dict[str, str]: return _read("workspace.json", {"active_dataset": "sample", "activated_at": ""})
def active_dataset() -> str: return str(workspace().get("active_dataset", "sample"))
def set_active_dataset(dataset: str) -> None: _write("workspace.json", {"active_dataset": dataset, "activated_at": datetime.now(UTC).isoformat()})
def mapping_profile(dataset: str) -> list[dict[str, object]] | None: return _read("mapping_profiles.json", {}).get(dataset)
def mapping_profiles() -> dict[str, list[dict[str, object]]]: return _read("mapping_profiles.json", {})
def save_mapping_profile(dataset: str, mappings: list[dict[str, object]]) -> None:
    profiles = _read("mapping_profiles.json", {}); profiles[dataset] = mappings; _write("mapping_profiles.json", profiles)
    versions = _read("mapping_versions.json", {})
    history = versions.setdefault(dataset, [])
    history.append({"saved_at": datetime.now(UTC).isoformat(), "mappings": mappings})
    versions[dataset] = history[-20:]
    _write("mapping_versions.json", versions)
