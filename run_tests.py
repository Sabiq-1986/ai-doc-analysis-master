"""Aggressive test suite for Full Context + Reranker pipeline."""
import requests
import time
import json
import sys
import io

# Fix Windows console encoding for Arabic
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = "http://localhost:8000/api/v1"
TIMEOUT = 600  # 10 minutes per request for slow hardware

# Latest test document IDs
DOC_EN_MED = "aae78eb5-aa67-4d79-b7b0-73ddda266d9b"  # test_handbook_en.txt (8 chunks)
DOC_AR_MED = "b5e47966-b5e5-4567-8421-9e5e7ea24456"  # test_handbook_ar.txt (6 chunks)
DOC_EN_LRG = "6f5ded72-9955-4999-8df4-c1a6090d38f3"  # test_large_report_en.txt (121 chunks)
DOC_AR_LRG = "fe21a660-49be-4ae3-827d-e514640282a7"  # test_large_report_ar.txt (121 chunks)


def ask(doc_ids, question, label):
    """Create session, send question, return answer."""
    print(f"\n=== {label} ===")
    sys.stdout.flush()

    # Create session
    r = requests.post(f"{BASE}/chat/sessions", json={
        "user_id": "test", "document_ids": doc_ids
    }, timeout=30)
    r.raise_for_status()
    sid = r.json()["id"]

    # Ask question
    try:
        r = requests.post(f"{BASE}/chat/sessions/{sid}/messages",
                          json={"content": question}, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        sources = [s["filename"] for s in data.get("sources", [])]
        answer = data.get("answer", data.get("response", ""))[:300]
        print(f"  Sources: {sources}")
        print(f"  Answer: {answer}")
        sys.stdout.flush()
        return True
    except requests.exceptions.ReadTimeout:
        print(f"  TIMEOUT after {TIMEOUT}s")
        sys.stdout.flush()
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.stdout.flush()
        return False


results = {}

# T1: EN Medium - Full Context
results["T1"] = ask(
    [DOC_EN_MED],
    "What is the salary range for a Staff Engineer at TechVision?",
    "T1: EN Medium - Full Context"
)

# T2: AR Medium - Full Context
results["T2"] = ask(
    [DOC_AR_MED],
    "ما هو راتب المهندس الرئيسي في شركة رؤية التقنية؟",
    "T2: AR Medium - Full Context"
)

# T3: EN Large - RAG + Reranker
results["T3"] = ask(
    [DOC_EN_LRG],
    "What is Robert Wilson salary and performance rating?",
    "T3: EN Large - RAG + Reranker"
)

# T4: AR Large - RAG + Reranker
results["T4"] = ask(
    [DOC_AR_LRG],
    "ما هو راتب عبدالرحمن محمد النعيمي وتقييم أدائه؟",
    "T4: AR Large - RAG + Reranker"
)

# T5: Multi-doc EN+AR Medium - Full Context
results["T5"] = ask(
    [DOC_EN_MED, DOC_AR_MED],
    "Compare the salary of a Staff Engineer at TechVision with the Chief Engineer at رؤية التقنية",
    "T5: Multi-doc EN+AR Medium - Full Context"
)

# T6: Multi-doc EN+AR Large - RAG + Reranker
results["T6"] = ask(
    [DOC_EN_LRG, DOC_AR_LRG],
    "What was Q4 2024 revenue and who had the highest salary in the English report?",
    "T6: Multi-doc EN+AR Large - RAG + Reranker"
)

# Summary
print("\n" + "=" * 50)
print("RESULTS SUMMARY")
print("=" * 50)
for k, v in results.items():
    status = "PASS" if v else "FAIL"
    print(f"  {k}: {status}")
passed = sum(1 for v in results.values() if v)
print(f"\n  {passed}/{len(results)} tests passed")
sys.stdout.flush()
