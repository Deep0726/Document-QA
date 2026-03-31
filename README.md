# 📄 Document QA System (Flask + Advanced RAG)

An advanced **Document Question Answering system** built using Flask that allows users to upload document and ask context-aware questions.  
This project implements a **Retrieval-Augmented Generation (RAG)** pipeline using hybrid search, reranking, and large language models for accurate responses.

---

## 🚀 Features

- 📂 Upload and process document
- 🧠 Semantic search using embeddings  
- ⚡ Fast vector search with FAISS  
- 🔍 Hybrid retrieval (Vector + BM25)  
- 🎯 Reranking using cross-encoder  
- 💬 Chat-based Q&A interface  
- 📝 Chat history tracking  
- 🌐 Interactive web UI  

---

## 🧠 Models & Architecture

### 🔹 Embedding Model
- **BAAI/bge-m3** (HuggingFace)

### 🔹 LLM (via Groq)
- LLaMA 3 (70B)
- GPT-OSS 120B
- LLaMA 4 Scout (17B)

### 🔹 Retrieval Pipeline
- FAISS (Vector Database)
- BM25 (Keyword-based Retrieval)
- Ensemble Retriever (Hybrid Search)
- Cross-Encoder Reranker (BAAI/bge-reranker-base)

👉 This combination enables high-accuracy contextual answers using both semantic and keyword matching.

---

## 🏗️ Project Structure

```bash
flask-doc-qa/
│
├── Website/
│   ├── app.py              # Flask app entry point
│   ├── main.py             # QA pipeline & logic
│   ├── loader.py           # Document processing
│   │
│   ├── static/             # CSS & JS files
│   ├── templates/          # HTML templates
│   │
│   ├── uploads/            # Uploaded documents
│   ├── faiss_indexes/      # Vector storage
│   ├── chat_histories/     # Chat logs
│
├── .gitignore
├── README.md

```
---

## ⚙️ How It Works

1. User uploads a document 📄  
2. Text is extracted and chunked  
3. Chunks are converted into embeddings 🧠  
4. Stored in FAISS vector database ⚡  
5. Hybrid retrieval (FAISS + BM25) is applied 🔍  
6. Results are reranked using cross-encoder 🎯  
7. Top context is passed to LLM 🤖  
8. Final answer is generated 💬  

---

## 🛠️ Tech Stack

- **Backend:** Flask (Python)  
- **Frontend:** HTML, CSS, JavaScript  
- **Vector DB:** FAISS  
- **Retrieval:** BM25 + Ensemble Retriever  
- **Reranking:** Cross-Encoder  
- **LLM Provider:** Groq  
- **Embeddings:** HuggingFace  

---

## 🛠️ Installation

```bash
git clone https://github.com/Deep0726/Document-QA.git
cd flask-doc-qa
pip install -r requirements.txt
```

## 🔑 Environment Setup

Create a file named:

```
key.env
```

Add your API key:

```
LANGCHAIN_API_KEY=your_api_key_here

HUGGINGFACE_API_KEY=your_api_key_here

HF_TOKEN=your_api_key_here

GROQ_API_KEY=your_api_key_here

ASTRA_DB_ID=your_api_key_here

ASTRA_DB_TOKEN=your_api_key_here

ASTRA_DB_KEYSPACE=your_keyspace_here

ASTRA_DB_API_ENDPOINT=your_endpoint_here

Gemini_API_Key=your_api_key_here

```
