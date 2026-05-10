import os
import pandas as pd
from pymilvus import connections, Collection
import logging
from ingest_to_milvus import load_model_optimized, encode_with_retry, LegalParser
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reingest_rescue")

# Config
MILVUS_HOST = "milvus-standalone"
MILVUS_PORT = "19530"
COLLECTION_NAME = "vi_legal_rag"
DATASET_PATH = "datasets/vi-legal/data/content.parquet"

def get_existing_ids():
    """Lấy danh sách ID đã có trong Milvus (Quét từ filename)"""
    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    collection = Collection(COLLECTION_NAME)
    collection.load()
    
    logger.info("🔍 Đang quét Milvus để tìm các văn bản đã nạp...")
    # Vì Milvus không hỗ trợ DISTINCT trên hàng triệu bản ghi hiệu quả, 
    # chúng ta sẽ query lấy toàn bộ filename và parse ID.
    # Để tiết kiệm RAM, chúng ta lấy theo batch.
    existing_ids = set()
    offset = 0
    batch_size = 10000
    
    while True:
        res = collection.query(
            expr="id > 0", 
            offset=offset, 
            limit=batch_size, 
            output_fields=["filename"]
        )
        if not res: break
        for item in res:
            # filename format: "vi-legal:12345#chunk-0"
            try:
                doc_id = item['filename'].split(':')[1].split('#')[0]
                existing_ids.add(int(doc_id))
            except: continue
        offset += batch_size
        if offset % 50000 == 0:
            logger.info(f"   - Đã quét {offset} bản ghi...")
            
    return existing_ids

def main():
    existing_ids = get_existing_ids()
    logger.info(f"✅ Tìm thấy {len(existing_ids)} văn bản gốc đã nạp thành công.")
    
    logger.info(f"📖 Đang đọc bộ dữ liệu gốc từ {DATASET_PATH}...")
    df = pd.read_parquet(DATASET_PATH, columns=["id", "content_html"])
    all_ids = set(df['id'].tolist())
    
    missed_ids = all_ids - existing_ids
    logger.info(f"🚨 Phát hiện {len(missed_ids)} văn bản bị thiếu!")
    
    if not missed_ids:
        logger.info("🎉 Tuyệt vời! Không có văn bản nào bị thiếu.")
        return

    # Chỉ lấy những văn bản bị thiếu
    missed_df = df[df['id'].isin(missed_ids)]
    del df
    
    logger.info("🚀 Bắt đầu nạp bù...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = load_model_optimized(device)
    collection = Collection(COLLECTION_NAME)
    
    for _, row in missed_df.iterrows():
        try:
            parser = LegalParser(row["content_html"])
            title = parser.title
            chunks = parser.parse_to_tree_chunks()
            
            f_batch, t_batch, txt_batch = [], [], []
            for idx, c in enumerate(chunks):
                f_batch.append(f"vi-legal:{row['id']}#chunk-{idx}")
                t_batch.append(title[:499])
                txt_batch.append(c["content"][:65500])
            
            if txt_batch:
                vectors = encode_with_retry(model, txt_batch, 32)
                if vectors:
                    collection.insert([f_batch, t_batch, txt_batch, vectors])
                    logger.info(f"✅ Đã nạp bù thành công ID: {row['id']}")
        except Exception as e:
            logger.error(f"❌ Vẫn không thể nạp ID {row['id']}: {e}")

    collection.flush()
    logger.info("🏁 Quá trình nạp bù hoàn tất!")

if __name__ == "__main__":
    main()
