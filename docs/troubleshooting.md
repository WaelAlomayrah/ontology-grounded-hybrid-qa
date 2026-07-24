# Troubleshooting

- First startup is slow while Ollama and Hugging Face models download; inspect `docker compose logs ollama-init backend`.
- Dimension errors mean `MILVUS_VECTOR_DIMENSION` does not match the embedding model; use 1024 for the default and reset the derived Milvus volume after intentionally changing models.
- If Docker lacks memory, temporarily select smaller configurable models.
- A partial chat answer means retrieval succeeded while Ollama was unavailable.
- Run `docker compose config`, `docker compose ps`, and inspect individual health checks before resetting data.

