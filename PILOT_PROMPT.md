# Build a Complete Ontology-Driven AI Pilot

Act as the principal software architect, senior Python engineer, frontend engineer, data engineer, DevOps engineer, and test engineer for this project.

Build a complete, runnable, documented proof of concept for an ontology-driven AI question-answering system.

Do not merely produce an architecture proposal or code snippets. Create the actual project files, application code, Docker configuration, tests, sample data, initialization scripts, and documentation.

Work autonomously. Inspect the repository before making changes. If the repository is empty, initialize the full project. Do not stop after creating scaffolding. Continue until the pilot can be started and its core workflow can be tested.

Do not ask me to make routine implementation decisions. Use the defaults and constraints in this prompt. Only stop when blocked by missing external assets that cannot reasonably be replaced with a sample or mock implementation.

---

# 1. Project objective

Build a single-machine master’s graduation-project pilot that answers natural-language questions using:

1. An RDF/OWL ontology and knowledge graph.
2. Vector similarity retrieval.
3. A local large language model.
4. Hybrid graph and vector retrieval.
5. Traceable answers showing the evidence used.
6. A web-based chat and graph-exploration interface.
7. Basic monitoring and evaluation.

The initial target dataset is:

```text
KG2QA_ontology_dataset
```

The application must also include a small built-in organizational demonstration dataset so the system remains runnable when the external KG2QA dataset is not present.

The project is a proof of concept, not a production platform. Favor correctness, clarity, reproducibility, modularity, and academic evaluation over unnecessary infrastructure complexity.

---

# 2. Required technology stack

Use the following stack.

## Backend

* Python 3.12
* FastAPI
* Uvicorn
* Pydantic v2
* httpx
* RDFLib
* SPARQLWrapper or direct SPARQL over HTTP
* pymilvus
* sentence-transformers
* pandas
* python-multipart
* prometheus-fastapi-instrumentator
* structured Python logging
* pytest
* ruff
* mypy where practical

## Ontology and graph storage

* Apache Jena Fuseki
* RDF, RDFS, OWL and SPARQL
* Fuseki is the authoritative ontology and graph store.

## Vector search

* Milvus standalone
* etcd
* MinIO
* Attu

## Local AI

* Ollama
* Default model configurable through environment variables
* Default model:

```text
qwen2.5:7b
```

## Embeddings

Default:

```text
intfloat/multilingual-e5-large
```

The embedding model must be configurable through environment variables.

Support CPU execution by default.

Add optional GPU configuration through a Compose override file instead of requiring a GPU in the base Compose file.

## Frontend

Use:

* React
* TypeScript
* Vite
* React Router if needed
* TanStack Query
* Cytoscape.js for graph visualization
* A lightweight CSS approach such as plain CSS modules

Do not add a large frontend design system unless needed.

## Monitoring

* Prometheus
* Grafana
* cAdvisor
* FastAPI `/metrics`

## Deployment

* Docker
* Docker Compose
* No Kubernetes
* No message broker
* No microservice framework
* No external cloud APIs

---

# 3. Required system architecture

Implement the following communication flow:

```text
User
  |
  v
React frontend
  |
  | HTTP/JSON
  v
FastAPI backend
  |
  +---------------------------+
  |                           |
  | SPARQL over HTTP          | Milvus gRPC
  v                           v
Apache Jena Fuseki         Milvus
  |                           |
  | graph facts               | vector matches
  +-------------+-------------+
                |
                v
         Retrieval fusion
                |
                v
      Prompt/context builder
                |
                | Ollama HTTP API
                v
             Ollama
                |
                v
 Answer + sources + graph paths
                |
                v
             Frontend
```

Fuseki must store:

* Ontology classes
* Object properties
* Data properties
* Entities
* RDF triples
* Entity relationships

Milvus must store embeddings for:

* Entities
* Entity descriptions
* Optional QA examples
* Optional graph-fact text representations

FastAPI must orchestrate all communication. The frontend must never connect directly to Fuseki, Milvus, MinIO, etcd, or Ollama.

---

# 4. Repository structure

Create this structure or a similarly clean structure:

```text
ontology-ai-pilot/
├── AGENTS.md
├── README.md
├── compose.yaml
├── compose.gpu.yaml
├── .env.example
├── .gitignore
├── Makefile
├── LICENSE
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── scripts/
│   │   ├── wait_for_services.py
│   │   └── download_embedding_model.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── logging_config.py
│   │   ├── dependencies.py
│   │   ├── models/
│   │   │   ├── api.py
│   │   │   ├── retrieval.py
│   │   │   └── graph.py
│   │   ├── api/
│   │   │   ├── health.py
│   │   │   ├── chat.py
│   │   │   ├── graph.py
│   │   │   ├── ingestion.py
│   │   │   └── evaluation.py
│   │   ├── services/
│   │   │   ├── fuseki_service.py
│   │   │   ├── milvus_service.py
│   │   │   ├── embedding_service.py
│   │   │   ├── ollama_service.py
│   │   │   └── ontology_service.py
│   │   ├── retrieval/
│   │   │   ├── graph_retriever.py
│   │   │   ├── vector_retriever.py
│   │   │   ├── hybrid_retriever.py
│   │   │   ├── intent_classifier.py
│   │   │   └── context_builder.py
│   │   ├── ingestion/
│   │   │   ├── loader.py
│   │   │   ├── kg2qa_loader.py
│   │   │   ├── sample_loader.py
│   │   │   ├── rdf_loader.py
│   │   │   ├── csv_loader.py
│   │   │   └── mappings.py
│   │   ├── evaluation/
│   │   │   ├── runner.py
│   │   │   ├── metrics.py
│   │   │   └── baselines.py
│   │   └── prompts/
│   │       ├── answer_system.txt
│   │       ├── query_planner.txt
│   │       └── entity_extraction.txt
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── fixtures/
│
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       ├── components/
│       ├── pages/
│       ├── types/
│       └── styles/
│
├── fuseki/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── configuration/
│   │   └── ontology.ttl
│   └── init/
│       └── README.md
│
├── data/
│   ├── .gitkeep
│   ├── sample/
│   │   ├── ontology.ttl
│   │   ├── departments.csv
│   │   ├── employees.csv
│   │   ├── projects.csv
│   │   ├── systems.csv
│   │   ├── project_assignments.csv
│   │   └── evaluation_questions.json
│   └── KG2QA_ontology_dataset/
│       └── README.md
│
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml
│   └── grafana/
│       ├── provisioning/
│       │   ├── datasources/
│       │   │   └── prometheus.yml
│       │   └── dashboards/
│       │       └── dashboards.yml
│       └── dashboards/
│           └── ontology-pilot.json
│
├── scripts/
│   ├── bootstrap.sh
│   ├── bootstrap.ps1
│   ├── ingest.sh
│   ├── ingest.ps1
│   ├── smoke_test.sh
│   ├── smoke_test.ps1
│   ├── evaluate.sh
│   └── backup.sh
│
└── docs/
    ├── architecture.md
    ├── api.md
    ├── ontology.md
    ├── ingestion.md
    ├── evaluation.md
    ├── troubleshooting.md
    └── diagrams/
        └── architecture.mmd
```

Avoid empty placeholder modules. Every source file should have a clear purpose and useful implementation.

---

# 5. Docker Compose requirements

Create a valid `compose.yaml` using a modern Compose specification. Do not include the obsolete top-level `version` field.

Define these services:

```text
frontend
backend
fuseki
etcd
minio
milvus
attu
ollama
ollama-init
prometheus
grafana
cadvisor
data-loader
```

Use the service name `milvus`, not `standalone`, so application configuration is obvious.

## Base Compose behavior

The base Compose file must run on a CPU-only Linux Docker host.

Do not require NVIDIA runtime in `compose.yaml`.

Create `compose.gpu.yaml` that adds NVIDIA GPU access to Ollama and, where useful, the backend embedding service.

Users should start GPU mode with:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
```

## Health checks

Add meaningful health checks for:

* Backend
* Frontend
* Fuseki
* etcd
* MinIO
* Milvus
* Ollama
* Prometheus
* Grafana

Use conditional `depends_on` where supported.

Do not rely only on container startup order.

## Networking

Use three networks:

```text
app-network
data-network
monitoring-network
```

Communication rules:

* Frontend communicates only with backend.
* Backend communicates with Fuseki, Milvus and Ollama.
* Milvus communicates with etcd and MinIO.
* Prometheus communicates with monitored services.
* Grafana communicates with Prometheus.

Expose only the ports useful to a developer running the pilot.

Use configurable host ports in `.env.example`.

## Persistence

Create named volumes for:

* Fuseki data
* etcd data
* MinIO data
* Milvus data
* Ollama models
* Hugging Face models
* Grafana data
* Prometheus data

## Service images

Use stable, mutually compatible image versions. Do not use `latest` except when no practical stable tag is available.

Document the chosen versions in the README.

## Secrets

Do not hardcode real passwords.

Provide development defaults only in `.env.example`, clearly marked as insecure for production.

Ensure `.env` is ignored by Git.

---

# 6. Configuration

Implement configuration through environment variables using `pydantic-settings`.

Include at least:

```text
APP_ENV
LOG_LEVEL
BACKEND_PORT
FRONTEND_PORT
CORS_ORIGINS

FUSEKI_BASE_URL
FUSEKI_DATASET
FUSEKI_USER
FUSEKI_PASSWORD

MILVUS_HOST
MILVUS_PORT
MILVUS_COLLECTION
MILVUS_VECTOR_DIMENSION
MILVUS_METRIC_TYPE

OLLAMA_BASE_URL
OLLAMA_MODEL
OLLAMA_TIMEOUT_SECONDS

EMBEDDING_MODEL
EMBEDDING_DEVICE
EMBEDDING_BATCH_SIZE
EMBEDDING_NORMALIZE

DATASET_PATH
ONTOLOGY_FILE

VECTOR_TOP_K
GRAPH_RESULT_LIMIT
HYBRID_VECTOR_WEIGHT
HYBRID_GRAPH_WEIGHT
MAX_CONTEXT_ITEMS
MAX_CONTEXT_CHARACTERS

ENABLE_LLM_QUERY_PLANNER
ENABLE_SAMPLE_FALLBACK
```

Validate configuration at application startup.

Never log passwords or secrets.

---

# 7. Built-in organizational sample dataset

Create a small but meaningful structured organizational dataset.

Include these entity types:

* Department
* Employee
* Project
* InformationSystem
* Vendor
* Location

Include these relationships:

```text
Employee worksIn Department
Employee manages Department
Employee assignedTo Project
Department owns InformationSystem
Project sponsoredBy Department
Project usesSystem InformationSystem
InformationSystem suppliedBy Vendor
Employee locatedAt Location
Department locatedAt Location
```

Create enough records to support multi-hop questions. Aim for approximately:

* 5 departments
* 15 employees
* 8 projects
* 6 systems
* 5 vendors
* 4 locations
* 25 or more relationships

Use fictional, non-sensitive data.

Create an RDF/OWL ontology in Turtle format defining:

* Classes
* Object properties
* Data properties
* Labels
* Domains
* Ranges
* At least a few inverse properties
* At least one class hierarchy

For example:

```text
Person
  └── Employee

OrganizationalUnit
  └── Department
```

Generate RDF instances from the CSV files during ingestion.

Do not manually duplicate every instance in the ontology file.

---

# 8. KG2QA ingestion support

Support a dataset mounted at:

```text
/app/data/KG2QA_ontology_dataset
```

The loader must detect available files rather than assuming that every possible filename exists.

Support these cases where present:

* `.rdf`
* `.ttl`
* `.owl`
* Entity CSV files
* Relationship CSV files
* QA JSON or CSV files
* Text descriptions

Implement tolerant column matching. For example, detect common alternatives such as:

```text
source
source_id
subject
head
from

target
target_id
object
tail
to

relation
predicate
relationship
type
```

If the external dataset is absent:

* Do not crash the entire application.
* Log a clear warning.
* Load the built-in organizational sample dataset.
* Expose dataset status through the health or status endpoint.

The loader must provide an ingestion report containing:

* Dataset selected
* RDF files loaded
* Entities processed
* Relationships processed
* Vectors generated
* Failed records
* Skipped records
* Elapsed time
* Errors and warnings

Make ingestion idempotent.

Support reset and append modes.

---

# 9. Fuseki implementation

Create or configure a persistent Fuseki dataset named:

```text
ontology
```

Expose standard endpoints internally:

```text
/ontology/query
/ontology/update
/ontology/data
```

Implement a `FusekiService` with methods such as:

```python
health_check()
query_select()
query_ask()
query_construct()
execute_update()
upload_rdf()
delete_all()
get_entity()
get_neighbors()
search_labels()
get_shortest_explanatory_paths()
```

Use parameterized query construction or strict escaping.

Never concatenate untrusted raw user text directly into SPARQL.

Implement reusable SPARQL queries for:

* Entity lookup by label
* Type lookup
* Immediate neighbors
* Relationships between selected entities
* Multi-hop traversal with a configurable depth
* Counts grouped by class
* Search by case-insensitive label substring

Enforce result limits.

Return graph results in a frontend-friendly structure:

```json
{
  "nodes": [
    {
      "id": "uri",
      "label": "Human-readable label",
      "type": "Class name",
      "properties": {}
    }
  ],
  "edges": [
    {
      "id": "stable-id",
      "source": "source-uri",
      "target": "target-uri",
      "predicate": "predicate-uri",
      "label": "relationship label"
    }
  ]
}
```

---

# 10. Milvus implementation

Create a Milvus collection whose schema supports:

```text
id
entity_uri
entity_type
label
text
source
embedding
metadata_json
```

Use appropriate maximum lengths.

The primary key may be a generated string or integer, but it must be deterministic enough to support idempotent upserts.

Use cosine similarity.

The vector dimension must be derived from the embedding model at initialization and checked against configuration.

Do not silently continue when dimensions differ.

Create the collection and index automatically if absent.

Implement a `MilvusService` with:

```python
health_check()
ensure_collection()
upsert_documents()
search()
delete_by_source()
count()
drop_collection()
```

Return similarity scores and metadata.

Batch inserts to avoid loading everything into memory.

---

# 11. Embedding implementation

Implement an `EmbeddingService` using `sentence-transformers`.

Requirements:

* Lazy model initialization
* Configurable device
* Configurable batch size
* Normalized embeddings
* Query and passage prefixes compatible with E5 models

For E5-family models use:

```text
query: <question>
passage: <entity or graph text>
```

Create vector text from useful combinations such as:

```text
Entity: Finance Department
Type: Department
Description: Responsible for budgeting and financial oversight.
Relationships: sponsors Project Atlas; owns Budget Management System.
```

Cache or persist the model through a Docker volume.

Provide a clear offline-mode section in the README explaining that the embedding model and Ollama model must be downloaded before moving the deployment into an air-gapped network.

---

# 12. Natural-language retrieval pipeline

Implement a transparent hybrid pipeline.

## Step 1: Normalize the question

* Trim whitespace
* Reject empty input
* Enforce a reasonable maximum length

## Step 2: Detect question intent

Use deterministic rules first.

Classify into one or more of:

```text
entity_lookup
relationship_lookup
aggregation
multi_hop
descriptive
unknown
```

The system must work even when the LLM query planner is disabled.

## Step 3: Identify candidate entities

Use both:

* Fuseki label search
* Milvus semantic search

Merge and deduplicate candidates.

## Step 4: Graph retrieval

Retrieve:

* Entity facts
* Neighboring entities
* Relevant relationships
* Short explanatory graph paths
* Limited multi-hop context

Do not allow unbounded traversal.

## Step 5: Vector retrieval

Retrieve top semantic matches from Milvus.

## Step 6: Hybrid fusion

Use a simple, explainable fusion strategy.

For example:

```text
hybrid_score =
    vector_weight * normalized_vector_score
    + graph_weight * graph_relevance_score
```

Use configurable weights.

Document the formula.

A more advanced rank-fusion method may be added, but do not hide the logic.

## Step 7: Context construction

Build structured context with sections:

```text
Identified entities
Graph facts
Relationship paths
Semantic matches
Dataset/source metadata
```

Deduplicate repeated facts.

Enforce maximum context items and characters.

## Step 8: LLM answer generation

Send the context and question to Ollama.

The system prompt must require the model to:

* Answer only from supplied evidence.
* State when evidence is insufficient.
* Avoid inventing entities or relationships.
* Mention the evidence identifiers.
* Keep the answer concise.
* Explain relevant relationship paths.
* Distinguish direct facts from inferred conclusions.

## Step 9: Structured response

Return:

```json
{
  "question": "...",
  "answer": "...",
  "answer_status": "answered",
  "confidence": 0.82,
  "intent": ["multi_hop"],
  "entities": [],
  "graph": {
    "nodes": [],
    "edges": [],
    "paths": []
  },
  "sources": [],
  "retrieval": {
    "vector_results": [],
    "graph_facts": [],
    "timings_ms": {}
  },
  "warnings": []
}
```

Allowed answer status values:

```text
answered
partial
insufficient_evidence
error
```

Confidence may be a transparent heuristic. Clearly document that it is not a calibrated probability.

---

# 13. Query planner safety

Optionally use the LLM to propose a structured retrieval plan, but do not permit arbitrary generated SPARQL execution by default.

The planner should produce validated JSON such as:

```json
{
  "intent": ["multi_hop"],
  "entity_mentions": ["Project Atlas"],
  "relationship_hints": ["sponsored by", "uses system"],
  "requested_fields": ["department", "vendor"],
  "max_hops": 3
}
```

Validate the result with Pydantic.

Use this plan to select pre-written safe SPARQL templates.

Do not execute raw SPARQL emitted by the LLM unless an explicitly disabled-by-default development flag is enabled.

---

# 14. API requirements

Create these endpoints.

## General

```text
GET  /
GET  /health
GET  /ready
GET  /version
GET  /metrics
```

## Chat and retrieval

```text
POST /api/v1/chat
POST /api/v1/retrieve
POST /api/v1/query-plan
```

## Graph

```text
GET  /api/v1/graph/classes
GET  /api/v1/graph/entity
GET  /api/v1/graph/neighbors
GET  /api/v1/graph/search
POST /api/v1/graph/path
GET  /api/v1/graph/stats
```

## Ingestion

```text
GET  /api/v1/ingestion/status
POST /api/v1/ingestion/sample
POST /api/v1/ingestion/kg2qa
POST /api/v1/ingestion/reset
```

Protect reset operations with a simple development admin token read from the environment.

Do not implement a full identity platform for this pilot.

## Evaluation

```text
POST /api/v1/evaluation/run
GET  /api/v1/evaluation/results
```

Generate OpenAPI documentation automatically.

Use consistent error responses:

```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human-readable message",
    "details": {}
  }
}
```

---

# 15. Frontend requirements

Build a clean pilot interface with the following pages.

## Chat page

Include:

* Question input
* Submit button
* Loading state
* Suggested sample questions
* Answer text
* Confidence indicator
* Answer-status indicator
* Evidence/source list
* Retrieval timing
* Expandable raw graph facts
* Button to show the supporting graph

Suggested questions should come from the backend or a configuration file.

Examples:

```text
Which department sponsors Project Atlas?
Which vendor supplies the system used by Project Atlas?
Who manages the department that owns the Case Management System?
Which projects are connected to employees located in Riyadh?
What systems are owned by the Finance Department?
```

## Graph explorer

Use Cytoscape.js.

Include:

* Search by label
* Node selection
* Neighbor expansion
* Node type filters
* Relationship label display
* Fit-to-screen button
* Reset graph button
* Entity details panel

## Dataset and system status page

Show:

* Active dataset
* Fuseki status
* Milvus status
* Ollama status
* Graph entity count
* Triple count where available
* Vector count
* Selected models
* Latest ingestion report

## Evaluation page

Show:

* Evaluation run button
* Number of questions
* Baseline metrics
* Hybrid metrics
* Comparison table
* Latency summary
* Downloadable JSON result

The frontend must handle backend errors clearly.

Do not place backend service credentials in frontend code.

Configure the production frontend container to serve static files through Nginx and proxy `/api` to the backend internally, or otherwise provide a reliable production configuration.

---

# 16. Evaluation framework

The academic value of this pilot depends on comparison and measurement.

Implement three retrieval modes:

```text
vector_only
graph_only
hybrid
```

Allow the mode to be selected through the API.

Create an evaluation question format:

```json
{
  "id": "q001",
  "question": "Which vendor supplies the system used by Project Atlas?",
  "expected_entities": [
    "Project Atlas",
    "Document Management System",
    "Alpha Technologies"
  ],
  "expected_answer_keywords": [
    "Alpha Technologies"
  ],
  "expected_path": [
    "Project Atlas",
    "usesSystem",
    "Document Management System",
    "suppliedBy",
    "Alpha Technologies"
  ],
  "category": "multi_hop"
}
```

Implement at least these metrics:

* Exact match where appropriate
* Token-level F1
* Expected keyword coverage
* Expected entity recall
* Graph-path recall
* Evidence precision
* Unsupported-claim heuristic
* End-to-end latency
* Retrieval latency
* Generation latency
* Answerable versus insufficient-evidence accuracy

Do not pretend an LLM-based subjective evaluator is objectively correct.

The main deterministic evaluation must run without an external judge model.

Produce JSON and CSV output.

Compare:

```text
vector_only versus graph_only versus hybrid
```

Include at least 15 evaluation questions for the built-in sample dataset:

* 4 direct entity questions
* 4 relationship questions
* 4 multi-hop questions
* 2 aggregation questions
* 1 intentionally unanswerable question

---

# 17. Monitoring requirements

Expose useful Prometheus metrics.

Include:

```text
HTTP request count
HTTP request latency
Chat request count
Chat failures
Retrieval latency
Fuseki query latency
Milvus search latency
Ollama generation latency
Ingestion entity count
Ingestion relationship count
Ingestion failures
Answer status counts
Retrieval mode counts
```

Avoid high-cardinality labels such as raw questions or entity URIs.

Configure Prometheus to scrape:

* Backend
* Milvus metrics when compatible
* cAdvisor
* Prometheus itself

Provision Grafana automatically.

Create a useful dashboard with panels for:

* Request rate
* Error rate
* P50/P95 API latency
* Retrieval latency by mode
* Ollama latency
* Answer status
* Container CPU
* Container memory
* Ingestion totals

The dashboard should load without manual data-source setup.

---

# 18. Logging

Implement structured logs containing:

```text
timestamp
level
service
request_id
event
duration_ms
status
```

Create request IDs through middleware.

Never log:

* Passwords
* Tokens
* Full prompts by default
* Sensitive source data

Support optional debug logging through configuration.

---

# 19. Reliability and error handling

The application must degrade gracefully.

Examples:

* If Ollama is unavailable, `/retrieve` should still return retrieval results.
* `/chat` should return a clear partial result rather than an opaque 500 error when retrieval succeeded but generation failed.
* If KG2QA is absent, use the sample dataset.
* If Milvus is unavailable, graph-only retrieval should still work.
* If Fuseki is unavailable, vector-only retrieval should still work.
* If both retrieval systems fail, return a structured service-unavailable error.

Set timeouts for all external service calls.

Use retries only for safe startup or transient health operations.

Do not create infinite retry loops.

---

# 20. Security constraints

This is a development pilot, but follow basic secure practices:

* Validate all API input.
* Limit question and file sizes.
* Escape or safely bind SPARQL values.
* Do not execute user-provided SPARQL.
* Do not expose etcd publicly.
* Do not expose MinIO credentials in frontend code.
* Do not commit `.env`.
* Run application containers as non-root where practical.
* Use read-only mounts where appropriate.
* Add a basic development admin token for destructive ingestion operations.
* Add CORS configuration through environment variables.
* Include a clear production-hardening section in the README.

Do not add a complicated authentication system.

---

# 21. Testing requirements

Create meaningful automated tests.

## Unit tests

Test:

* Configuration validation
* Entity text construction
* Intent classification
* Hybrid score calculation
* Result deduplication
* Context length limiting
* KG2QA column detection
* Sample CSV-to-RDF mapping
* API model validation
* Evaluation metrics

## Integration tests

Where possible, test:

* Fuseki health and simple SPARQL query
* Milvus collection creation and search
* Backend health
* Sample ingestion
* One graph-only question
* One vector-only question
* One hybrid question

Integration tests may require Docker services and should be clearly marked.

## API tests

Use FastAPI TestClient or httpx ASGI transport for:

* Health
* Validation errors
* Chat response schema
* Retrieval response schema
* Graph search
* Ingestion authorization

## Frontend tests

At minimum:

* Type checking
* Production build
* A few component tests if practical

Add commands for:

```text
lint
format
typecheck
test
integration-test
build
```

---

# 22. Bootstrap and developer workflow

Create a Makefile supporting at least:

```make
help
env
build
up
up-gpu
down
restart
logs
ps
ingest-sample
ingest-kg2qa
test
test-integration
lint
format
evaluate
smoke-test
clean
reset-data
```

Create Linux/macOS shell scripts and Windows PowerShell equivalents for the main workflow.

The normal first-run sequence should be:

```bash
cp .env.example .env
docker compose up -d --build
docker compose run --rm data-loader --dataset sample --reset
./scripts/smoke_test.sh
```

The data-loader must support explicit command-line arguments, for example:

```bash
python -m app.ingestion.loader \
  --dataset sample \
  --reset \
  --load-graph \
  --load-vectors
```

And:

```bash
python -m app.ingestion.loader \
  --dataset kg2qa \
  --reset \
  --load-graph \
  --load-vectors
```

---

# 23. Ollama initialization

Create an `ollama-init` one-shot service that:

1. Waits until Ollama is healthy.
2. Checks whether the configured model is present.
3. Pulls it only when absent.
4. Exits successfully.

Document that this step requires internet access the first time.

Do not make the entire Compose deployment permanently fail merely because model download is temporarily unavailable.

The backend health status must clearly report whether the configured model is available.

---

# 24. Air-gapped deployment documentation

The intended organizational environment may be offline.

Add documentation explaining how to prepare on an internet-connected machine:

* Pull all Docker images.
* Download the Ollama model.
* Download the sentence-transformers model.
* Export Docker images to tar archives.
* Copy model volumes or model directories.
* Transfer the repository and dataset.
* Load images on the offline machine.
* Start Compose without internet access.

Include concrete example commands.

Do not claim the project is fully offline-ready unless all required artifacts have been downloaded.

---

# 25. Documentation

Create a detailed README containing:

1. Project overview
2. Research motivation
3. Architecture diagram
4. Technology stack
5. Directory structure
6. Prerequisites
7. Quick start
8. CPU mode
9. GPU mode
10. KG2QA dataset placement
11. Sample dataset behavior
12. Ingestion commands
13. API usage
14. Example questions
15. Evaluation procedure
16. Monitoring URLs
17. Troubleshooting
18. Security limitations
19. Air-gapped preparation
20. Known limitations
21. Future research extensions

Use Mermaid diagrams in the README and `docs/architecture.md`.

Document the exact communication protocols:

```text
Frontend -> Backend: HTTP/JSON
Backend -> Fuseki: SPARQL Protocol over HTTP
Backend -> Milvus: gRPC through pymilvus
Backend -> Ollama: HTTP/JSON
Milvus -> etcd: internal coordination
Milvus -> MinIO: object storage API
Prometheus -> services: HTTP metrics scraping
Grafana -> Prometheus: Prometheus HTTP API
```

---

# 26. AGENTS.md

Create an `AGENTS.md` file for future coding agents.

It must summarize:

* Project purpose
* Architecture boundaries
* Code conventions
* Commands to run
* Test requirements
* Safety rules
* Never execute raw LLM-generated SPARQL
* Frontend may only call backend
* Fuseki is the graph source of truth
* Milvus is a derived semantic index
* Ingestion must remain idempotent
* Every code change must preserve CPU-only mode

---

# 27. Code quality

Requirements:

* Use type annotations for public Python functions.
* Use async HTTP clients where appropriate.
* Separate API, business logic and infrastructure clients.
* Avoid giant modules.
* Avoid unnecessary abstraction.
* Add docstrings to important classes and non-obvious functions.
* Use dependency injection through FastAPI dependencies.
* Do not create circular imports.
* Use pathlib instead of fragile string paths.
* Handle errors explicitly.
* Do not suppress exceptions without logging.
* Do not leave commented-out experimental code.
* Do not leave unresolved `TODO` items for core functionality.

A few clearly documented future-work TODOs are acceptable, but the core pilot must work.

---

# 28. Implementation priorities

Implement in this order:

1. Repository structure and configuration
2. Docker Compose infrastructure
3. Built-in sample ontology and data
4. Fuseki service and RDF ingestion
5. Embedding and Milvus indexing
6. Graph retrieval
7. Vector retrieval
8. Hybrid retrieval
9. Ollama answer generation
10. API endpoints
11. Frontend
12. Evaluation
13. Monitoring
14. Tests
15. Documentation
16. Final verification

Do not spend excessive time polishing the frontend before the backend workflow works.

---

# 29. Required acceptance tests

Before declaring completion, verify as much as the environment permits.

Run:

```bash
docker compose config
```

Run backend checks:

```bash
ruff check backend
pytest backend/tests/unit
```

Build frontend:

```bash
cd frontend
npm ci
npm run typecheck
npm run build
cd ..
```

Build containers:

```bash
docker compose build
```

Start services:

```bash
docker compose up -d
```

Inspect status:

```bash
docker compose ps
```

Ingest the sample dataset:

```bash
docker compose run --rm data-loader \
  --dataset sample \
  --reset \
  --load-graph \
  --load-vectors
```

Run smoke tests.

Verify:

```text
GET /health
GET /ready
GET /api/v1/graph/stats
POST /api/v1/retrieve
POST /api/v1/chat
```

Test at least these questions:

```text
Which department sponsors Project Atlas?
Which vendor supplies the system used by Project Atlas?
Who manages the department that owns the Case Management System?
Which projects involve employees located in Riyadh?
What systems are owned by the Finance Department?
```

Verify the intentionally unanswerable question returns an insufficient-evidence response rather than inventing an answer:

```text
What is the CEO's favorite restaurant?
```

Run evaluation and save the output.

If Docker or external model downloads are unavailable in the current environment, still run all static tests and unit tests possible. Clearly document exactly which runtime checks could not be completed and why.

Do not falsely claim that checks passed.

---

# 30. Final response expected from you

After implementing the project, provide a concise completion report with:

1. What was created
2. Important architectural decisions
3. Files and directories added
4. Commands executed
5. Tests that passed
6. Tests that failed
7. Services that were successfully started
8. Anything not verified
9. Exact startup commands
10. Exact URLs for the application and monitoring interfaces

Do not return only an explanation or proposed code.

Create the project in the current working directory and perform the implementation now.
