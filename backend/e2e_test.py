import os
import sys
import time
import requests
from fastapi.testclient import TestClient
from main import app
import json

sys.stdout.reconfigure(encoding='utf-8')

# Setup temporary directory for test files
temp_dir = "e2e_test_files"
os.makedirs(temp_dir, exist_ok=True)

paper_a_url = "https://arxiv.org/pdf/1706.03762.pdf" # Attention is all you need
paper_b_url = "https://arxiv.org/pdf/1810.04805.pdf" # BERT

paper_a_path = os.path.join(temp_dir, "attention_is_all_you_need.pdf")
paper_b_path = os.path.join(temp_dir, "bert.pdf")

def download_file(url, path):
    if not os.path.exists(path):
        print(f"Downloading {url} to {path}...")
        r = requests.get(url)
        with open(path, "wb") as f:
            f.write(r.content)
        print("Download complete.")

def run_tests():
    download_file(paper_a_url, paper_a_path)
    download_file(paper_b_url, paper_b_path)

    metrics = {
        "upload_a_time": 0,
        "upload_b_time": 0,
        "retrieval_generation_times": []
    }

    report = []

    def log(msg):
        print(msg)
        report.append(msg)

    log("=== STARTING END-TO-END TEST ===")

    doc_a = None
    doc_b = None

    with TestClient(app) as client:
        log("\n--- UPLOAD & METRICS ---")
        
        # Upload Paper A
        start_t = time.time()
        with open(paper_a_path, "rb") as f:
            resp_a = client.post("/api/documents/upload", files={"file": ("attention_is_all_you_need.pdf", f, "application/pdf")})
        upload_time_a = time.time() - start_t
        metrics["upload_a_time"] = upload_time_a
        
        assert resp_a.status_code == 200
        doc_a = resp_a.json()
        log(f"Paper A uploaded. ID: {doc_a['id']}, Total Processing Time (Extract+Chunk+Embed): {upload_time_a:.2f}s")

        # Upload Paper B
        start_t = time.time()
        with open(paper_b_path, "rb") as f:
            resp_b = client.post("/api/documents/upload", files={"file": ("bert.pdf", f, "application/pdf")})
        upload_time_b = time.time() - start_t
        metrics["upload_b_time"] = upload_time_b
        
        assert resp_b.status_code == 200
        doc_b = resp_b.json()
        log(f"Paper B uploaded. ID: {doc_b['id']}, Total Processing Time (Extract+Chunk+Embed): {upload_time_b:.2f}s")
        
        # Get chunks to report chunk count
        resp_a_chunks = client.get(f"/api/documents/{doc_a['id']}/chunks")
        chunks_a = resp_a_chunks.json()
        log(f"Paper A generated {len(chunks_a)} chunks.")
        
        resp_b_chunks = client.get(f"/api/documents/{doc_b['id']}/chunks")
        chunks_b = resp_b_chunks.json()
        log(f"Paper B generated {len(chunks_b)} chunks.")

        def ask(question, doc_id=None):
            payload = {"question": question, "top_k": 5}
            if doc_id:
                payload["document_id"] = doc_id
            
            for attempt in range(5):
                start_t = time.time()
                resp = client.post("/api/ask", json=payload)
                req_time = time.time() - start_t
                if resp.status_code == 200:
                    metrics["retrieval_generation_times"].append(req_time)
                    return resp.json(), req_time
                if resp.status_code == 503 or resp.status_code == 500:
                    log(f"API Error {resp.status_code}: {resp.text}. Retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                assert resp.status_code == 200, resp.text
            assert False, "Failed after 5 retries"

        log("\n--- AUTOMATED QUESTIONS (PAPER A) ---")
        q1 = "What is the main objective of this research?"
        res1, t1 = ask(q1, doc_a['id'])
        log(f"\nQ: {q1}\nA: {res1['answer']}\nSources: {len(res1['sources'])}\nTime: {t1:.2f}s")
        
        q2 = "What methodology or approach does the paper propose?"
        res2, t2 = ask(q2, doc_a['id'])
        log(f"\nQ: {q2}\nA: {res2['answer']}\nSources: {len(res2['sources'])}\nTime: {t2:.2f}s")

        q3 = "What dataset or data was used?"
        res3, t3 = ask(q3, doc_a['id'])
        log(f"\nQ: {q3}\nA: {res3['answer']}\nSources: {len(res3['sources'])}\nTime: {t3:.2f}s")

        q4 = "What are the main findings or results?"
        res4, t4 = ask(q4, doc_a['id'])
        log(f"\nQ: {q4}\nA: {res4['answer']}\nSources: {len(res4['sources'])}\nTime: {t4:.2f}s")

        q5 = "What limitations are discussed in the paper?"
        res5, t5 = ask(q5, doc_a['id'])
        log(f"\nQ: {q5}\nA: {res5['answer']}\nSources: {len(res5['sources'])}\nTime: {t5:.2f}s")

        log("\n--- HALLUCINATION & ABSENT-INFO TESTS ---")
        q6 = "What is the recipe for making biryani?"
        res6, t6 = ask(q6)
        refused_6 = "couldn't find" in res6["answer"].lower()
        log(f"\nQ: {q6}\nA: {res6['answer']}\nSources: {len(res6['sources'])}\nRefusal?: {refused_6}")

        q7 = "What was the exact deployment cost of the proposed system in US dollars?"
        res7, t7 = ask(q7, doc_a['id'])
        refused_7 = "couldn't find" in res7["answer"].lower()
        log(f"\nQ: {q7}\nA: {res7['answer']}\nSources: {len(res7['sources'])}\nRefusal?: {refused_7}")

        log("\n--- DOCUMENT ISOLATION & GLOBAL SEARCH ---")
        # Global Search
        q8 = "What is bidirectional training?"
        res8, t8 = ask(q8)
        filenames_8 = list(set(s['filename'] for s in res8['sources']))
        log(f"\nGlobal Search: {q8}\nA: {res8['answer']}\nSources mostly from: {filenames_8}")

        # Document specific
        res9, t9 = ask(q8, doc_a['id'])
        filenames_9 = list(set(s['filename'] for s in res9['sources']))
        log(f"\nIsolated Search (Paper A) for '{q8}'\nSources mostly from: {filenames_9}")

    # Now exit the with-block to simulate server shutdown.
    log("\n--- RESTART TEST ---")
    with TestClient(app) as client_restart:
        log("Server restarted successfully (lifespan completed).")
        # Ask same question
        start_t = time.time()
        resp = client_restart.post("/api/ask", json={"question": "What is the Transformer?", "document_id": doc_a['id'], "top_k": 5})
        req_time = time.time() - start_t
        res10 = resp.json()
        log(f"Post-restart Q: 'What is the Transformer?'\nA: {res10['answer']}\nSources: {len(res10['sources'])}\nTime: {req_time:.2f}s")

        log("\n--- DELETION TEST ---")
        client_restart.delete(f"/api/documents/{doc_a['id']}")
        log("Paper A deleted.")
        
        # Verify chunks are gone
        resp_del = client_restart.get(f"/api/documents/{doc_a['id']}/chunks")
        assert resp_del.status_code == 404, "Chunks should be deleted"
        
        # Verify query against deleted document fails gracefully or returns empty
        resp_del_ask = client_restart.post("/api/ask", json={"question": "What is the Transformer?", "document_id": doc_a['id']})
        res11 = resp_del_ask.json()
        refused_11 = "couldn't find" in res11["answer"].lower()
        log(f"Deleted Doc Search Refusal?: {refused_11}")

    log("\n=== TEST COMPLETED ===")
    
    with open("e2e_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report))

if __name__ == "__main__":
    run_tests()
