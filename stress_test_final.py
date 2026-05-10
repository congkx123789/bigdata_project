import asyncio
import httpx
import time
import random
import statistics
import json

# Configuration
URL = "http://localhost:8003/api/chats/send"
CONCURRENT_USERS = 50
REQUESTS_PER_USER = 2
TOTAL_REQUESTS = CONCURRENT_USERS * REQUESTS_PER_USER

QUESTIONS = [
    "Luật đất đai quy định thế nào về đền bù?",
    "Thủ tục ly hôn đơn phương mất bao lâu?",
    "Mức phạt nồng độ cồn xe máy?",
    "Lao động tự ý nghỉ việc 5 ngày có bị sa thải?",
    "Quy định về thừa kế đất đai?",
    "Lương cơ bản năm 2024 là bao nhiêu?",
    "Bị công ty sa thải không lý do phải làm sao?",
    "Thủ tục đăng ký kinh doanh hộ cá thể?"
]

async def simulate_user(client, user_id):
    latencies = []
    errors = 0
    mismatches = 0
    
    for i in range(REQUESTS_PER_USER):
        query = random.choice(QUESTIONS)
        session_id = f"stress_session_{user_id}_{i}"
        payload = {
            "message": query,
            "session_id": session_id,
            "user_id": f"user_{user_id}",
            "retrieve_only": False
        }
        
        start_time = time.time()
        try:
            # High timeout to account for semaphore queuing
            response = await client.post(URL, json=payload, timeout=120.0)
            latency = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                reply = data.get("reply", "")
                
                # Verify that the session_id returned matches ours (no leakage)
                # Note: In our current API, session_id is returned in the response
                resp_session = data.get("session_id", "")
                if resp_session != session_id:
                    mismatches += 1
                    print(f"🚨 SESSION LEAK DETECTED! Expected {session_id}, got {resp_session}")
                
                latencies.append(latency)
            else:
                errors += 1
                print(f"❌ User {user_id} | Req {i} | Status {response.status_code} | {response.text[:100]}")
        except Exception as e:
            errors += 1
            print(f"⚠️ User {user_id} | Req {i} | Exception: {type(e).__name__} - {str(e)[:50]}")
            
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
    return latencies, errors, mismatches

async def run_stress_test():
    print(f"🚀 STRESS TEST: {CONCURRENT_USERS} concurrent users, total {TOTAL_REQUESTS} requests")
    print(f"🎯 Target: {URL} (using Mock Google Server)")
    print("-" * 60)
    
    # Use a large connection pool to avoid client-side bottlenecks
    limits = httpx.Limits(max_keepalive_connections=100, max_connections=200)
    async with httpx.AsyncClient(limits=limits) as client:
        start_total = time.time()
        tasks = [simulate_user(client, i) for i in range(CONCURRENT_USERS)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_total
    
    all_latencies = []
    total_errors = 0
    total_mismatches = 0
    for latencies, errors, mismatches in results:
        all_latencies.extend(latencies)
        total_errors += errors
        total_mismatches += mismatches
        
    print("\n" + "="*60)
    print("📊 FINAL RESULTS")
    print("="*60)
    print(f"Total Requests: {TOTAL_REQUESTS}")
    print(f"Successful:     {len(all_latencies)}")
    print(f"Errors:         {total_errors}")
    print(f"Session Leaks:  {total_mismatches}")
    print(f"Total Time:     {total_time:.2f}s")
    
    if all_latencies:
        print(f"Throughput:     {len(all_latencies) / total_time:.2f} req/s")
        print(f"Avg Latency:    {statistics.mean(all_latencies):.2f}s")
        print(f"P95 Latency:    {statistics.quantiles(all_latencies, n=20)[18]:.2f}s")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_stress_test())
