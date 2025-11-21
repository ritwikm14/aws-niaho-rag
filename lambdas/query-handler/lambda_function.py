import os
import json
import math
import re
from datetime import datetime, timezone

import boto3

s3 = boto3.client("s3")

BUCKET = os.environ["NIAHO_BUCKET"]
CHUNKS_PREFIX = os.environ.get("CHUNKS_PREFIX", "chunks/")
EMBEDDINGS_INDEX_KEY = os.environ.get("EMBEDDINGS_INDEX_KEY", "embeddings/embeddings_index.json")
EMBEDDING_MODEL_ID = os.environ.get("BEDROCK_EMBEDDING_MODEL_ID", "")
LLM_MODEL_ID = os.environ.get("BEDROCK_LLM_MODEL_ID", "")
MOCK_MODE = os.environ.get("MOCK_MODE", "true").lower() == "true"

# Only create bedrock client if we ever turn MOCK_MODE off
bedrock = boto3.client("bedrock-runtime") if not MOCK_MODE else None

# Pattern for chapter references like QM.1, LS.2, IC.3, etc.
CHAPTER_ID_PATTERN = re.compile(r"\b([A-Z]{2,3}\.\d+)\b")

def lambda_handler(event, context):
    """
    Entry point:
    - event["query"] = user query string
    - decides between 'citation' or 'question' mode
    """
    print(f"Incoming event: {json.dumps(event)}")

    # Support both direct invocation and API Gateway/Lambda proxy
    if "query" in event:
        query = event["query"]
    elif "body" in event:
        try:
            body = json.loads(event["body"])
            query = body.get("query", "")
        except Exception:
            return _response(400, {"error": "Invalid body JSON"})
    else:
        return _response(400, {"error": "Missing 'query' in event"})

    query = query.strip()
    if not query:
        return _response(400, {"error": "Empty query"})

    print(f"Received query: {query}")

    # Load embeddings index from S3
    index = load_embeddings_index()
    print(f"Loaded embeddings index with {len(index)} entries")

    qtype = detect_query_type(query)
    print(f"Detected query type: {qtype}")

    if qtype == "citation":
        result = handle_citation(query, index)
    else:
        result = handle_question(query, index)

    return _response(200, result)

# ---------- Helpers for loading data ----------

def load_embeddings_index():
    obj = s3.get_object(Bucket=BUCKET, Key=EMBEDDINGS_INDEX_KEY)
    return json.loads(obj["Body"].read())

def load_chunk(chunk_id: str):
    key = f"{CHUNKS_PREFIX}chunk_{chunk_id}.json"
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    return json.loads(obj["Body"].read())

# ---------- Query type detection ----------

def detect_query_type(query: str) -> str:
    """
    Very simple heuristic:
    - If it has a QM.1 / LS.2 / IC.3 etc. -> citation
    - If it says 'show me chapter', 'exact text', 'verbatim' -> citation
    - Otherwise -> question
    """
    if CHAPTER_ID_PATTERN.search(query):
        return "citation"

    citation_keywords = ["show me chapter", "exact text", "verbatim", "cite", "give me the wording"]
    lowered = query.lower()
    if any(kw in lowered for kw in citation_keywords):
        return "citation"

    return "question"

# ---------- Citation mode: return exact text ----------

def handle_citation(query: str, index):
    """
    Given a query like 'Show me QM.1 and LS.2',
    return the exact text chunks for those chapters.
    """
    chapter_ids = {m.group(1).upper() for m in CHAPTER_ID_PATTERN.finditer(query)}
    if not chapter_ids:
        return {
            "query": query,
            "query_type": "citation",
            "error": "No chapter ID found in query"
        }

    results = []
    now = datetime.now(timezone.utc).isoformat()

    for cid in chapter_ids:
        # Find matching entries in embeddings index
        matches = [c for c in index if c["metadata"]["chapter"].upper() == cid]
        if not matches:
            results.append({
                "query": query,
                "query_type": "citation",
                "chapter": cid,
                "found": False,
                "message": f"No matching chapter {cid} found in index"
            })
            continue

        chunk_texts = []
        chunk_ids = []

        for m in matches:
            chunk_id = m["chunk_id"]
            chunk = load_chunk(chunk_id)
            chunk_texts.append(chunk["text"])
            chunk_ids.append(chunk_id)

        combined_text = "\n\n".join(chunk_texts)

        results.append({
            "query": query,
            "query_type": "citation",
            "chapter": cid,
            "exact_text": combined_text,
            "source": {
                "document": matches[0]["metadata"]["document"],
                "section": matches[0]["metadata"]["section"],
                "chapter": cid,
                "chunk_ids": chunk_ids,
            },
            "disclaimer": f"Exact text from NIAHO standards document, retrieved {now}"
        })

    # If only one chapter requested, return it as an object, not a list
    return results[0] if len(results) == 1 else results

# ---------- Question mode: mock RAG over embeddings ----------

def handle_question(query: str, index, top_k: int = 3):
    """
    In MOCK_MODE:
    - use a deterministic fake embedding for the query
    - do cosine similarity with stored chunk embeddings
    - return top_k as 'citations'
    - return a mock answer string (no Bedrock call, no cost)
    """
    # Build a fake embedding for the query
    q_emb = mock_embedding(query)

    # Compute cosine similarity with each chunk
    scored = []
    for entry in index:
        emb = entry.get("embedding") or []
        if not emb:
            continue
        score = cosine_similarity(q_emb, emb)
        scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    citations = []
    for score, entry in top:
        citations.append({
            "chunk_id": entry["chunk_id"],
            "chapter": entry["metadata"]["chapter"],
            "section": entry["metadata"]["section"],
            "score": round(score, 4)
        })

    if MOCK_MODE:
        # We do NOT call any LLM here; this keeps it free.
        answer_text = (
            "This is a mock answer generated without calling an LLM. "
            "In a real deployment, the system would pass the top relevant NIAHO sections "
            "to Claude 3.5 Haiku and return a grounded answer with citations. "
            f"Top chapters referenced here: {[c['chapter'] for c in citations]}."
        )
        confidence = "mock"
    else:
        # Placeholder for real Bedrock call if you ever turn MOCK_MODE off
        answer_text, confidence = call_claude_with_context(query, top)

    return {
        "query": query,
        "query_type": "question",
        "answer": answer_text,
        "citations": citations,
        "confidence": confidence,
    }

# ---------- Embedding + similarity helpers ----------

def mock_embedding(text: str):
    """
    Same style as in embedding-generator: deterministic 64-dim fake embedding.
    """
    import random
    random.seed(len(text))
    return [random.random() for _ in range(64)]

def cosine_similarity(v1, v2):
    if len(v1) != len(v2):
        # Basic safety; in our mock pipeline they should match
        n = min(len(v1), len(v2))
        v1 = v1[:n]
        v2 = v2[:n]
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

def call_claude_with_context(query: str, scored_entries):
    """
    Placeholder for a real Claude 3.5 Haiku call via Bedrock.
    Not used while MOCK_MODE = true.
    """
    # This is intentionally left as a stub for now.
    return "LLM call not implemented in this environment.", "low"

# ---------- Simple HTTP-style response wrapper ----------

def _response(status_code, body_obj):
    return {
        "statusCode": status_code,
        "body": json.dumps(body_obj)
    }
