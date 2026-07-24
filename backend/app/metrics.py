from prometheus_client import Counter, Histogram

CHAT_REQUESTS = Counter("ontology_chat_requests_total", "Chat requests")
CHAT_FAILURES = Counter("ontology_chat_failures_total", "Chat generation or retrieval failures")
RETRIEVAL_LATENCY = Histogram("ontology_retrieval_duration_seconds", "Retrieval latency", ["mode"])
FUSEKI_QUERY_LATENCY = Histogram("ontology_fuseki_query_duration_seconds", "Fuseki query latency")
MILVUS_SEARCH_LATENCY = Histogram("ontology_milvus_search_duration_seconds", "Milvus search latency")
OLLAMA_LATENCY = Histogram("ontology_ollama_generation_duration_seconds", "Ollama generation latency")
INGESTION_ENTITIES = Counter("ontology_ingestion_entities_total", "Entities ingested", ["dataset"])
INGESTION_RELATIONSHIPS = Counter("ontology_ingestion_relationships_total", "Relationships ingested", ["dataset"])
INGESTION_FAILURES = Counter("ontology_ingestion_failures_total", "Ingestion failures", ["dataset"])
ANSWER_STATUS = Counter("ontology_answer_status_total", "Answers grouped by status", ["status"])
RETRIEVAL_MODES = Counter("ontology_retrieval_modes_total", "Retrieval requests grouped by mode", ["mode"])

