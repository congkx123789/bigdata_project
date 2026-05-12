import os
import time
import logging
import pandas as pd
import torch
import gc
import threading
from queue import Queue, Empty
from sentence_transformers import SentenceTransformer
from pymilvus import (
    connections,
    FieldSchema, CollectionSchema, DataType,
    Collection, utility
)
from legal_parser import LegalParser

# ═══════════════════════════════════════════════════
# BLACKWELL GPU OPTIMIZATIONS
# ═══════════════════════════════════════════════════
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["TOKENIZERS_PARALLELISM"] = "true"
# cuDNN benchmark sẽ được bật sau khi import torch
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
torch.backends.cudnn.benchmark = True

# Ghi log ra console và file với định dạng thời gian sạch
logger = logging.getLogger("milvus_ingestor")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s | %(message)s", datefmt="%H:%M:%S")

# File Handler
# Dùng tên file mới để tránh lỗi Permission Denied từ file cũ của Docker
log_path = os.path.join(os.path.dirname(__file__), "../../../ingestion_host.log")
fh = logging.FileHandler(log_path, mode="w")
fh.setFormatter(formatter)

# Console Handler
ch = logging.StreamHandler()
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)
logger.propagate = False # Tránh lặp log

# Config
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "vi_legal_rag"
MODEL_NAME = "BAAI/bge-m3"
BATCH_SIZE = 8
DIMENSION = 1024
NUM_WORKERS = 12  # Tăng luồng để tận dụng CPU Blackwell mạnh mẽ
GC_THRESHOLD = 100 # Dọn rác cực kỳ thường xuyên

DATASET_CANDIDATES = [
    "/home/alida/Documents/Cursor/Bigdata/hf_snapshots/data/content.parquet",
    "datasets/vi-legal/data/content.parquet",
    "/app/datasets/vi-legal/data/content.parquet"
]
CHECKPOINT_FILE = "ingestion_checkpoint.txt"
MAX_DOCS = int(os.getenv("MAX_DOCS", "178665"))
START_OFFSET = int(os.getenv("START_OFFSET", "0"))
REINGEST = os.getenv("REINGEST", "false").lower() == "true"


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r") as f:
                return int(f.read().strip())
        except:
            return 0
    return 0


def save_checkpoint(offset):
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(str(offset))


def create_collection():
    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    if REINGEST and utility.has_collection(COLLECTION_NAME):
        utility.drop_collection(COLLECTION_NAME)
        if os.path.exists(CHECKPOINT_FILE):
            os.remove(CHECKPOINT_FILE)

    if not utility.has_collection(COLLECTION_NAME):
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=255),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=DIMENSION),
        ]
        collection = Collection(COLLECTION_NAME, CollectionSchema(fields))
        collection.create_index(
            "vector",
            {"metric_type": "L2", "index_type": "IVF_FLAT", "params": {"nlist": 1024}},
        )
    else:
        collection = Collection(COLLECTION_NAME)
    collection.load()
    return collection


def load_model_optimized(device):
    """Load BGE-M3 with Blackwell-native optimizations."""
    logger.info(f"🚀 Loading {MODEL_NAME} on {device}...")

    # Thử FlashAttention2 trước, fallback sang SDPA
    model = None
    for attn_impl in ["flash_attention_2", "sdpa", None]:
        try:
            kwargs = {"attn_implementation": attn_impl} if attn_impl else {}
            model = SentenceTransformer(MODEL_NAME, device=device, model_kwargs=kwargs)
            if attn_impl:
                logger.info(f"✅ Attention: {attn_impl}")
            break
        except Exception as e:
            logger.warning(f"⚠️ {attn_impl} not available: {e}")
            continue

    if model is None:
        model = SentenceTransformer(MODEL_NAME, device=device)

    if device == "cuda":
        # BF16 native cho Blackwell (tốt hơn FP16)
        if torch.cuda.is_bf16_supported():
            model = model.to(dtype=torch.bfloat16)
            logger.info("✅ BF16 enabled (Blackwell native)")
        else:
            model = model.half()
            logger.info("✅ FP16 enabled")

        # Tắt torch.compile để tiết kiệm VRAM
        # Tắt torch.compile để tiết kiệm VRAM
        # try:
        #     model[0].auto_model = torch.compile(model[0].auto_model, mode="reduce-overhead")
        #     logger.info("✅ torch.compile enabled (Blackwell optimized)")
        # except Exception as e:
        #     logger.warning(f"⚠️ torch.compile skipped: {e}")

    return model


def encode_with_retry(model, texts, batch_size):
    """Encode với auto-retry: nếu OOM thì chia nhỏ batch và thử lại."""
    try:
        with torch.inference_mode():
            return model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
            ).tolist()
    except torch.cuda.OutOfMemoryError:
        torch.cuda.empty_cache()
        gc.collect()
        # Chia đôi batch và thử lại
        mid = len(texts) // 2
        if mid == 0:
            logger.error(f"❌ Single text too long, skipping")
            return None
        logger.warning(f"⚠️ OOM! Splitting batch {len(texts)} -> {mid} + {len(texts)-mid}")
        v1 = encode_with_retry(model, texts[:mid], batch_size)
        v2 = encode_with_retry(model, texts[mid:], batch_size)
        if v1 is None or v2 is None:
            return None
        return v1 + v2


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = load_model_optimized(device)
    collection = create_collection()
    resume_offset = load_checkpoint() if not REINGEST else 0

    for path in DATASET_CANDIDATES:
        if not os.path.exists(path):
            continue
        logger.info(f"📖 Loading: {path}")
        df = pd.read_parquet(path, columns=["id", "content_html"])
        actual_start = START_OFFSET + resume_offset
        subset_df = df.iloc[actual_start : actual_start + MAX_DOCS]
        total_docs = len(subset_df)
        logger.info(f"⚡ Ingesting {total_docs:,} docs from #{actual_start}")
        del df
        gc.collect()

        # ── Producer threads ──
        chunk_queue = Queue(maxsize=500)
        docs_processed = 0
        doc_lock = threading.Lock()
        start_time = time.time()

        def producer_worker(data_chunk):
            nonlocal docs_processed
            for _, row in data_chunk.iterrows():
                try:
                    parser = LegalParser(row["content_html"])
                    title = parser.title
                    for idx, c in enumerate(parser.parse_to_tree_chunks()):
                        text = c["content"].encode("utf-8")[:65500].decode("utf-8", "ignore")
                        chunk_queue.put({
                            "filename": f"vi-legal:{row['id']}#chunk-{idx}"[:255],
                            "title": title.encode('utf-8')[:499].decode('utf-8','ignore'),
                            "text": text,
                        })
                    with doc_lock:
                        docs_processed += 1
                except Exception as e:
                    with doc_lock:
                        docs_processed += 1
                        # Ghi lại ID bị lỗi để chạy lại sau
                        err_log_path = os.path.join(os.path.dirname(__file__), "../../../failed_ingestion_ids.txt")
                        with open(err_log_path, "a") as f_err:
                            f_err.write(f"{row['id']} | Error: {str(e)}\n")
                    logger.error(f"❌ Error processing doc {row['id']}: {e}")
                    continue

        # Chia dữ liệu cho các luồng
        chunk_size = len(subset_df) // NUM_WORKERS + 1
        threads = []
        for i in range(NUM_WORKERS):
            t_df = subset_df.iloc[i * chunk_size : (i + 1) * chunk_size]
            t = threading.Thread(target=producer_worker, args=(t_df,), daemon=True)
            t.start()
            threads.append(t)

        # ── Consumer (GPU) ──
        total_inserted = 0
        f_batch, t_batch, txt_batch = [], [], []

        while any(t.is_alive() for t in threads) or not chunk_queue.empty():
            try:
                item = chunk_queue.get(timeout=3)
                f_batch.append(item["filename"].encode('utf-8')[:255].decode('utf-8','ignore'))
                t_batch.append(item["title"].encode('utf-8')[:499].decode('utf-8','ignore'))
                txt_batch.append(item["text"].encode('utf-8')[:65500].decode('utf-8','ignore'))

                if len(txt_batch) >= BATCH_SIZE:
                    vectors = encode_with_retry(model, txt_batch, BATCH_SIZE)
                    if vectors is not None:
                        try:
                            collection.insert([f_batch, t_batch, txt_batch, vectors])
                            total_inserted += len(txt_batch)
                        except Exception as e:
                            logger.warning(f"⚠️ Insert failed, skipping batch: {e}")

                    # Progress
                    with doc_lock:
                        cur_docs = docs_processed
                    elapsed = time.time() - start_time
                    rate = total_inserted / elapsed if elapsed > 0 else 0
                    eta_min = (total_docs - cur_docs) / (cur_docs / elapsed) / 60 if cur_docs > 0 else 0
                    vram = torch.cuda.memory_allocated() / 1024**3 if device == "cuda" else 0
                    logger.info(
                        f"📊 {actual_start+cur_docs:,}/{actual_start+total_docs:,} docs | "
                        f"{total_inserted:,} chunks | {rate:.1f}/s | "
                        f"ETA: {eta_min:.0f}min | VRAM: {vram:.1f}GB"
                    )

                    # Checkpoint mỗi 100 docs
                    if cur_docs % 100 == 0 and cur_docs > 0:
                        save_checkpoint(resume_offset + cur_docs)
                        collection.flush()

                    f_batch, t_batch, txt_batch = [], [], []
                    # GC chạy mỗi 200 chunks để bảo vệ RAM
                    if total_inserted % GC_THRESHOLD == 0:
                        gc.collect()
                        if device == "cuda": torch.cuda.empty_cache()

            except Empty:
                continue

        # Final batch
        if txt_batch:
            vectors = encode_with_retry(model, txt_batch, BATCH_SIZE)
            if vectors:
                collection.insert([f_batch, t_batch, txt_batch, vectors])
                total_inserted += len(txt_batch)

        collection.flush()
        with doc_lock:
            final_docs = docs_processed
        save_checkpoint(resume_offset + final_docs)

        elapsed = time.time() - start_time
        logger.info(f"✅ DONE! {total_inserted:,} chunks in {elapsed/60:.1f}min ({total_inserted/elapsed:.1f}/s)")
        break


if __name__ == "__main__":
    main()
