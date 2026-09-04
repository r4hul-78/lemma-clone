import urllib.request
import json
import time

def run_tests():
    # 1. Health check
    res = urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')
    health = json.loads(res.read().decode())
    print("=== 1. HEALTH CHECK ===", flush=True)
    print("Overall Status:", health["status"], flush=True)
    print("Database:", health["services"]["database"]["status"], flush=True)
    print("Elasticsearch:", health["services"]["elasticsearch"]["status"], flush=True)
    print("Ollama:", health["services"]["ollama"]["status"], flush=True)

    # 2. Document upload
    url = 'http://127.0.0.1:8000/api/v1/documents/upload'
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    body = (
        f'--{boundary}\r\n'
        'Content-Disposition: form-data; name="file"; filename="sample.txt"\r\n'
        'Content-Type: text/plain\r\n\r\n'
        'Plagiarism involves reproducing another persons work without proper acknowledgment.\r\n'
        f'--{boundary}--\r\n'
    ).encode('utf-8')

    req = urllib.request.Request(url, data=body, headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    try:
        res = urllib.request.urlopen(req)
        doc_data = json.loads(res.read().decode())
        print("\n=== 2. DOCUMENT UPLOAD ===", flush=True)
        print("Filename:", doc_data.get("filename"), flush=True)
        print("Char Count:", doc_data.get("char_count"), flush=True)
        print("Sentences Extracted:", doc_data.get("sentence_count"), flush=True)
    except Exception as e:
        if hasattr(e, 'read'):
            print("Upload Error Body:", e.read().decode(), flush=True)
        raise e

    # 3. Rewrite test
    req_rw = urllib.request.Request(
        'http://127.0.0.1:8000/api/v1/rewrite',
        data=json.dumps({'text': 'Plagiarism is copying work without attribution.', 'tone': 'academic'}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    res_rw = urllib.request.urlopen(req_rw)
    rw_data = json.loads(res_rw.read().decode())
    print("\n=== 3. OLLAMA REWRITE LLM ===", flush=True)
    print("Original:", rw_data["original_text"], flush=True)
    print("Rewritten:", rw_data["rewritten_text"], flush=True)

    # 4. Asynchronous Plagiarism Analysis Test
    url_ana = 'http://127.0.0.1:8000/api/v1/analyze'
    req_ana = urllib.request.Request(url_ana, data=body, headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    res_ana = urllib.request.urlopen(req_ana)
    ana_data = json.loads(res_ana.read().decode())
    job_id = ana_data.get("job_id")
    print("\n=== 4. ASYNC PLAGIARISM ANALYSIS QUEUED ===", flush=True)
    print("Job ID:", job_id, flush=True)
    print("Initial Status:", ana_data.get("status"), flush=True)

    # Poll status
    time.sleep(12)
    res_st = urllib.request.urlopen(f'http://127.0.0.1:8000/api/v1/status/{job_id}')
    st_data = json.loads(res_st.read().decode())
    print("Polled Status:", st_data.get("status"), flush=True)
    if st_data.get("status") == "completed":
        print("Analysis Result Similarity Score:", st_data.get("result", {}).get("analysis", {}).get("overall_similarity_score"), flush=True)
    elif st_data.get("status") == "failed":
        print("Task Failure Error:", st_data.get("error"), flush=True)

    # 5. Frontend static check
    res_front = urllib.request.urlopen('http://127.0.0.1:8000/dashboard.html')
    print("\n=== 5. FRONTEND DASHBOARD HTML ===", flush=True)
    print(f"Status Code: {res_front.status}, Content Length: {len(res_front.read())} bytes", flush=True)

if __name__ == "__main__":
    run_tests()
