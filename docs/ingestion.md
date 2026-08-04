# Ingestion

## Configurable vector indexes

The Modeling page lets an administrator choose the dataset, embedding model,
processor, batch size, and ingestion scope. Vector collections are isolated by
dataset and model:

`ontology_<dataset>_<model>`

Supported model profiles are:

- `e5-large` — the 1024-dimensional multilingual E5 baseline.
- `granite-311m-r2` — the 768-dimensional quality-focused IBM Granite model.
- `granite-97m-r2` — the 384-dimensional CPU-efficiency profile.

Base `compose.yaml` remains CPU-only. Start the optional NVIDIA configuration
with:

`docker compose -f compose.yaml -f compose.gpu.yaml up -d --build`

The GPU image pins a CUDA 12.6-compatible PyTorch build. The CPU image pins the
matching CPU-only build.

## Incremental and batched operation

Each searchable document receives a SHA-256 hash of its normalized searchable
text. Append ingestion reads the hashes already stored in the selected Milvus
collection and embeds only new or changed records. Unchanged records are
reported as reused/skipped.

Embeddings are generated and upserted progressively in selectable batches of
16, 32, 64, or 128. Job progress advances after each completed batch, and a
failed run can be safely restarted because IDs and hashes are deterministic.

Available scopes:

- **Update changed vectors** — idempotent graph append plus incremental vectors.
- **Graph only** — update Fuseki without touching Milvus.
- **Vectors only** — update the selected Milvus index without touching Fuseki.
- **Full graph and vector rebuild** — clear and rebuild both selected layers.

## Precomputed vectors

Enable **Save reusable vectors** during ingestion to write:

`<dataset>/precomputed_vectors/<model-id>.jsonl`

Each row contains the deterministic document ID, content hash, and embedding.
Subsequent ingestion validates the hash and vector dimension before reuse.
Dataset ZIP export includes these files, allowing another compatible deployment
to load vectors without recomputing them. Generated vector caches are ignored by
Git and must not be committed.

## Evaluation selection

The Evaluation page lists datasets with question sets and all configured
embedding models. A dataset/model pair becomes selectable after its isolated
Milvus index exists. The selected dataset must also be the active Fuseki graph
so graph, vector, hybrid, and ontology comparisons use the same evidence.

The loader discovers external formats, maps tolerant CSV columns, merges RDF graphs, serializes one upload to Fuseki, builds descriptive entity passages, adds E5 passage prefixes, and deterministically upserts Milvus documents. Reset clears graph data and replaces vectors from that source. Reports contain counts, elapsed seconds, failures, skips, warnings, and errors.

## Police.uk and ONS

The `policeuk` adapter uses the same graph/document contract and the same
Fuseki/Milvus writers as existing datasets:

```bash
docker compose --profile tools run --rm data-loader --dataset policeuk \
  --reset --download --load-graph --load-vectors \
  --force "Thames Valley Police" --months 12

docker compose --profile tools run --rm data-loader --dataset policeuk \
  --reset --no-download --load-graph --load-vectors \
  --force "Thames Valley Police" --months 12
```

ZIP contents are inspected and filtered by force, available month, and record
type. Exact Crime ID and LSOA-code joins are enforced. See
[Police.uk dataset](policeuk-dataset.md).
# Arabic Enterprise full-folder ingestion

`Arabic_enterprise_dataset` is a native prepared dataset. Its ingestion job:

1. parses and loads `knowledge_graph.ttl` into Fuseki;
2. reads and validates up to 5,000 UTF-8 records from `documents.jsonl`;
3. creates semantic records for graph entities and full Arabic document text;
4. upserts the resulting vectors into Milvus under source `arabic_enterprise`; and
5. activates `evaluation_questions_ar.json` for evaluation after a successful job.

In the frontend, open **Modeling → Describe data**, select **Arabic enterprise dataset**, choose append or reset, and select **Ingest complete Arabic dataset**. Reset replaces the current Fuseki graph; append retains existing graph data.

The equivalent authenticated API request is:

```http
POST /api/v1/ingestion/jobs
Content-Type: application/json

{
  "dataset": "arabic_enterprise",
  "mode": "append",
  "load_graph": true,
  "load_vectors": true
}
```

## Dataset ZIP export

Labeler, analyst, and administrator accounts can export source datasets from **Operations → Available datasets → Export ZIP** or:

```http
GET /api/v1/ingestion/datasets/Arabic_enterprise_dataset/export
```

The ZIP preserves the dataset folder and contains source tables, documents, RDF/OWL files, questions, metadata, and its README. Runtime state and evaluation-result folders are not exportable. Export is limited to 10,000 files and 250 MB.
