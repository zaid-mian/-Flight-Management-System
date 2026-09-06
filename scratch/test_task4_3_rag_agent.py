import os
import sys
import json
sys.path.insert(0, r"E:\n8n\flight-agent-hackathon")
from app.mcp.mcp_tools import query_pinecone_policy
from app.database import get_db_cursor

def run_rag_policy_agent(inquiry_text: str, passenger_email: str = "customer@example.com"):
    print(f"\n--- Processing Policy Inquiry: '{inquiry_text}' ---")
    
    # 1. Retrieve policy evidence from Pinecone vector store
    search_res = query_pinecone_policy(query=inquiry_text, top_k=3)
    
    is_sufficient = search_res.get("is_sufficient_evidence", False)
    top_matches = search_res.get("matches", [])
    
    if not is_sufficient or not top_matches:
        answer = (
            "Thank you for contacting customer support. We could not find a specific airline policy "
            "addressing your query in our knowledge base. A support agent will review your inquiry shortly."
        )
        sources_cited = []
        status = "INSUFFICIENT_EVIDENCE_FALLBACK"
    else:
        # Build grounded response
        evidence_text = "\n\n".join([f"[{m['source']} - {m['chunk_id']}]: {m['text']}" for m in top_matches])
        sources_cited = list(set([m["source"] for m in top_matches]))
        
        answer = (
            f"Based on our official airline policy ({', '.join(sources_cited)}):\n\n"
            f"{top_matches[0]['text']}\n\n"
            f"If you have additional questions, please let us know!"
        )
        status = "GROUNDED_ANSWER_PROVIDED"
        
    # 2. Log audit trail
    payload = {
        "inquiry": inquiry_text,
        "status": status,
        "sources": sources_cited
    }
    
    with get_db_cursor() as (cur, conn):
        cur.execute("""
            INSERT INTO audit_logs (actor_type, actor_id, action, entity_name, entity_id, payload_changes)
            VALUES ('N8N_WORKFLOW', 'rag_policy_agent', 'POLICY_INQUIRY_ANSWERED', 'policy_inquiries', 'rag_query', %s::jsonb);
        """, (json.dumps(payload),))
        
    return {
        "inquiry": inquiry_text,
        "status": status,
        "answer": answer,
        "sources_cited": sources_cited,
        "is_sufficient_evidence": is_sufficient
    }

def test_task4_3_rag_agent():
    print("=== Task 4.3: RAG Policy Agent Test ===")
    
    # Test 1: Grounded Policy Query
    q1 = "What is the cancellation policy if I cancel more than 48 hours before departure?"
    res1 = run_rag_policy_agent(q1)
    print(f"[PASS] Query 1 Status: {res1['status']}")
    print(f"  - Sources Cited: {res1['sources_cited']}")
    print(f"  - Answer Snippet: {res1['answer'][:200]}...")
    assert res1["status"] == "GROUNDED_ANSWER_PROVIDED"
    assert len(res1["sources_cited"]) > 0
    
    # Test 2: Insufficient Evidence Fallback Query
    q2 = "Can I bring a live radioactive particle onto the plane?"
    res2 = run_rag_policy_agent(q2)
    print(f"\n[PASS] Query 2 Status: {res2['status']}")
    print(f"  - Answer Snippet: {res2['answer'][:200]}...")
    assert res2["status"] == "INSUFFICIENT_EVIDENCE_FALLBACK"
    
    print("\n--> TASK 4.3 RAG POLICY AGENT: ALL VERIFIED PASS! <--")
    return True

if __name__ == "__main__":
    test_task4_3_rag_agent()
