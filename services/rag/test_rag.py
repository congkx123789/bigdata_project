import logging
from rag_pipeline import ask_question

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_rag")

def test():
    question = "What is the primary objective of the document processing system?"
    logger.info(f"Testing RAG with question: {question}")
    try:
        answer, context = ask_question(question)
        print("\n" + "="*50)
        print(f"QUESTION: {question}")
        print(f"ANSWER: {answer}")
        print("="*50 + "\n")
    except Exception as e:
        logger.error(f"Error during RAG test: {e}")

if __name__ == "__main__":
    test()
