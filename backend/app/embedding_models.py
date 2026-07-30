import re
from dataclasses import dataclass

from app.config import Settings


@dataclass(frozen=True)
class EmbeddingModelSpec:
    id: str
    model_name: str
    dimension: int
    label: str
    recommended_batch_size: int
    cpu_suitable: bool


MODELS = {
    "e5-large": EmbeddingModelSpec(
        "e5-large",
        "intfloat/multilingual-e5-large",
        1024,
        "Multilingual E5 Large (baseline)",
        16,
        True,
    ),
    "granite-311m-r2": EmbeddingModelSpec(
        "granite-311m-r2",
        "ibm-granite/granite-embedding-311m-multilingual-r2",
        768,
        "IBM Granite 311M Multilingual R2",
        64,
        True,
    ),
    "granite-97m-r2": EmbeddingModelSpec(
        "granite-97m-r2",
        "ibm-granite/granite-embedding-97m-multilingual-r2",
        384,
        "IBM Granite 97M Multilingual R2",
        64,
        True,
    ),
}


def model_spec(model_id: str) -> EmbeddingModelSpec:
    try:
        return MODELS[model_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported embedding model: {model_id}") from exc


def collection_name(dataset: str, model_id: str) -> str:
    safe_dataset = re.sub(r"[^a-z0-9_]+", "_", dataset.lower().replace(":", "_")).strip("_")
    safe_model = re.sub(r"[^a-z0-9_]+", "_", model_id.lower()).strip("_")
    return f"ontology_{safe_dataset}_{safe_model}"[:200]


def settings_for_index(
    settings: Settings,
    dataset: str,
    model_id: str,
    device: str | None = None,
    batch_size: int | None = None,
) -> Settings:
    spec = model_spec(model_id)
    return settings.model_copy(
        update={
            "embedding_model": spec.model_name,
            "embedding_device": device or settings.embedding_device,
            "embedding_batch_size": batch_size or spec.recommended_batch_size,
            "milvus_vector_dimension": spec.dimension,
            "milvus_collection": collection_name(dataset, model_id),
        }
    )
