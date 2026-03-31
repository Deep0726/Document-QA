import os
import json
import pickle
import re
import pandas as pd
from dotenv import load_dotenv
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.chains import create_retrieval_chain, create_history_aware_retriever
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_groq import ChatGroq
from langchain_astradb import AstraDBChatMessageHistory
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from loader import load_document

load_dotenv("../Key.env")

os.environ["HF_TOKEN"] = os.getenv("HF_TOKEN")
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "Document Q&A with History"


# ============================================================
# LLM Models
# ============================================================

llm_cache = {}

def set_llm_model(type):
    global llm_cache
    if type in llm_cache:
        return llm_cache[type]

    if type == "Fast Model":
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.0
        )
    elif type == "Balanced Model":
        llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0.0
        )
    elif type == "Advanced Model":
        llm = ChatGroq(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            temperature=0.0
        )
    else:
        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.0)

    llm_cache[type] = llm
    return llm



_em_model    = None
_reranker    = None
local_retriever = None


def get_em_model():
    global _em_model
    if _em_model is None:
        print("[MODEL] Loading embedding model: BAAI/bge-m3")
        _em_model = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            encode_kwargs={"normalize_embeddings": True}
        )
        print("[MODEL] Embedding model loaded")
    return _em_model


def get_reranker():
    global _reranker
    if _reranker is None:
        print("[MODEL] Loading reranker: BAAI/bge-reranker-base")
        _reranker = CrossEncoderReranker(
            model=HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base"),
            top_n=5
        )
        print("[MODEL] Reranker loaded")
    return _reranker


# ============================================================
# Helper — Build Retriever with Reranker
# ============================================================

def build_retriever(ensemble_retriever):
    return ContextualCompressionRetriever(
        base_compressor=get_reranker(),
        base_retriever=ensemble_retriever
    )


# ============================================================
# Data Embedding
# ============================================================

def data_embedding(file_path, session_id):
    global local_retriever

    ext = os.path.splitext(file_path)[1].lower()

    # ✅ Sab kuch session folder ke andar save karo
    session_dir = os.path.join("faiss_indexes", session_id)
    os.makedirs(session_dir, exist_ok=True)

    # ── Excel: FAISS skip — sirf BM25 + DataFrame ──
    if ext in [".xlsx", ".xls"]:
        result = load_document(file_path)
        split_doc, dataframes = result

        # DataFrame session folder mein save karo
        df_pkl_path = os.path.join(session_dir, "df.pkl")
        with open(df_pkl_path, "wb") as f:
            pickle.dump(dataframes, f)
        print(f"[EXCEL] DataFrame saved: {df_pkl_path} | sheets: {list(dataframes.keys())}")

        # Docs pkl session folder mein save karo
        with open(os.path.join(session_dir, "docs.pkl"), "wb") as f:
            pickle.dump(split_doc, f)

        bm25_retriever = BM25Retriever.from_documents(split_doc)
        bm25_retriever.k = 10
        local_retriever = bm25_retriever
        print(f"[EXCEL] BM25-only retriever set — FAISS skipped for speed")
        return

    # ── All other file types: normal FAISS + BM25 + Reranker ──
    split_doc = load_document(file_path)

    # Docs pkl session folder mein save karo
    with open(os.path.join(session_dir, "docs.pkl"), "wb") as f:
        pickle.dump(split_doc, f)

    vectorstore = FAISS.from_documents(split_doc, get_em_model())
    vectorstore.save_local(session_dir)  # FAISS bhi session_dir mein

    faiss_retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": 10,
            "lambda_mult": 0.7,
            "fetch_k": 20
        }
    )

    bm25_retriever = BM25Retriever.from_documents(split_doc)
    bm25_retriever.k = 10

    ensemble = EnsembleRetriever(
        retrievers=[bm25_retriever, faiss_retriever],
        weights=[0.5, 0.5]
    )

    local_retriever = build_retriever(ensemble)


# ============================================================
# Load Existing Vector
# ============================================================

def load_vector(session_id):
    global local_retriever

    session_dir = os.path.join("faiss_indexes", session_id)

    # ── Excel check: df.pkl session folder mein exist karta hai ──
    df_pkl_path = os.path.join(session_dir, "df.pkl")
    is_excel = os.path.exists(df_pkl_path)

    if is_excel:
        try:
            with open(os.path.join(session_dir, "docs.pkl"), "rb") as f:
                split_doc = pickle.load(f)
            bm25_retriever = BM25Retriever.from_documents(split_doc)
            bm25_retriever.k = 10
            local_retriever = bm25_retriever
            print(f"[EXCEL] load_vector: BM25-only mode (FAISS skipped)")
        except Exception as e:
            print(f"[EXCEL load_vector ERROR]: {e}")
        return

    # ── Non-Excel: normal FAISS + BM25 + Reranker ──
    vectorstore = FAISS.load_local(
        session_dir,
        get_em_model(),
        allow_dangerous_deserialization=True
    )

    faiss_retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": 10,
            "lambda_mult": 0.7,
            "fetch_k": 20
        }
    )

    try:
        with open(os.path.join(session_dir, "docs.pkl"), "rb") as f:
            split_doc = pickle.load(f)
    except Exception:
        print("Docs not found, fallback to FAISS only")
        local_retriever = faiss_retriever
        return

    bm25_retriever = BM25Retriever.from_documents(split_doc)
    bm25_retriever.k = 10

    ensemble = EnsembleRetriever(
        retrievers=[bm25_retriever, faiss_retriever],
        weights=[0.5, 0.5]
    )

    local_retriever = build_retriever(ensemble)


# ============================================================
# Chat History — AstraDB
# ============================================================

def get_history(session_id):
    return AstraDBChatMessageHistory(
        session_id=session_id,
        token=os.getenv("ASTRA_DB_TOKEN"),
        api_endpoint="https://9cc26a57-6f4b-4d89-a39f-bfe26a973534-asia-south1.apps.astra.datastax.com",
        collection_name="chat_history"    
    )


# ============================================================
# Excel — DataFrame load karo session se
# ============================================================

def load_excel_dataframes(session_id):
    """
    Session ka saved DataFrame load karo.
    Returns: dict {sheet_name: df} ya None agar file nahi mili
    """
    df_pkl_path = os.path.join("faiss_indexes", session_id, "df.pkl")
    if not os.path.exists(df_pkl_path):
        return None
    try:
        with open(df_pkl_path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print(f"[DF LOAD ERROR]: {e}")
        return None


# ============================================================
# Excel — Query Classifier
# Decide karo: aggregation query hai ya lookup query
# ============================================================

def is_aggregation_query(question, llm_model, chat_history_str=""):
    """
    LLM se puchho ki ye question aggregation/calculation ka hai
    ya simple text lookup ka.
    chat_history_str: last few messages — follow-up questions resolve karne ke liye
    Returns: True (pandas use karo) / False (RAG use karo)
    """
    history_section = ""
    if chat_history_str:
        history_section = f"""
Recent conversation context (use this to understand follow-up questions):
{chat_history_str}
"""

    classifier_prompt = f"""You are a query classifier for tabular data (Excel/spreadsheet).
{history_section}
Classify the CURRENT question as either "aggregation" or "lookup".
Use the conversation context to understand what follow-up questions refer to.

"aggregation" means ANY of these:
- Calculation: win rate, percentage, average, sum, total, count, ratio
- Listing ALL unique values of a column: names, categories, types
- Follow-up asking "which ones", "name them", "list them", "kon konsi" after a count
- Grouping or breakdown: "by pair", "by category", "har ek ka"
- Finding min/max/best/worst across rows
- Counting rows matching a filter: "kitni trades on 23-feb"
- ANY question needing to scan ALL rows

"lookup" means: show me the DETAILS of specific records
- "show full details of trades on 25 Feb"
- "nzdusd ki 25-feb wali trade ka entry time kya tha"

Examples:
- "overall win rate kya hai" -> aggregation
- "total kitni pair hain" -> aggregation
- "which are those" (after asking about pairs) -> aggregation
- "kon konsi pair hain" -> aggregation
- "pair ke naam do" -> aggregation
- "har pair ka win rate" -> aggregation
- "how many trades on 23-feb" -> aggregation
- "23-feb ko kya trades hue" -> aggregation
- "show me the entry time of the first nzdusd trade" -> lookup

Current question: {question}

Reply with ONLY one word: aggregation OR lookup"""

    try:
        from langchain_core.messages import HumanMessage
        response = llm_model.invoke([HumanMessage(content=classifier_prompt)])
        result = response.content.strip().lower()
        print(f"[CLASSIFIER] '{question}' -> {result.split()[0]}")
        return "aggregation" in result
    except Exception as e:
        print(f"[CLASSIFIER ERROR]: {e}")
        return False  # Default to RAG on error


# ============================================================
# Excel — Schema Extract karo for LLM
# ============================================================

def get_excel_schema(dataframes):
    """
    DataFrame ka schema string banao — LLM ko dena hai
    taaki wo sahi column names aur values se pandas code likhe.
    """
    schema_parts = []

    for sheet_name, df in dataframes.items():
        schema_parts.append(f"Sheet: '{sheet_name}'")
        schema_parts.append(f"  Total rows: {len(df)}")
        schema_parts.append(f"  Columns: {list(df.columns)}")

        for col in df.columns:
            col_data = df[col].dropna()
            if len(col_data) == 0:
                continue
            dtype = str(df[col].dtype)
            if "object" in dtype or "string" in dtype:
                unique_vals = col_data.unique()
                if len(unique_vals) <= 15:
                    schema_parts.append(f"  Column '{col}' (text) unique values: {list(unique_vals)}")
                else:
                    schema_parts.append(f"  Column '{col}' (text) — {len(unique_vals)} unique values, sample: {list(unique_vals[:5])}")
            else:
                schema_parts.append(
                    f"  Column '{col}' (numeric) — min={col_data.min()}, max={col_data.max()}, mean={round(col_data.mean(), 2)}"
                )

    return "\n".join(schema_parts)


# ============================================================
# Excel — Pandas Code Safety Check
# ============================================================

BANNED_PATTERNS = [
    r'\bos\b', r'\bopen\b', r'\bimport\b', r'\bexec\b',
    r'\beval\b', r'\bsystem\b', r'\bremove\b', r'\bshutil\b',
    r'\bsubprocess\b', r'\b__\b', r'\bgetattr\b', r'\bsetattr\b',
    r'\bcompile\b', r'\bglobals\b', r'\blocals\b'
]

def is_safe_code(code):
    """
    Generated pandas code mein dangerous patterns check karo.
    Returns: True (safe) / False (dangerous)
    """
    for pattern in BANNED_PATTERNS:
        if re.search(pattern, code):
            print(f"[SAFETY BLOCK] Dangerous pattern found: {pattern}")
            return False
    return True


# ============================================================
# Excel — Pandas Execution
# ============================================================

def execute_pandas_query(question, dataframes, llm_model):
    """
    1. Schema + question → LLM → pandas code generate
    2. Safety check
    3. Code execute on actual DataFrame
    4. Result → LLM → natural language answer
    """

    schema = get_excel_schema(dataframes)
    print(f"[PANDAS DEBUG] execute_pandas_query called for: {question[:80]}")

    # ── Dynamic examples — schema se actual names inject karo ──
    # Pehli sheet aur uske columns use karo examples mein
    first_sheet = list(dataframes.keys())[0]
    first_df = dataframes[first_sheet]
    all_cols = list(first_df.columns)

    # Result/outcome column dhundo (win/loss, status, result type columns)
    outcome_col = next(
        (c for c in all_cols if any(k in c.lower() for k in ["win", "loss", "result", "status", "outcome", "profit"])),
        all_cols[-1]  # fallback: last column
    )
    # Group column dhundo (category, type, name columns)
    group_col = next(
        (c for c in all_cols if any(k in c.lower() for k in ["pair", "category", "type", "name", "group", "region", "product", "symbol"])),
        all_cols[0]  # fallback: first column
    )
    # Date/time column dhundo
    date_col = next(
        (c for c in all_cols if any(k in c.lower() for k in ["date", "time", "day", "month", "year", "period"])),
        all_cols[0]  # fallback: first column
    )

    # Outcome column ki actual win/loss values
    outcome_vals = first_df[outcome_col].dropna().astype(str).str.strip().str.lower().unique().tolist()
    win_val = next((v for v in outcome_vals if "win" in v), outcome_vals[0] if outcome_vals else "win")
    loss_val = next((v for v in outcome_vals if "loss" in v), outcome_vals[1] if len(outcome_vals) > 1 else "loss")

    # ── Step 1: Pandas code generate karo ──
    code_prompt = f"""You are a Python pandas expert writing code to answer questions about spreadsheet data.

The data is loaded as 'dfs' — a dict of DataFrames. Here is the exact schema:

{schema}

STRICT RULES:
- Use EXACTLY the column names from the schema above (case-sensitive)
- Always normalize strings before comparing: .str.strip().str.lower()
- Store the final answer in a variable called 'result'
- result must be a string, number, or DataFrame
- Do NOT import anything. Do NOT use os, open, exec, eval, system.
- Write ONLY Python code. No markdown, no backticks, no explanation.
- NEVER hardcode values — always extract them from the user question or use variables

CALCULATION PATTERNS — adapt these to the actual columns in the schema:

1. COUNT / RATE of an outcome value:
   df = dfs['{first_sheet}'].copy()
   df['{outcome_col}'] = df['{outcome_col}'].str.strip().str.lower()
   wins = (df['{outcome_col}'] == '{win_val}').sum()
   losses = (df['{outcome_col}'] == '{loss_val}').sum()
   rate = round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0
   result = str(wins) + " wins, " + str(losses) + " losses, rate=" + str(rate) + "%"

2. RATE BY GROUP (breakdown per category):
   df = dfs['{first_sheet}'].copy()
   df['{group_col}'] = df['{group_col}'].str.strip().str.lower()
   df['{outcome_col}'] = df['{outcome_col}'].str.strip().str.lower()
   rows = []
   for grp, grp_df in df.groupby('{group_col}'):
       w = (grp_df['{outcome_col}'] == '{win_val}').sum()
       l = (grp_df['{outcome_col}'] == '{loss_val}').sum()
       total = w + l
       rate = round(w / total * 100, 1) if total > 0 else 0
       rows.append({{"Group": grp, "Wins": int(w), "Losses": int(l), "Rate": str(rate)+"%"}})
   result = pd.DataFrame(rows)

3. LIST UNIQUE VALUES of a column:
   vals = dfs['{first_sheet}']['COLUMN_NAME'].dropna().str.strip().str.lower().unique().tolist()
   result = "Total " + str(len(vals)) + " unique values: " + ", ".join(sorted(str(v) for v in vals))

4. COUNT UNIQUE values in a column:
   n = dfs['{first_sheet}']['COLUMN_NAME'].dropna().nunique()
   result = "Total unique count: " + str(n)

5. FILTER ROWS matching a value (replace SEARCH_VALUE with value from user question):
   df = dfs['{first_sheet}'].copy()
   search_value = "EXTRACT_FROM_USER_QUESTION"
   mask = df['{date_col}'].astype(str).str.contains(search_value, case=False, na=False)
   filtered = df[mask]
   result = str(len(filtered)) + " rows found:" + chr(10) + filtered.to_string(index=False)

6. GROUP BY date/time — count rows per date:
   df = dfs['{first_sheet}'].copy()
   df['_date'] = df['{date_col}'].astype(str).str.extract(r'([0-9]{{1,2}}-[A-Za-z]{{3}})', expand=False)
   counts = df['_date'].value_counts().sort_index().reset_index()
   counts.columns = ['{date_col}', 'Count']
   result = counts

7. NUMERIC STATS (sum, average, min, max of a number column):
   df = dfs['{first_sheet}'].copy()
   result = df['NUMERIC_COLUMN'].describe().to_string()

User question: {question}

Write the pandas code now:"""

    try:
        from langchain_core.messages import HumanMessage
        code_response = llm_model.invoke([HumanMessage(content=code_prompt)])
        generated_code = code_response.content.strip()

        # Remove markdown backticks agar LLM ne add kiye
        generated_code = re.sub(r'^```python\s*', '', generated_code)
        generated_code = re.sub(r'^```\s*', '', generated_code)
        generated_code = re.sub(r'\s*```$', '', generated_code)
        generated_code = generated_code.strip()

        print(f"[PANDAS CODE GENERATED]:\n{generated_code}")

        # ── Step 2: Safety check ──
        if not is_safe_code(generated_code):
            return "I cannot execute this query for security reasons. Please rephrase your question."

        # ── Step 3: Execute (with retry on failure) ──
        def run_code(code):
            exec_globals = {"dfs": dataframes, "pd": pd}
            exec(code, exec_globals)
            # 'result' check karo — LLM kabhi 'filtered' ya dusra naam use karta hai
            res = exec_globals.get("result", None)
            if res is None:
                # Common fallback variable names check karo
                for fallback in ["filtered", "output", "answer", "df_result", "grouped", "out"]:
                    if fallback in exec_globals and exec_globals[fallback] is not None:
                        print(f"[PANDAS] 'result' not found, using '{fallback}'")
                        res = exec_globals[fallback]
                        break
            return res

        result = None
        try:
            result = run_code(generated_code)
        except Exception as exec_err:
            print(f"[PANDAS EXEC ERROR - attempt 1]: {exec_err}")
            # ── Retry with stricter prompt ──
            print("[PANDAS] Retrying with stricter prompt...")
            retry_prompt = f"""Fix this broken Python pandas code and rewrite it correctly.

Error: {str(exec_err)}

Broken code:
{generated_code}

Schema:
{schema}

Rules:
- The variable holding the final answer MUST be named exactly: result
- Do NOT use any other variable name for the final answer
- Do NOT import anything
- Write ONLY the corrected Python code, nothing else

Original question: {question}"""
            try:
                retry_response = llm_model.invoke([HumanMessage(content=retry_prompt)])
                retry_code = retry_response.content.strip()
                retry_code = re.sub(r"^```python\s*", "", retry_code)
                retry_code = re.sub(r"^```\s*", "", retry_code)
                retry_code = re.sub(r"\s*```$", "", retry_code)
                retry_code = retry_code.strip()
                print(f"[PANDAS RETRY CODE]:\n{retry_code}")
                if is_safe_code(retry_code):
                    result = run_code(retry_code)
            except Exception as retry_err:
                print(f"[PANDAS EXEC ERROR - retry]: {retry_err}")

        if result is None:
            return "I could not calculate this. Please try rephrasing your question."

        # Result ko string mein convert karo
        if isinstance(result, pd.DataFrame):
            result_str = result.to_string(index=False)
        elif isinstance(result, pd.Series):
            result_str = result.to_string()
        else:
            result_str = str(result)

        print(f"[PANDAS RESULT]: {result_str[:300]}")

        # ── Step 4: Natural language answer ──
        answer_prompt = f"""The user asked: "{question}"

The data analysis result is:
{result_str}

Give a clear, concise answer to the user's question based on this result.
Use markdown table format if the result has multiple rows/columns.
Do NOT mention pandas, DataFrames, or code in your answer.
Just answer naturally as if you read it from the document."""

        answer_response = llm_model.invoke([HumanMessage(content=answer_prompt)])
        return answer_response.content.strip()

    except Exception as e:
        import traceback
        print(f"[PANDAS EXEC ERROR FULL]: {traceback.format_exc()}")
        return f"I encountered an error while calculating. Please try rephrasing your question. (Error: {str(e)[:150]})"


# ============================================================
# RAG Chain Builder — Common for get_response + stream
# ============================================================

RAG_SYSTEM_PROMPT = """
You are an expert document analyst. Answer clearly and confidently 
using ONLY the provided Context below.

GROUNDING:
- Answer ONLY from the Context — zero outside knowledge.
- If the answer is not in the Context, say exactly:
  "This information is not available in the provided document."
- If Context has partial info, answer what IS there and state what is missing.
- Never guess, assume, or fabricate any fact, number, or name.

ANSWER QUALITY:
- Use exact terms, numbers, and names from the Context.
- Cover ALL relevant points — never silently drop details.
- Be assertive. Never use: "It seems...", "might be...", "possibly..."
- Instead write: "The document states..." or just state the fact directly.

FORMAT — choose based on question:
- Single fact / definition  → 2-3 plain sentences, no bullets
- Multiple items / features → one intro line + bullet list (use -, not *)
- Step-by-step process      → numbered list in exact document order
- Comparing 3+ things       → markdown table
- Complex / multi-part      → ## Heading + ### sub-sections
- Bold (**term**) only on key terms, never on full sentences
- No heading for short simple answers

Context:
{context}

"""

QUERY_REWRITER_PROMPT = """
You are a query rewriter.

Your only job is to rewrite the user's question into a clear standalone search query using the chat history.

Rules:
- Only use chat history to resolve unclear references like "it", "this", "they", "that"
- If the question is already clear, return it as-is
- Do NOT answer the question
- Do NOT add extra information
- Output only the rewritten question, nothing else
"""

def build_rag_chain(llm_model):
    q_prompt = ChatPromptTemplate.from_messages([
        ("system", QUERY_REWRITER_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")
    ])
    history_aware_retriever = create_history_aware_retriever(
        llm_model, local_retriever, q_prompt
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", RAG_SYSTEM_PROMPT),
        ("human", "{input}")
    ])
    qa_chain = create_stuff_documents_chain(llm_model, prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, qa_chain)
    return rag_chain

def get_session_history_fn(session_id):
    history = get_history(session_id)
    messages = history.messages
    if len(messages) > 8:
        last_msgs = messages[-8:]
        history.clear()
        for msg in last_msgs:
            history.add_message(msg)
    return history


# ============================================================
# RAG Response (non-streaming)
# ============================================================

def get_response(question, session_id, llm_model):

    # ── Guards ──
    if not question or len(question.strip()) < 3:
        return "Please ask a valid question."
    if len(question) > 1000:
        return "Your question is too long. Please keep it under 1000 characters."
    if local_retriever is None:
        return "Document not loaded. Please upload a document and create a session first."
    if not session_id or len(session_id.strip()) == 0:
        return "Session expired. Please start a new session."
    if llm_model is None:
        return "Model not initialized. Please try again."

    # ── Excel aggregation check ──
    dataframes = load_excel_dataframes(session_id)
    if dataframes is not None:
        # Last 3 messages fetch karo — follow-up questions resolve karne ke liye
        chat_history_str = ""
        try:
            history = get_history(session_id)
            msgs = history.messages[-6:] if len(history.messages) >= 6 else history.messages
            chat_history_str = "\n".join([
                f"{'User' if m.type == 'human' else 'Assistant'}: {m.content[:200]}"
                for m in msgs
            ])
        except Exception:
            pass

        if is_aggregation_query(question, llm_model, chat_history_str):
            print(f"[ROUTE] Aggregation → Pandas")
            return execute_pandas_query(question, dataframes, llm_model)
        else:
            print(f"[ROUTE] Lookup → RAG")

    # ── Normal RAG flow ──
    try:
        rag_chain = build_rag_chain(llm_model)
        conversational_rag_chain = RunnableWithMessageHistory(
            rag_chain,
            get_session_history_fn,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer"
        )
        responses = conversational_rag_chain.invoke(
            {"input": question},
            config={"configurable": {"session_id": session_id}}
        )
        answer = responses.get("answer", "")

        if not answer or len(answer.strip()) == 0:
            return "I could not generate a response. Please try rephrasing your question."

        return answer

    except Exception as e:
        print(f"[RAG ERROR]: {e}")
        return "An error occurred while processing your question. Please try again."


# ============================================================
# Streaming Response — SSE
# ============================================================

def get_response_stream(question, session_id, llm_model):
    """
    Generator function — SSE ke liye chunks yield karta hai.
    Excel aggregation → pandas execute karke stream karo.
    Other files → normal RAG stream.
    """

    # ── Guards ──
    if not question or len(question.strip()) < 3:
        yield f"data: {json.dumps({'type':'error','text':'Please ask a valid question.'})}\n\n"
        return
    if len(question) > 1000:
        yield f"data: {json.dumps({'type':'error','text':'Question is too long.'})}\n\n"
        return
    if local_retriever is None:
        yield f"data: {json.dumps({'type':'error','text':'Document not loaded. Please upload first.'})}\n\n"
        return
    if not session_id:
        yield f"data: {json.dumps({'type':'error','text':'Session expired.'})}\n\n"
        return

    try:
        # ── Excel aggregation check ──
        dataframes = load_excel_dataframes(session_id)
        # ✅ chat_history_str hamesha define karo — if block ke bahar rakho
        chat_history_str = ""
        if dataframes is not None:
            try:
                history = get_history(session_id)
                msgs = history.messages[-6:] if len(history.messages) >= 6 else history.messages
                chat_history_str = "\n".join([
                    f"{'User' if m.type == 'human' else 'Assistant'}: {m.content[:200]}"
                    for m in msgs
                ])
            except Exception:
                pass

        if dataframes is not None and is_aggregation_query(question, llm_model, chat_history_str):
            print(f"[STREAM ROUTE] Aggregation → Pandas")

            yield f"data: {json.dumps({'type':'thinking','step':1,'text':'🔍 Understanding your question...'})}\n\n"
            yield f"data: {json.dumps({'type':'thinking','step':2,'text':'📊 Analyzing spreadsheet data...'})}\n\n"
            yield f"data: {json.dumps({'type':'thinking','step':3,'text':'🧮 Running calculations...'})}\n\n"
            yield f"data: {json.dumps({'type':'thinking','step':4,'text':'🤖 Generating answer...'})}\n\n"

            answer = execute_pandas_query(question, dataframes, llm_model)
            yield f"data: {json.dumps({'type':'token','text':answer})}\n\n"
            yield f"data: {json.dumps({'type':'done','full_text':answer})}\n\n"
            return

        # ── Normal RAG streaming ──
        yield f"data: {json.dumps({'type':'thinking','step':1,'text':'🔍 Understanding your question...'})}\n\n"

        rag_chain = build_rag_chain(llm_model)

        yield f"data: {json.dumps({'type':'thinking','step':2,'text':'📄 Searching through document chunks...'})}\n\n"
        yield f"data: {json.dumps({'type':'thinking','step':3,'text':'⚡ Reranking best matching chunks...'})}\n\n"

        conversational_rag_chain = RunnableWithMessageHistory(
            rag_chain,
            get_session_history_fn,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer"
        )

        yield f"data: {json.dumps({'type':'thinking','step':4,'text':'🤖 Generating answer...'})}\n\n"

        full_answer = ""
        for chunk in conversational_rag_chain.stream(
            {"input": question},
            config={"configurable": {"session_id": session_id}}
        ):
            token = chunk.get("answer", "")
            if token:
                full_answer += token
                yield f"data: {json.dumps({'type':'token','text':token})}\n\n"

        if not full_answer.strip():
            full_answer = "I could not generate a response. Please try rephrasing."
            yield f"data: {json.dumps({'type':'token','text':full_answer})}\n\n"

        yield f"data: {json.dumps({'type':'done','full_text':full_answer})}\n\n"

    except Exception as e:
        print(f"[STREAM ERROR]: {e}")
        yield f"data: {json.dumps({'type':'error','text':'An error occurred. Please try again.'})}\n\n"