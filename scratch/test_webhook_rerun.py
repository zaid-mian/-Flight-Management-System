import urllib.request
import urllib.error
import json
import time

def test_n8n_webhook_reliability():
    print("=== N8N WEBHOOK STABILITY TEST ===")
    url = "https://mlengineerss.app.n8n.cloud/webhook/jobscout-search"
    payload = {
        "cvText": "Preflight stability retest",
        "location": "Remote",
        "targetRole": "Backend Developer"
    }
    data = json.dumps(payload).encode('utf-8')
    
    successes = 0
    failures = 0
    attempts = 3
    
    for i in range(1, attempts + 1):
        print(f"\nAttempt {i}/{attempts} to {url}...")
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        try:
            start_time = time.time()
            with urllib.request.urlopen(req, timeout=15) as response:
                status = response.getcode()
                elapsed = time.time() - start_time
                res_body = response.read().decode('utf-8')
                print(f"  -> Attempt {i}: HTTP {status} (took {elapsed:.2f}s)")
                print(f"  -> Response: {res_body[:120]}")
                if status == 200:
                    successes += 1
                else:
                    failures += 1
        except Exception as e:
            print(f"  -> Attempt {i} FAILED: {type(e).__name__} - {e}")
            failures += 1
        time.sleep(1)
        
    print("\n----------------------------------")
    if successes == attempts:
        print(f"RESULT: PASS ({successes}/{attempts} succeeded reliably)")
        return "PASS"
    elif successes > 0:
        print(f"RESULT: TRANSIENT/RETRY ({successes}/{attempts} succeeded, {failures} failed)")
        return "TRANSIENT/RETRY"
    else:
        print(f"RESULT: FAIL (0/{attempts} succeeded)")
        return "FAIL"

if __name__ == "__main__":
    test_n8n_webhook_reliability()
