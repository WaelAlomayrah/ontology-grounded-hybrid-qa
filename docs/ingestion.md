# Ingestion

The loader discovers external formats, maps tolerant CSV columns, merges RDF graphs, serializes one upload to Fuseki, builds descriptive entity passages, adds E5 passage prefixes, and deterministically upserts Milvus documents. Reset clears graph data and replaces vectors from that source. Reports contain counts, elapsed seconds, failures, skips, warnings, and errors.

