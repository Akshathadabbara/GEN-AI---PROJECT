# 🏛️ College Lost and Found Portal (GenAI & RAG Powered)

An intelligent, full-stack campus lost and found platform that reunites students with missing belongings using **Natural Language RAG (Retrieval-Augmented Generation)**, **ChromaDB Vector Embeddings**, and **OpenAI Large Language Models**.

Built on Python Flask, SQLite, ChromaDB, and modern responsive vanilla JavaScript.

---

## 🌟 Main Objective & Key Features

Help college students find lost belongings by describing items in simple, everyday natural language (e.g., *"I lost my dark-colored purse near the library yesterday"* or *"Found a blue water bottle in the classroom"*). The AI searches actual database records and identifies possible matches even when the student's wording differs from stored records.

1. **AI-Powered Natural Search Interface**:
   * Prominent natural language search box with clear button, loading indicator, and responsive layout for mobile and desktop.
   * Search scope filters: All Items, Looking for Found Items (I lost something), Looking for Lost Reports (I found something).
2. **Complete RAG Pipeline (Retrieval-Augmented Generation)**:
   * Uses an embedding model and **ChromaDB** vector database to convert descriptions and queries into high-dimensional vector representations.
   * Authoritative item records are retrieved directly from the SQLite database before generating responses, preventing hallucinated records.
   * Auto-synchronizes with the database whenever items are added, updated, or marked resolved.
3. **OpenAI LLM Integration**:
   * Uses official OpenAI API (`OPENAI_API_KEY`, defaulting to `gpt-4o-mini`).
   * **Truthful Status Handling**: If no API key is configured, the system displays a clear setup message rather than pretending the AI is working. Semantic vector search continues to operate using database records.
   * API keys are kept securely on the backend in environment variables and never exposed to frontend code or committed to Git.
4. **Context-Based Grounded AI Responses**:
   * Passes the student's query and verified database records to the LLM.
   * Generates a concise, factual summary explaining possible matches using **only** retrieved records.
   * Explicitly labels results as *possible matches*, never claiming confirmed ownership.
   * Prompt injection defense: treats all item descriptions and queries as untrusted data.
5. **Student Privacy Protection**:
   * Student contact numbers, emails, and registration numbers are strictly redacted from public item listings and vector embeddings (`"Verification Required"` / `"Protected"`).
   * Private details are only accessible to authorized campus staff with `X-Admin-Key`.
6. **Preserved Working Features**:
   * Reporting lost and found items, browsing feeds, automated candidate matching, and ownership verification claims remain fully intact.

---

## 🏗️ Architecture & Data Flow

```text
       Student Natural Language Query
   "I lost my dark-colored purse near the library"
                      │
                      ▼
         [ Embedding Generation ]
       (ChromaDB Vector Embeddings)
                      │
                      ▼
         [ Semantic Vector Search ]
      (Cosine Similarity across ChromaDB)
                      │
                      ▼
      [ Database Record Verification ]
      (Fetch Authoritative SQLite Records)
                      │
                      ▼
        [ Grounded Prompt Assembly ]
    (Query + Factual Context + Anti-Injection)
                      │
                      ▼
           [ OpenAI LLM Synthesis ]
          (Grounded Rationale Summary)
                      │
                      ▼
       [ Displayed UI Result Cards ]
 (AI Match Analysis + DB Details + Similarity %)
```

---

## 💻 Prerequisites & Setup (Windows PowerShell)

* **Operating System**: Windows 10/11
* **Python**: Python 3.10+ (Tested on Python 3.11)
* **Shell**: Windows PowerShell

### 1. Clone or Open Project Directory
```powershell
cd c:\Users\dabba\OneDrive\Desktop\College-Lost-and-Found-Portal-main
```

### 2. Create Virtual Environment
Using `uv` (recommended):
```powershell
uv venv .venv
```
Or using standard `python`:
```powershell
python -m venv .venv
```

### 3. Activate Virtual Environment
```powershell
.\.venv\Scripts\Activate.ps1
```
> *Note on Execution Policy*: If PowerShell blocks script activation (`running scripts is disabled`), run:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> .\.venv\Scripts\Activate.ps1
> ```

### 4. Install Dependencies
```powershell
uv pip install -r requirements.txt
```
Or with standard pip:
```powershell
python -m pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

Edit `.env` to configure your settings:
```ini
# Vector Database (ChromaDB)
CHROMA_PATH=chroma_data
CHROMA_COLLECTION=items_rag

# OpenAI LLM Integration
# Set your OpenAI API key here. NEVER commit this file with your real key!
OPENAI_API_KEY=your_actual_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT=10

# SQLite Database Location
DATABASE_PATH=lost_found.db

# Admin Authorization Key for Claim Reviews and Item Status Changes
ADMIN_KEY=campus_admin_secret_2026
```

> **Note on OpenAI API Key**: If left empty, the portal operates in graceful offline mode: semantic vector search retrieves matching database items, and the UI displays a clear setup banner explaining how to configure your key.

---

## ▶️ Running the Application

Start the Flask server:
```powershell
.\.venv\Scripts\python app.py
```

Open your browser and navigate to:
```
http://127.0.0.1:5000/
```

---

## 🔍 Testing the AI-Powered Search

Try entering these sample natural language queries in the search box:

1. **Semantic Conceptual Matching**:
   * Query: `I lost my dark-colored purse near the library yesterday`
   * *Match*: Retrieves database records describing a **"Black leather wallet"** found at the library.
2. **Category & Location Proximity**:
   * Query: `I found a blue water bottle in the classroom`
   * *Match*: Retrieves records for a **"Milton Insulated Bottle"** or **"Blue Flask"**.
3. **Synonym Matching**:
   * Query: `Looking for my wireless earphones misplaced in cafeteria`
   * *Match*: Retrieves records for **"Bluetooth Earbuds"** or **"AirPods"** found near the canteen.
4. **Empty / Non-Existent Item**:
   * Query: `Lost a purple hoverboard in space`
   * *Response*: Clearly states that no matching items were found in the database.

---

## 🧪 Running Automated Tests

Run the full pytest suite (21 automated unit and integration tests):
```powershell
.\.venv\Scripts\python -m pytest tests/ -v
```

### Test Coverage Summary:
* `tests/test_rag_search.py` (7 tests):
  * Semantic vector matching (*dark purse* $\leftrightarrow$ *black wallet*).
  * Ranking relevant items above unrelated items.
  * Ensuring zero results when items do not match.
  * Empty search input validation.
  * Clear setup notice when `OPENAI_API_KEY` is unconfigured.
  * Exclusion of resolved items from vector search.
  * Prompt injection resistance and secret protection.
* `tests/test_api.py` (7 tests):
  * Static file serving and index route.
  * Form field validation and item creation.
  * Automated opposite-type matching (*lost* vs *found*).
  * Exclusion of lost-vs-lost matching.
  * Item resolution workflow with `PATCH /api/items/<id>/status`.
  * Claims submission and admin inspection with `ADMIN_KEY`.
* `tests/test_matching.py` (5 tests):
  * Text normalization and synonym expansion.
  * Privacy filtering in semantic item representations.
  * Attribute scoring (color, brand, location).
  * Grounded deterministic explanation fallback.
* `tests/test_privacy.py` (2 tests):
  * Student contact redaction on public endpoints.
  * Accurate dashboard database counts.

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/ai/search` | **RAG Natural Language Search**: Vector search + OpenAI LLM synthesis |
| `GET` | `/api/items` | List reported items (publicly redacted; `X-Admin-Key` reveals contacts) |
| `POST` | `/api/items` | Report lost/found item; syncs with vector store & generates candidate matches |
| `PATCH` | `/api/items/<id>/status` | Update item status (`active`, `resolved`). Protected by `X-Admin-Key` |
| `GET` | `/api/matches` | Retrieve candidate matches between lost and found items |
| `POST` | `/api/claims` | Submit ownership verification claim with identifying marks |
| `GET` | `/api/claims` | Inspect submitted claims (Protected by `X-Admin-Key`) |
| `GET` | `/api/dashboard/stats` | Real-time counts of lost, found, active, and resolved items |

---

## 🔒 Security & Privacy Guarantees

1. **No Hallucinated Items**: All search candidates originate directly from verified SQLite records (`lost_found.db`).
2. **Student Privacy**: Phone numbers, emails, and student registration IDs are excluded from vector embeddings and redacted from public API outputs.
3. **Anti-Prompt-Injection**: User queries and item descriptions are treated strictly as untrusted text within system prompts.
4. **No Premature Handover**: High match percentages are explicitly labeled as *potential matches*, directing students to submit verification claims for administrative approval.
