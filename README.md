Perfect 👍 — here’s the **complete and final professional `README.md`** content for your root project (`aws-niaho-rag/README.md`) — not the one inside `raw/`.
It’s concise, clean, and looks like something a senior AWS engineer or top-tier open-source contributor would write:

---

````markdown
# 🧠 AWS NIAHO RAG Pipeline (Serverless, Mock Mode)

This repository implements a **serverless Retrieval-Augmented Generation (RAG) pipeline** on **AWS Lambda** and **Amazon S3**, built around the  
**DNV NIAHO® Accreditation Requirements for Hospitals** document.

> 🧩 The pipeline processes the official NIAHO standards PDF, splits it into chapter-aware JSON chunks, builds a lightweight embeddings index, and exposes a question-answering interface — all while running fully inside AWS free-tier resources.

---

## 🚀 Key Features

- **PDF Processor Lambda** – extracts text using `pypdf`, splits by chapters (`QM.1`, `MS.11`, etc.), and stores structured JSON chunks in S3.  
- **Embedding Generator Lambda** – builds deterministic *mock embeddings* (for free-tier safety) and creates an index file `embeddings_index.json`.  
- **Query Handler Lambda** – accepts user queries via a test event or API Gateway:  
  - `"Show me QM.1"` → Citation mode (returns exact section text)  
  - `"What are the quality management requirements?"` → Question mode (mock answer + citations)  
- **No Secrets / No Charges:** Runs entirely in `MOCK_MODE=true` — no Bedrock or API keys required.

---

## 🏗️ Architecture Overview

```text
┌────────────────────┐
│   S3 Bucket         │
│  ├ raw/             │  ← Original NIAHO PDF
│  ├ chunks/          │  ← JSON chapter sections
│  └ embeddings/      │  ← Embeddings index JSON
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ AWS Lambda Layers  │
│ 1. pdf-processor   │ → Extract & split PDF
│ 2. embedding-gen   │ → Build embeddings index
│ 3. query-handler   │ → Query (citation / QA)
└────────────────────┘
````

Each Lambda reads configuration from **environment variables** — no hard-coded paths or credentials.

---

## 📁 Repository Layout

```text
aws-niaho-rag/
│
├─ lambdas/
│   ├─ pdf-processor/
│   │   └─ lambda_function.py
│   ├─ embedding-generator/
│   │   └─ lambda_function.py
│   └─ query-handler/
│       └─ lambda_function.py
│
├─ data/
│   ├─ chunks/
│   │   ├─ chunk_001.json
│   │   ├─ chunk_025.json
│   │   ├─ chunk_034.json
│   │   ├─ chunk_113.json
│   │   └─ chunk_171.json
│   ├─ embeddings_index.json
│   └─ raw/
│       └─ README.md        # explains why PDF not included
│
├─ events/
│   ├─ test-pdf.json
│   ├─ test-embed.json
│   ├─ test-citation.json
│   └─ test-question.json
│
├─ .gitignore
└─ README.md
```

---

## ⚙️ Environment Variables (per Lambda)

| Variable                     | Description                         | Example                                                              |
| ---------------------------- | ----------------------------------- | -------------------------------------------------------------------- |
| `NIAHO_BUCKET`               | S3 bucket name                      | `ritwik-niaho-rag`                                                   |
| `CHUNKS_PREFIX`              | Path prefix for chunked files       | `chunks/`                                                            |
| `EMBEDDINGS_INDEX_KEY`       | Location of embeddings index        | `embeddings/embeddings_index.json`                                   |
| `RAW_KEY`                    | Original PDF path in S3             | `raw/DNV_NIAHO_Accreditation_Requirements_for_Hospitals_Rev25-1.pdf` |
| `MOCK_MODE`                  | Enables offline, deterministic mode | `true`                                                               |
| `BEDROCK_EMBEDDING_MODEL_ID` | (future use)                        | `amazon.titan-embed-text-v1`                                         |

---

## 🧪 Testing (AWS Console)

**1️⃣ PDF Processor**
Event JSON: `{}`
Expected logs:

```
Loaded PDF (459 pages)
Saved 301 chunks to S3
```

**2️⃣ Embedding Generator**
Event JSON: `{}`
Expected output:

```json
{ "message": "Embeddings index created", "chunks_indexed": 301 }
```

**3️⃣ Query Handler (Citation Mode)**
Event JSON:

```json
{ "query": "Show me QM.1" }
```

Expected output:

```json
{ "query_type": "citation", "chapter": "QM.1", "exact_text": "...", ... }
```

**4️⃣ Query Handler (Question Mode)**
Event JSON:

```json
{ "query": "What are the quality management requirements for hospitals?" }
```

Expected output:

```json
{ "query_type": "question", "answer": "This is a mock answer...", "citations": [...] }
```

---

## 🔒 Data & Privacy

* The **NIAHO PDF** is **not** committed due to licensing.
* Only minimal derivative data (sample chunks + embeddings index) is included for demonstration.
* All embeddings are mock deterministic vectors — no external API calls, no private data, no cost.

---

## 🔮 Future Work

* Replace `MOCK_MODE=true` with real Bedrock embeddings & LLMs (Claude 3.5 Haiku).
* Add **API Gateway** or **Lambda URL** for live querying.
* Introduce **guardrails** (citation thresholds, weak-evidence refusal).
* Use **Terraform / CDK** for IaC provisioning.

---

## 🧾 License & Attribution

This project is for **academic and non-commercial demonstration** of AWS serverless RAG design.
DNV and NIAHO® are registered trademarks of Det Norske Veritas Healthcare Inc.
© 2025 Ritwik Mohan. All rights reserved.

````

---

✅ Once you paste this into `D:\aws-niaho-rag\README.md` and save (`Ctrl + S`), run:

```powershell
git add README.md
git commit -m "Add full professional README for AWS NIAHO RAG project"
git push
````


