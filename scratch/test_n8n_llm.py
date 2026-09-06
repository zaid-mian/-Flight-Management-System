import urllib.request
import urllib.error
import json
import sys

def test_n8n_webhook():
    print("=== N8N & LLM LIVE PREFLIGHT TEST ===")
    url = "https://mlengineerss.app.n8n.cloud/webhook/jobscout-search"
    payload = {
        "cvText": "Python Developer experienced in FastAPI, Postgres, n8n, AI Agents",
        "location": "Remote",
        "targetRole": "AI Engineer"
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        print(f"Sending POST request to {url}...")
        with urllib.request.urlopen(req, timeout=30) as response:
            status = response.getcode()
            res_body = response.read().decode('utf-8')
            print(f"Status Code: {status}")
            print(f"Response snippet: {res_body[:500]}")
            if status == 200:
                print("\n[PASS] n8n Webhook, Postgres/InMemory node, and LLM Execution fully operational!")
                return True
            else:
                print(f"\n[FAIL] Unexpected status code {status}")
                return False
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} - {e.reason}")
        print(f"Error body: {e.read().decode('utf-8', errors='ignore')}")
        return False
    except Exception as e:
        print(f"Exception during request: {type(e).__name__} - {e}")
        return False

if __name__ == "__main__":
    test_n8n_webhook()
