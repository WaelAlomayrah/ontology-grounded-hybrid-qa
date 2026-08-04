"""Atomically rebuild the Police.uk Milvus collection from persisted evidence IDs."""

import argparse
import json
from pathlib import Path

from app.config import get_settings
from app.embedding_models import settings_for_index
from app.services.milvus_service import MilvusService


FIELDS = [
    "id",
    "entity_uri",
    "entity_type",
    "label",
    "text",
    "source",
    "content_hash",
    "embedding",
    "metadata_json",
]


def evidence_ids(path: Path) -> list[str]:
    identifiers: list[str] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            identifier = str(json.loads(line)["id"])
            if identifier in seen:
                raise ValueError(f"Duplicate evidence ID: {identifier}")
            seen.add(identifier)
            identifiers.append(identifier)
    return identifiers


def rebuild(path: Path, batch_size: int) -> tuple[int, int]:
    settings = settings_for_index(get_settings(), "policeuk", "e5-large")
    source = MilvusService(settings)
    before = source.count()
    identifiers = evidence_ids(path)
    temporary_name = f"{settings.milvus_collection}_clean"
    temporary_settings = settings.model_copy(update={"milvus_collection": temporary_name})
    target = MilvusService(temporary_settings)
    target.drop_collection()
    target.ensure_collection(settings.milvus_vector_dimension)

    copied = 0
    for offset in range(0, len(identifiers), batch_size):
        batch = identifiers[offset : offset + batch_size]
        rows = source.client.get(settings.milvus_collection, ids=batch, output_fields=FIELDS)
        returned = {str(row["id"]) for row in rows}
        missing = set(batch) - returned
        if missing:
            target.drop_collection()
            raise RuntimeError(f"Source collection is missing {len(missing)} expected vectors")
        target.client.upsert(temporary_name, rows)
        copied += len(rows)
        if copied % 4096 == 0 or copied == len(identifiers):
            print(f"copied={copied}/{len(identifiers)}", flush=True)

    target.flush()
    if target.count() != len(identifiers):
        target.drop_collection()
        raise RuntimeError("Temporary Police.uk collection count validation failed")

    try:
        source.client.release_collection(settings.milvus_collection)
    except Exception:
        pass
    source.drop_collection()
    source.client.rename_collection(temporary_name, settings.milvus_collection)
    after = source.count()
    if after != len(identifiers):
        raise RuntimeError(f"Final collection contains {after}, expected {len(identifiers)}")
    return before, after


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("/app/data/policeuk/processed/evidence-documents.jsonl"),
    )
    parser.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args()
    before, after = rebuild(args.evidence, args.batch_size)
    print(f"Police.uk collection rebuilt: before={before}, after={after}")


if __name__ == "__main__":
    main()
