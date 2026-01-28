import os
import json
import httpx

API = os.getenv("API_URL", "http://127.0.0.1:8000")
TOKEN = os.getenv("TOKEN")  # paste your Bearer token here via env var

QUERIES = [
    "author of moby dick",
    "what is the name of the narrator",
    "what is the ship called",
]

def main():
    if not TOKEN:
        raise SystemExit("Set TOKEN env var to your JWT access token first.")

    headers = {"Authorization": f"Bearer {TOKEN}"}

    with httpx.Client(timeout=30.0) as client:
        for q in QUERIES:
            r = client.post(
                f"{API}/v1/rag/query",
                headers=headers,
                json={"question": q, "top_k": 5},
            )
            print("\n=== QUERY:", q)
            print("status:", r.status_code)
            data = r.json()
            print("answer:", data.get("answer"))
            cites = data.get("citations", [])
            if cites:
                print("top_score:", cites[0].get("score"))
            else:
                print("top_score: none")
            print("citations:", len(cites))
            # print first citation snippet
            if cites:
                print("top_citation_snippet:", cites[0].get("snippet"))

if __name__ == "__main__":
    main()
