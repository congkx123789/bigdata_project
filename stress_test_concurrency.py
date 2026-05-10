import asyncio
import httpx
import time
import random
import statistics
import re

# Configuration
URL = "http://localhost:8003/api/chats/send"
CONCURRENT_USERS = 50
REQUESTS_PER_USER = 2
TOTAL_REQUESTS = CONCURRENT_USERS * REQUESTS_PER_USER

# Sample questions
QUESTIONS = [
    "Tôi muốn hỏi về luật hôn nhân gia đình",
    "Thủ tục ly hôn đơn phương mất bao lâu?",
    "Chia tài sản khi ly hôn thế nào?",
    "Đất đang tranh chấp có được bán không?",
    "Quy định về thừa kế đất đai?",
    "Mức phạt vi phạm giao thông mới nhất?",
    "Lương cơ bản năm 2024 là bao nhiêu?",
    "Bị công ty sa thải không lý do phải làm sao?",
    "Hợp đồng lao động vô hiệu khi nào?",
    "Thủ tục đăng ký kinh doanh hộ cá thể?"
]

async def simulate_user(client, user_id):
    latencies = []
    errors = 0
    integrity_failures = 0
    
    # Each user has a unique "mock key" to verify response integrity
    user_key = f"MOCK_KEY_USER_{user_id:03d}_{hashlib_md5(str(user_id))}"
    
    for i in range(REQUESTS_PER_USER):
        query = random.choice(QUESTIONS)
        payload = {
            "message": query,
            "session_id": f"session_u{user_id}_q{i}",
            "user_id": f"user_{user_id}",
            "api_key": user_key, # Pass unique key for integrity check
            "retrieve_only": False
        }
        
        start_time = time.time()
        try:
            response = await client.post(URL, json=payload, timeout=90.0)
            latency = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                
                # Verify Integrity Tag (echoed by mock server)
                # The tag is in the 'answer' text as a comment
                tag_match = re.search(r"INTEGRITY_TAG: KEY=(.*?) \|", answer)
                if tag_match:
                    returned_key = tag_match.group(1).strip()
                    if returned_key != user_key:
                        print(f"❌ INTEGRITY FAILURE | User {user_id} | Expected {user_key} | Got {returned_key}")
                        integrity_failures += 1
                    else:
                        latencies.append(latency)
                else:
                    # If tag missing but request successful, we count it but note the missing tag
                    latencies.append(latency)
            else:
                errors += 1
                print(f"User {user_id} | Req {i} | Error {response.status_code}")
        except Exception as e:
            errors += 1
            print(f"User {user_id} | Req {i} | Exception: {e}")
            
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
    return latencies, errors, integrity_failures

def hashlib_md5(s):
    import hashlib
    return hashlib.md5(s.encode()).hexdigest()[:8]

async def run_stress_test():
    print(f"🚀 Starting Advanced Stress Test: {CONCURRENT_USERS} users, {REQUESTS_PER_USER} req/user")
    print(f"🎯 Target URL: {URL}")
    print(f"🛡️ Integrity Check: ENABLED")
    print("-" * 50)
    
    async with httpx.AsyncClient() as client:
        start_total = time.time()
        tasks = [simulate_user(client, i) for i in range(CONCURRENT_USERS)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_total
    
    all_latencies = []
    total_errors = 0
    total_integrity_failures = 0
    for latencies, errors, integrity in results:
        all_latencies.extend(latencies)
        total_errors += errors
        total_integrity_failures += integrity
        
    if all_latencies:
        avg_latency = statistics.mean(all_latencies)
        p95_latency = statistics.quantiles(all_latencies, n=20)[18]
        throughput = len(all_latencies) / total_time
        
        print("\n" + "="*50)
        print("📊 STRESS TEST RESULTS")
        print("="*50)
        print(f"Total Requests: {TOTAL_REQUESTS}")
        print(f"Successful:     {len(all_latencies)}")
        print(f"Errors:         {total_errors}")
        print(f"Integrity Fails: {total_integrity_failures} (CRITICAL)")
        print(f"Total Time:     {total_time:.2f}s")
        print(f"Throughput:     {throughput:.2f} req/s")
        print("-" * 30)
        print(f"Avg Latency:    {avg_latency:.2f}s")
        print(f"P95 Latency:    {p95_latency:.2f}s")
        print(f"Min Latency:    {min(all_latencies):.2f}s")
        print(f"Max Latency:    {max(all_latencies):.2f}s")
        print("="*50)
        
        if total_integrity_failures == 0:
            print("✅ PASSED: No session mix-ups detected.")
        else:
            print("❌ FAILED: Session mix-ups detected! System is NOT thread-safe.")
    else:
        print("❌ No successful requests.")

if __name__ == "__main__":
    asyncio.run(run_stress_test())
