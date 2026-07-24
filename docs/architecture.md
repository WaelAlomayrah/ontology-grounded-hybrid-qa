# Architecture

```mermaid
sequenceDiagram
 participant U as User
 participant F as Frontend
 participant B as FastAPI
 participant J as Fuseki
 participant M as Milvus
 participant O as Ollama
 U->>F: Natural-language question
 F->>B: HTTP/JSON
 par bounded graph retrieval
 B->>J: SPARQL Protocol over HTTP
 and semantic retrieval
 B->>M: gRPC through pymilvus
 end
 B->>B: transparent weighted fusion and context bounds
 B->>O: grounded prompt over HTTP/JSON
 O-->>B: concise answer
 B-->>F: answer + sources + graph + timings
```

Milvus uses etcd for internal coordination and MinIO's object storage API. Prometheus scrapes HTTP metrics; Grafana queries the Prometheus HTTP API. Failure boundaries deliberately retain either retrieval mode and treat generation as optional after evidence retrieval.

