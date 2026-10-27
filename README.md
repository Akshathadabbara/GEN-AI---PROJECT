# 🏛️ Campus Lost and Found Portal (GenAI-Powered)

An intelligent, full-stack campus lost and found platform that reunites students with missing belongings using **semantic vector matching**, structured attribute scoring, and **Generative AI grounded explanations**.

Built on Python Flask, SQLite, and vanilla modern JavaScript.

---

## 🚀 Key Features

* **AI Semantic Candidate Matching**: Uses a hybrid matching pipeline (TF-IDF subword vector space, domain-specific campus synonym ontology, and support for Sentence Transformers) to recognize conceptual equivalence (e.g., *“Water bottle”* $\leftrightarrow$ *“Navy Flask”*, *“Earbuds”* $\leftrightarrow$ *“Headphone Case”*).
* **Opposite-Type Integrity**: Automatically pairs only Lost reports with Found reports. Never compares Lost vs. Lost or Found vs. Found.
* **Calibrated Similarity Scores & Evidence**: Produces similarity scores combining semantic similarity with structured attribute alignment (color, brand, category, campus location, and distinctive features).
* **Natural-Language Explanations (LLM + Offline Fallback)**:
  * Modular Google Gemini integration for conversational, grounded match explanations.
  * **Autonomous offline fallback**: When no API key is provided, or if rate-limited, the system seamlessly generates high-quality, grounded deterministic explanations with zero crashes.
* **Student Privacy Safeguards**:
  * Contact numbers, email addresses, and student registration numbers are strictly redacted from public item listings and AI embeddings.
  * Private details are only accessible to authorized campus staff.
* **Ownership Verification & Claims Workflow**:
  * Students submit private identifying marks (e.g., hidden scratches, serial numbers) for administrative verification rather than relying on automatic ownership assumptions.
* **Search & Semantic Directory**:
  * Real-time keyword and semantic retrieval across campus reports.
* **Live Statistics Dashboard**:
  * Real-time database metrics showing total lost, found, active, matched, and resolved belongings.

---

## 🛠️ Architecture & Data Flow

```text
[ Student Report Form ]
          │
          ▼
   [ Flask REST API ] (app.py)
          │
    ┌─────┴───────────────────────┐
    │ 1. Validate & Store         │
    │    SQLite (lost_found.db)   │
    └─────┬───────────────────────┘
          │
          ▼
   [ AI Matcher ] (ai_matcher.py)
    ├─ 2. Fetch Active Opposite-Type Candidates
    ├─ 3. Construct Non-Sensitive Semantic Document Representation
    ├─ 4. Compute Vector Cosine Similarity & Domain Expansion
    └─ 5. Calculate Attribute Alignment (Brand, Color, Location)
          │
          ▼
   [ LLM Service ] (llm_service.py)
    ├─ 6. Google Gemini (or Deterministic Offline Fallback)
    └─ 7. Grounded, Non-Hallucinatory Match Rationale
          │
          ▼
   [ SQLite Matches Table ]
          │
          ▼
[ Frontend Dynamic UI ] (script.js & index.html)
```

---

## 💻 Prerequisites & Setup (Windows PowerShell)

* **Operating System**: Windows 10/11
* **Python**: Python 3.10+ (Recommended: Python 3.12)
* **Shell**: Windows PowerShell

### 1. Clone or Open Project Folder
Open PowerShell in the project directory:
```powershell
cd c:\Users\renuk\Downloads\College-Lost-and-Found-Portal-main\College-Lost-and-Found-Portal-main
```

### 2. (Optional) Create Virtual Environment
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```
> *Note on PowerShell Execution Policy*: If PowerShell blocks script activation (`cannot be loaded because running scripts is disabled`), run:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> .\.venv\Scripts\Activate.ps1
> ```

### 3. Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
* **LLM API Key (Optional)**: If you want to use Google Gemini for explanations, obtain an API key from [Google AI Studio](https://aistudio.google.com/) and paste it into `.env`:
  ```ini
  GEMINI_API_KEY=your_gemini_api_key_here
  ```
  *If left blank, the portal operates completely offline with deterministic grounded explanations.*

---

## ▶️ Running the Application

Start the Flask server:
```powershell
python app.py
```

Open your browser and navigate to:
```
http://127.0.0.1:5000/
```

---

## 🧪 Running Automated Tests

Run the full pytest test suite:
```powershell
python -m pytest -v
```

All 14 unit and integration tests verify:
1. Application initialization & index serving.
2. Required-field form validations.
3. Automatic opposite-type AI matching.
4. Prevention of lost-versus-lost matching.
5. Exclusion of resolved items from active matches.
6. Ownership verification / claim state transitions.
7. Semantic similarity ranking (e.g. Water bottle vs. Flask).
8. Concept equivalence (Earbuds vs. Bluetooth headphone case).
9. Grounded deterministic explanation fallback.
10. Contact privacy redaction on public endpoints.
11. Accurate real-time dashboard statistics.

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/items` | List items (publicly redacted; supports `?type=`, `?category=`, `?location=`) |
| `GET` | `/api/items/<id>` | Retrieve single item details |
| `POST` | `/api/items` | Submit a new lost or found report (triggers automatic AI matching) |
| `PATCH` | `/api/items/<id>/status` | Update item status (`active`, `resolved`). Protected by `X-Admin-Key`. |
| `GET` | `/api/matches` | Retrieve ranked potential matches with evidence and explanations |
| `PATCH` | `/api/matches/<id>` | Update match state (`pending`, `dismissed`, `resolved`) |
| `POST` | `/api/items/<id>/match` | Manually re-trigger AI candidate matching for an item |
| `POST` | `/api/claims` | Submit an ownership verification claim with private identifying proof |
| `GET` | `/api/claims` | Staff access to submitted claims (Protected by `X-Admin-Key`) |
| `PATCH` | `/api/claims/<id>` | Approve or reject a claim (Protected by `X-Admin-Key`) |
| `GET` | `/api/search` | Search items by keyword or semantic query (`?q=query&type=lost`) |
| `GET` | `/api/dashboard/stats` | Live summary statistics from the SQLite database |

---

## 🔒 Security & Privacy Notice

1. **Student Confidentiality**: Phone numbers, emails, and student registration IDs are never exposed in public listing JSON payloads or semantic document embeddings.
2. **Untrusted Input Sanitation**: Descriptions are treated as plain text strings, preventing prompt injections.
3. **No Automated Handover**: High similarity scores do not trigger automated transfers; claims undergo administrative verification.
4. **Parameterized SQL**: All database operations use parameterized statements to prevent SQL injection.
