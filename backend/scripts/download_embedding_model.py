import os

from sentence_transformers import SentenceTransformer

SentenceTransformer(os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-large"), device="cpu")

