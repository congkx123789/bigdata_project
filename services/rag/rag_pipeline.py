import os
import logging
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection
from sentence_transformers import SentenceTransformer
from langchain.llms import Ollama
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser
from dotenv import load_dotenv

load_dotenv()

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag_pipeline")

# Configuration
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
EMBEDDING_MODEL = "BAAI/bge-m3"
COLLECTION_NAME = "document_vectors"
DIMENSION = 1024 # BGE-M3 dimension

# 1. Initialize BGE-M3 Embeddings
logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
model = SentenceTransformer(EMBEDDING_MODEL)

# 2. Connect to Milvus
connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)

# Create Collection if not exists
if not Collection.exists(COLLECTION_NAME):
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=255),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=DIMENSION)
    ]
    schema = CollectionSchema(fields, "Document collection for RAG")
    collection = Collection(COLLECTION_NAME, schema)
    
    # Create Index
    index_params = {
        "index_type": "IVF_FLAT",
        "metric_type": "L2",
        "params": {"nlist": 128}
    }
    collection.create_index("vector", index_params)
    logger.info(f"Created collection: {COLLECTION_NAME}")
else:
    collection = Collection(COLLECTION_NAME)
    collection.load()

# 3. LangChain with Local Llama-3 (via Ollama)
llm = Ollama(model="llama3")

def get_context(query, k=5):
    """
    Search Milvus for relevant documents
    """
    query_vector = model.encode([query])[0].tolist()
    search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
    
    results = collection.search(
        data=[query_vector],
        anns_field="vector",
        param=search_params,
        limit=k,
        output_fields=["filename", "text"]
    )
    
    context = ""
    for hits in results:
        for hit in hits:
            context += f"\n[Source: {hit.entity.get('filename')}]\n{hit.entity.get('text')}\n"
    return context

# 4. RAG Pipeline
prompt_template = """
You are an AI assistant for a large document repository. 
Answer the following question based ONLY on the provided context.
If you don't know the answer, say "I don't have enough information from the documents."

CONTEXT:
{context}

QUESTION: {question}

ANSWER:
"""

prompt = ChatPromptTemplate.from_template(prompt_template)

def ask_question(question: str):
    context = get_context(question)
    chain = (
        {"context": lambda x: context, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    return chain.invoke(question), context

if __name__ == "__main__":
    # Test
    logger.info("RAG Pipeline initialized. Ready for questions.")
    # result, source = ask_question("What is the main topic of your documents?")
    # print(f"Answer: {result}")
    # print(f"Sources: {source}")
