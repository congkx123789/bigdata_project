
import asyncio
import httpx
import time

URL = "http://localhost:8002/internal/inference"
NUM_REQUESTS = 10

async def send_request(client, i):
    payload = {"query": f"Câu hỏi kiểm tra song song số {i}", "retrieve_only": True}
    start = time.time()
    try:
        resp = await client.post(URL, json=payload, timeout=60)
        elapsed = time.time() - start
        print(f"Request {i:2}: Status {resp.status_code}, Time: {elapsed:.2f}s")
    except Exception as e:
        print(f"Request {i:2}: FAILED - {str(e)}")

async def main():
    print(f"Sending {NUM_REQUESTS} requests simultaneously to test Semaphore...")
    async with httpx.AsyncClient() as client:
        tasks = [send_request(client, i) for i in range(NUM_REQUESTS)]
        start_total = time.time()
        await asyncio.gather(*tasks)
        print(f"Total time for all requests: {time.time() - start_total:.2f}s")

if __name__ == "__main__":
    time.sleep(3) # Wait for server
    asyncio.run(main())
