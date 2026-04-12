import logging
import os
import re
from typing import List, Tuple

import pandas as pd
import torch
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("milvus_ingestor")

MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = os.getenv("MILVUS_COLLECTION", "document_vectors")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "32"))
MAX_DOCS = int(os.getenv("MAX_DOCS", "500"))
START_OFFSET = int(os.getenv("START_OFFSET", "0"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))

DATASET_CANDIDATES = [
    os.getenv("VI_LEGAL_CONTENT_PATH", "datasets/vi-legal/data/content.parquet"),
]


def strip_html(html: str) -> str:
    if not isinstance(html, str):
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    if not text:
        return []
    chunks = []
    step = max(1, chunk_size - overlap)
    for i in range(0, len(text), step):
        chunk = text[i:i + chunk_size].strip()
        if len(chunk) >= 60:
            chunks.append(chunk)
    return chunks


def load_documents() -> List[Tuple[str, str]]:
    for path in DATASET_CANDIDATES:
        if os.path.exists(path):
            logger.info(f"Loading documents from: {path}")
            df = pd.read_parquet(path)
            if "id" not in df.columns or "content_html" not in df.columns:
                raise ValueError("Parquet schema missing required columns: id, content_html")

            docs: List[Tuple[str, str]] = []
            for _, row in df.head(MAX_DOCS).iterrows():
                doc_id = str(row["id"])
                cleaned = strip_html(row["content_html"])
                if not cleaned:
                    continue
                for idx, chunk in enumerate(chunk_text(cleaned)):
                    docs.append((f"vi-legal:{doc_id}#chunk-{idx}", chunk))
            logger.info(f"Prepared {len(docs)} text chunks for embedding")
            return docs

    raise FileNotFoundError("No input dataset found for ingestion")


def ensure_collection(dim: int) -> Collection:
    if not utility.has_collection(COLLECTION_NAME):
        logger.info(f"Creating Milvus collection: {COLLECTION_NAME}")
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=255),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
        ]
        schema = CollectionSchema(fields=fields, description="Document chunks for RAG")
        collection = Collection(name=COLLECTION_NAME, schema=schema)
        index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": "L2",
            "params": {"nlist": 128},
        }
        collection.create_index(field_name="vector", index_params=index_params)
    else:
        collection = Collection(COLLECTION_NAME)

    collection.load()
    return collection


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Embedding device: {device}")
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL, device=device)

    dim = model.get_sentence_embedding_dimension()
    logger.info(f"Embedding dimension: {dim}")

    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    collection = ensure_collection(dim)

    docs = load_documents()
    if not docs:
        logger.warning("No documents to ingest")
        return

    filenames_batch: List[str] = []
    texts_batch: List[str] = []
    total_inserted = 0

    for filename, text in docs:
        filenames_batch.append(filename[:255])
        texts_batch.append(text[:65535])

        if len(texts_batch) >= BATCH_SIZE:
            vectors = model.encode(texts_batch, batch_size=BATCH_SIZE, show_progress_bar=False).tolist()
            collection.insert([filenames_batch, texts_batch, vectors])
            total_inserted += len(texts_batch)
            filenames_batch, texts_batch = [], []
            logger.info(f"Inserted {total_inserted} chunks")

    if texts_batch:
        vectors = model.encode(texts_batch, batch_size=BATCH_SIZE, show_progress_bar=False).tolist()
        collection.insert([filenames_batch, texts_batch, vectors])
        total_inserted += len(texts_batch)

    collection.flush()
    logger.info(f"Ingestion finished. Inserted chunks: {total_inserted}")
    logger.info(f"Collection num_entities: {collection.num_entities}")


if __name__ == "__main__":
    main()
