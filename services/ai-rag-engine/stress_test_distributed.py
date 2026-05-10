import asyncio
import httpx
import time
import random
import statistics
import json
import os

# Configuration
URL = "http://127.0.0.1:8002/internal/inference_stream"
CONCURRENT_USERS = 50
REQUESTS_PER_USER = 1
TOTAL_REQUESTS = CONCURRENT_USERS * REQUESTS_PER_USER

QUESTIONS = [
    "Luật đất đai quy định thế nào về đền bù?",
    "Thủ tục ly hôn đơn phương mất bao lâu?",
    "Mức phạt nồng độ cồn xe máy?",
    "Lao động tự ý nghỉ việc 5 ngày có bị sa thải?",
    "Quy định về thừa kế đất đai?",
    "Lương cơ bản năm 2024 là bao nhiêu?",
    "Bị công ty sa thải không lý do phải làm sao?",
    "Thủ tục đăng ký kinh doanh hộ cá thể?",
    "Quy định về bảo hiểm xã hội 1 lần?",
    "Mức lương tối thiểu vùng năm 2024?"
]

async def simulate_user(client, user_id):
    latencies = []
    errors = 0
    mismatches = 0
    crashes = 0
    
    for i in range(REQUESTS_PER_USER):
        query = random.choice(QUESTIONS)
        # Unique session and key for this user to detect mixing
        session_id = f"session_{user_id}_{i}"
        user_key = f"key_{user_id}_{i}_secret"
        
        payload = {
            "query": query,
            "session_id": session_id,
            "google_api_key": user_key,
            "google_model": "gemini-1.5-flash"
        }
        
        start_time = time.time()
        full_response = ""
        try:
            # We use stream=True to test the streaming stability
            async with client.stream("POST", URL, json=payload, timeout=60.0) as response:
                if response.status_code == 200:
                    async for chunk in response.aiter_text():
                        full_response += chunk
                    
                    latency = time.time() - start_time
                    latencies.append(latency)
                    
                    # VERIFICATION: Check if the response contains OUR key and OUR query
                    # The mock server returns: "...trả lời câu hỏi '{user_query}' ... cho Key {key[:10]}"
                    short_key = user_key[:10]
                    # Note: Agent might truncate query or wrap it, but mock server uses it directly
                    # Let's check for the key which is more unique
                    if short_key not in full_response:
                        mismatches += 1
                        print(f"🚨 SESSION LEAK/MIXING! User {user_id} expected key {short_key} in response, but got something else.")
                        # print(f"Response snippet: {full_response[:200]}...")
                else:
                    errors += 1
                    print(f"❌ User {user_id} | Status {response.status_code}")
        except Exception as e:
            errors += 1
            print(f"⚠️ User {user_id} | Exception: {type(e).__name__}")
            
        # Small stagger to simulate realistic traffic
        await asyncio.sleep(random.uniform(0.01, 0.1))
        
    return latencies, errors, mismatches

async def run_stress_test():
    print(f"🚀 STARTING DISTRIBUTED STRESS TEST")
    print(f"👥 Users: {CONCURRENT_USERS} | Requests/User: {REQUESTS_PER_USER}")
    print(f"🎯 Target: {URL}")
    print("-" * 60)
    
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
    print("📊 STRESS TEST SUMMARY")
    print("="*60)
    print(f"Total Requests: {TOTAL_REQUESTS}")
    print(f"Successful:     {len(all_latencies)}")
    print(f"Errors:         {total_errors}")
    print(f"Session Mixing: {total_mismatches} (CRITICAL)")
    print(f"Total Duration: {total_time:.2f}s")
    
    if all_latencies:
        print(f"Throughput:     {len(all_latencies) / total_time:.2f} req/s")
        print(f"Avg Latency:    {statistics.mean(all_latencies):.2f}s")
        print(f"Min Latency:    {min(all_latencies):.2f}s")
        print(f"Max Latency:    {max(all_latencies):.2f}s")
    print("="*60)
    
    if total_mismatches == 0 and total_errors == 0:
        print("✅ STABILITY VERIFIED: No session mixing or crashes detected.")
    else:
        print("⚠️ STABILITY ISSUES DETECTED. Check logs above.")

if __name__ == "__main__":
    asyncio.run(run_stress_test())
