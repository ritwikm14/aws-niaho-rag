# AWS NIAHO RAG Pipeline (Serverless, Mock-Mode)

This repository contains a **serverless Retrieval-Augmented Generation (RAG) pipeline** built on **AWS Lambda** and **Amazon S3** around the  
**DNV NIAHO® Accreditation Requirements for Hospitals** document.

The implementation is designed to:

- Ingest the NIAHO PDF into S3.
- Chunk it into chapter/section–aware JSON documents.
- Build a searchable embeddings index.
- Expose a query Lambda that supports:
  - **Citation mode** – “Show me QM.1” → return exact NIAHO text.
  - **Question mode** – natural-language question → retrieve top sections and return a grounded, mock answer with citations.

To stay within the **AWS free tier**, this version runs in **`MOCK_MODE=true`**:
all embedding and LLM calls are deterministic mocks (no Bedrock charges, no secrets).

---

## High-Level Architecture

**Services:**

- **Amazon S3**
  - `raw/` – original NIAHO PDF (not stored in this repo).
  - `chunks/` – chapter/section–aware JSON chunks.
  - `embeddings/` – global embeddings index (`embeddings_index.json`).

- **AWS Lambda**
  1. `pdf-processor-lambda`  
     - Triggered manually (test event `{}`).
     - Reads the NIAHO PDF from `raw/` in S3.
     - Uses `pypdf` (via Lambda Layer) to extract text.
     - Splits into chapter/section–oriented chunks (e.g., `QM.1`, `MS.11`).
     - Writes `chunks/chunk_XXX.json` back to S3.

  2. `embedding-generator-lambda`  
     - Triggered manually (test event `{}`).
     - Lists all objects under `chunks/`.
     - Generates **mock embeddings** for each chunk (deterministic vectors).
     - Writes a single `embeddings/embeddings_index.json` containing:
       - `chunk_id`
       - metadata (document, section, chapter)
       - token counts
       - embedding vector.

  3. `query-handler-lambda`  
     - Invoked with payloads like `{"query": "Show me QM.1"}`.
     - **Query type detection:**
       - If it finds a chapter pattern (e.g., `QM.1`), runs **citation mode**.
       - Otherwise, runs **question mode**.
     - **Citation mode:**
       - Locates the chunk(s) for the requested chapter.
       - Returns:
         - Exact NIAHO text for that chapter.
         - A structured source object (document, section, chapter, chunk IDs).
         - A timestamped disclaimer about the source.
     - **Question mode:**
       - Builds a mock embedding for the query.
       - Computes cosine similarity vs. `embeddings_index.json`.
       - Selects top-k chunks, returns:
         - A mock “answer” string explaining that in production this would call an LLM (e.g., Claude 3.5 via Bedrock).
         - A list of citations (chunk IDs, chapters, sections).
         - A simple confidence flag.

All infrastructure configuration (bucket name, prefixes, model IDs, mock mode) is controlled via **environment variables**, not hard-coded in code.

---

## Repository Layout

```text
aws-niaho-rag/
  lambdas/
    pdf-processor/
      lambda_function.py        # PDF → chunks
    embedding-generator/
      lambda_function.py        # chunks → embeddings_index
    query-handler/
      lambda_function.py        # query → citation / answer
  data/
    chunks/
      chunk_001.json            # sample real chunk JSON from S3
      chunk_025.json
      chunk_034.json
      chunk_113.json
      chunk_171.json
    raw/
      README.md                 # explains why the PDF is not committed
    embeddings_index.json       # copy of the embeddings index from S3
  events/
    test-pdf.json               # {}
    test-embed.json             # {}
    test-citation.json          # {"query": "Show me QM.1"}
    test-question.json          # {"query": "What are the quality management requirements for hospitals?"}
  .gitignore
  README.md



Data & Privacy
NIAHO PDF

The NIAHO standards PDF is not committed to this repository for licensing reasons.

In AWS, the PDF is expected at:

s3://<your-bucket>/raw/DNV_NIAHO_Accreditation_Requirements_for_Hospitals_Rev25-1.pdf


The repo includes only a small amount of derivative data:

Selected real chunk JSON files under data/chunks/, pulled from S3.

The embeddings index in data/embeddings_index.json, which contains only numeric vectors and metadata (no full-text reproduction of the document).

Sample Chunks

The following chunk files are included to illustrate the JSON schema:

data/chunks/chunk_001.json

data/chunks/chunk_025.json (Medical Staff – MS.11)

data/chunks/chunk_034.json (Staffing Management – SM.1)

data/chunks/chunk_113.json (Infection Prevention and Control – IC.3)

data/chunks/chunk_171.json (Quality Management – QM.1)

In AWS, the pdf-processor-lambda generated 301 chunks in total.

Embeddings Index

The file:

data/embeddings_index.json


is a copy of the index written by embedding-generator-lambda to:

embeddings/embeddings_index.json


It contains:

chunk_id

metadata (document, section, chapter)

token_count

embedding (list of floats)

This is safe to publish and demonstrates how the retrieval layer is structured.

Environment Variables (Per Lambda)

Each Lambda reads configuration from environment variables (no secrets in code).

Common

NIAHO_BUCKET – S3 bucket name holding raw/, chunks/, embeddings/.

CHUNKS_PREFIX – usually chunks/.

EMBEDDINGS_INDEX_KEY – usually embeddings/embeddings_index.json.

PDF Processor

RAW_KEY – e.g. raw/DNV_NIAHO_Accreditation_Requirements_for_Hospitals_Rev25-1.pdf.

Embedding Generator

BEDROCK_EMBEDDING_MODEL_ID – reserved for future use (e.g. amazon.titan-embed-text-v1).

MOCK_MODE – true in this implementation.

Query Handler

BEDROCK_LLM_MODEL_ID – reserved for future use (e.g. Claude 3.5 Haiku).

MOCK_MODE – true to avoid calling Bedrock and stay inside free tier.

In a real deployment, you can switch MOCK_MODE=false and plug in Amazon Bedrock calls using these model IDs.

Testing the Lambdas in AWS

Once the Lambdas and environment variables are configured:

1. PDF Processor

Function: pdf-processor-lambda

Test event:

{}


Expected response (example):

{
  "statusCode": 200,
  "body": "{\"message\": \"Chunks created\", \"count\": 301, ...}"
}


Expected logs:

PDF loaded from raw/...

Pages processed

“Saved 301 chunks to S3”

2. Embedding Generator

Function: embedding-generator-lambda

Test event:

{}


Expected response (example):

{
  "statusCode": 200,
  "body": "{\"message\": \"Embeddings index created\", \"chunks_indexed\": 301}"
}


Expected logs:

Found 301 chunk files

Saved embeddings index to embeddings/embeddings_index.json

3. Query Handler – Citation Mode

Function: query-handler-lambda

Test event:

{
  "query": "Show me QM.1"
}


Expected response (example):

{
  "statusCode": 200,
  "body": "{\"query\": \"Show me QM.1\", \"query_type\": \"citation\", \"chapter\": \"QM.1\", ...}"
}


The response body contains exact QM.1 text, source metadata, and a timestamped disclaimer.

4. Query Handler – Question Mode

Function: query-handler-lambda

Test event:

{
  "query": "What are the quality management requirements for hospitals?"
}


Expected response (example):

{
  "statusCode": 200,
  "body": "{ \"query_type\": \"question\", \"answer\": \"This is a mock answer...\", \"citations\": [...] }"
}


The mock answer explains that in production an LLM would be called, and citations list the top chapters (e.g., MS.11, SM.1, IC.3).

Deployment Notes

This repo is intentionally infrastructure-agnostic:

No CloudFormation / CDK / Terraform is committed.

All AWS-specific configuration (bucket names, ARNs, roles) is handled in the console and via environment variables.

No credentials, keys, or secrets are present in the codebase.

To redeploy from scratch, you would:

Create an S3 bucket and upload the NIAHO PDF to raw/....

Create an IAM role for Lambda with S3 read/write + basic execution.

Create the 3 Lambda functions, attaching:

The shared IAM role.

A pypdf-based Lambda Layer for the PDF processor.

Environment variables as described above.

Upload the plain Python files from lambdas/ as the Lambda handlers.

Test with the events from events/.

Future Extensions

The current design is intentionally simple and safe. Obvious extensions:

Swap MOCK_MODE=true for real Amazon Bedrock calls (embeddings + LLM).

Add an API Gateway or Lambda Function URL in front of query-handler-lambda.

Implement guardrails: citation thresholds, refusal when evidence is weak, and audit logging.

Add IaC (CDK/Terraform) to provision bucket, roles, and Lambdas end-to-end.

This codebase is meant to demonstrate practical RAG architecture on AWS:
clean separation of concerns, environment-driven configuration, and a realistic path from PDF → chunks → embeddings → query-time retrieval without ever exposing credentials or copyrighted source documents in version control.