import sys
import os
import json

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentic_rag.agent import AgenticRAG

def test_full_json():
    try:
        # Initialize Agent with environment variables
        ollama_url = os.getenv("OLLAMA_URL", "http://heritage_ollama:11434")
        if not ollama_url.endswith("/v1"):
            ollama_url += "/v1"
        agent = AgenticRAG(base_url=ollama_url)
        
        query = "Quyền của người lao động khi bị thôi việc bất ngờ"
        print(f"--- EXECUTING FULL AGENTIC RAG TEST ---")
        
        # Run the agent (default to local/finetuned if applicable, or simulate the flow)
        # Note: We need a valid API key if using google provider, 
        # but here we'll just test the retrieval and summary structure.
        result = agent.run(query)
        
        # Save to JSON file
        output_file = "/app/agent_response_output.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
            
        print(f"✅ Success! JSON output saved to {output_file}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_full_json()
