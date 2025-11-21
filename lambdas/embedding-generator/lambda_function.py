import os
import json
import random
import boto3

s3 = boto3.client("s3")

BUCKET = os.environ["NIAHO_BUCKET"]
CHUNKS_PREFIX = os.environ.get("CHUNKS_PREFIX", "chunks/")
EMBEDDINGS_INDEX_KEY = os.environ.get("EMBEDDINGS_INDEX_KEY", "embeddings/embeddings_index.json")
EMBEDDING_MODEL_ID = os.environ.get("BEDROCK_EMBEDDING_MODEL_ID", "")
MOCK_MODE = os.environ.get("MOCK_MODE", "true").lower() == "true"

# If we ever turn off MOCK_MODE, we'd init Bedrock here:
bedrock = boto3.client("bedrock-runtime") if not MOCK_MODE else None

def lambda_handler(event, context):
    """
    1) List all chunk_XXX.json files in S3 under chunks/
    2) For each chunk, generate an embedding (mock for now)
    3) Save updated chunks back to S3
    4) Build a global embeddings_index.json file under embeddings/
    """
    chunk_keys = list_chunk_keys()
    print(f"Found {len(chunk_keys)} chunk files")

    index_entries = []

    for key in chunk_keys:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        chunk = json.loads(obj["Body"].read())
        text = chunk["text"]

        if MOCK_MODE:
            emb = mock_embedding(text)
        else:
            emb = real_embedding(text)

        # Update chunk with embedding
        chunk["embedding"] = emb

        # Save updated chunk back to S3
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(chunk).encode("utf-8"),
            ContentType="application/json"
        )

        index_entries.append({
            "chunk_id": chunk["chunk_id"],
            "metadata": chunk["metadata"],
            "token_count": chunk["token_count"],
            "embedding": emb
        })

    # Save combined index
    s3.put_object(
        Bucket=BUCKET,
        Key=EMBEDDINGS_INDEX_KEY,
        Body=json.dumps(index_entries).encode("utf-8"),
        ContentType="application/json"
    )

    print(f"Saved embeddings index with {len(index_entries)} entries to {EMBEDDINGS_INDEX_KEY}")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Embeddings index created",
            "chunks_indexed": len(index_entries)
        })
    }

def list_chunk_keys():
    """
    List all JSON files under CHUNKS_PREFIX.
    """
    keys = []
    continuation_token = None

    while True:
        if continuation_token:
            resp = s3.list_objects_v2(
                Bucket=BUCKET,
                Prefix=CHUNKS_PREFIX,
                ContinuationToken=continuation_token
            )
        else:
            resp = s3.list_objects_v2(
                Bucket=BUCKET,
                Prefix=CHUNKS_PREFIX
            )

        for obj in resp.get("Contents", []):
            if obj["Key"].endswith(".json"):
                keys.append(obj["Key"])

        if resp.get("IsTruncated"):
            continuation_token = resp.get("NextContinuationToken")
        else:
            break

    return keys

def mock_embedding(text: str):
    """
    Deterministic fake embedding: same text -> same vector.
    This keeps everything free while still letting us build the pipeline.
    """
    random.seed(len(text))  # simple deterministic seed
    # 64-dim fake vector
    return [random.random() for _ in range(64)]

def real_embedding(text: str):
    """
    Placeholder for real Bedrock Titan embedding call if MOCK_MODE is false.
    Not used while MOCK_MODE=true.
    """
    body = json.dumps({"inputText": text})
    resp = bedrock.invoke_model(
        modelId=EMBEDDING_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body
    )
    payload = json.loads(resp["body"].read())
    return payload["embedding"]
