import os
import uuid
import json
import hashlib
import mimetypes
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, current_app, Response, stream_with_context
from main import get_response, get_response_stream, data_embedding, load_vector, set_llm_model, get_history

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max

CHAT_HISTORY_DIR = os.path.join(os.path.dirname(__file__), "chat_histories")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "txt", "md", "csv", "xls", "xlsx", "png", "jpg", "jpeg", "webp", "bmp", "ppt", "pptx"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_history_file_path(session_id):
    safe_id = "".join(c for c in session_id if c.isalnum() or c in ('-', '_'))
    return os.path.join(CHAT_HISTORY_DIR, f"{safe_id}.txt")


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_session_meta(session_id):
    path = get_history_file_path(session_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            if first_line:
                data = json.loads(first_line)
                if data.get("type") == "meta":
                    return data
    except Exception:
        pass
    return None


def save_session_meta(session_id, password_hash, file_meta=None):
    path = get_history_file_path(session_id)
    meta = {
        "type": "meta",
        "password_hash": password_hash,
        "created_at": datetime.utcnow().isoformat()
    }
    if file_meta:
        meta["file_name"] = file_meta.get("name", "")
        meta["file_size"] = file_meta.get("size", 0)
        meta["file_type"] = file_meta.get("type", "")
        meta["file_path"] = file_meta.get("path", "")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
    except Exception:
        pass


def load_chat_history(session_id):
    path = get_history_file_path(session_id)
    if not os.path.exists(path):
        return []
    messages = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        if entry.get("type") == "meta":
                            continue
                        messages.append(entry)
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass
    return messages


def save_message_to_history(session_id, role, content):
    path = get_history_file_path(session_id)
    entry = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat()
    }
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def delete_chat_file(session_id):
    path = get_history_file_path(session_id)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


@app.route("/")
def upload_page():
    return render_template("upload.html")


@app.route("/confirmation")
def confirmation_page():
    filename = session.get("uploaded_filename")
    if not filename:
        return redirect(url_for("upload_page"))
    return render_template("confirmation.html", filename=filename)


@app.route("/chat")
def chat_page():
    filename = session.get("uploaded_filename")
    if not filename:
        return redirect(url_for("upload_page"))
    # Pop these flags so they don't persist on future visits to /chat
    joined_from_home = session.pop("joined_from_home", False)
    file_available = session.pop("file_available", True)
    chat_session_id = session.get("chat_session_id", "")
    # Load existing history when joining from home so it can be rendered immediately
    chat_history = []
    if joined_from_home and chat_session_id:
        chat_history = load_chat_history(chat_session_id)
    return render_template(
        "chat.html",
        filename=filename,
        joined_from_home=joined_from_home,
        file_available=file_available,
        chat_session_id=chat_session_id,
        chat_history=chat_history
    )


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"success": False, "error": "File type not allowed"}), 400

    filename = file.filename
    file_data = file.read()
    file_size = len(file_data)
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = "application/octet-stream"

    safe_name = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
    with open(file_path, "wb") as f:
        f.write(file_data)

    session["uploaded_filename"] = filename
    session["uploaded_file_path"] = file_path
    session["uploaded_file_size"] = file_size
    session["uploaded_file_type"] = mime_type

    return jsonify({"success": True, "filename": filename, "redirect": url_for("confirmation_page")})


@app.route("/api/session/check", methods=["POST"])
def api_check_session():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "").strip()

    if not session_id:
        return jsonify({"success": False, "error": "Session ID is required"}), 400

    meta = get_session_meta(session_id)
    exists = meta is not None

    return jsonify({
        "success": True,
        "exists": exists,
        "created_at": meta.get("created_at") if exists else None
    })


@app.route("/api/session/create", methods=["POST"])
def api_create_session():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "").strip()
    password = data.get("password", "").strip()

    data_embedding(session.get("uploaded_file_path", ""),session_id)

    if not session_id:
        return jsonify({"success": False, "error": "Session ID is required"}), 400

    if not password:
        return jsonify({"success": False, "error": "Password is required"}), 400

    meta = get_session_meta(session_id)
    is_existing = meta is not None

    if is_existing:
        stored_hash = meta.get("password_hash", "")
        if hash_password(password) != stored_hash:
            return jsonify({"success": False, "error": "Incorrect password. Access denied."}), 401
        existing_history = load_chat_history(session_id)
        filename = session.get("uploaded_filename", "document")
        welcome_message = f"Welcome back! Resuming session for \"{filename}\". Your previous conversation has been loaded."
        session["chat_session_id"] = session_id
        save_message_to_history(session_id, "ai", welcome_message)
        return jsonify({
            "success": True,
            "session_id": session_id,
            "message": welcome_message,
            "history": existing_history
        })
    else:
        password_hash = hash_password(password)
        filename = session.get("uploaded_filename", "document")
        file_meta = {
            "name": filename,
            "size": session.get("uploaded_file_size", 0),
            "type": session.get("uploaded_file_type", ""),
            "path": session.get("uploaded_file_path", "")
        }
        save_session_meta(session_id, password_hash, file_meta)
        welcome_message = f"Hello! I've analyzed \"{filename}\". What would you like to know about it?"
        session["chat_session_id"] = session_id
        save_message_to_history(session_id, "ai", welcome_message)
        return jsonify({
            "success": True,
            "session_id": session_id,
            "message": welcome_message,
            "history": []
        })


@app.route("/api/session/join", methods=["POST"])
def api_join_session():
    """Join an existing session from the home page using session ID and password."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "").strip()
    password = data.get("password", "").strip()

    

    if not session_id:
        return jsonify({"success": False, "error": "Session ID is required"}), 400

    if not password:
        return jsonify({"success": False, "error": "Password is required"}), 400

    meta = get_session_meta(session_id)
    if meta is None:
        return jsonify({"success": False, "error": "Session not found. Please check the Session ID."}), 404

    stored_hash = meta.get("password_hash", "")
    if hash_password(password) != stored_hash:
        return jsonify({"success": False, "error": "Incorrect password. Access denied."}), 401

    file_name = meta.get("file_name", "document")
    file_path = meta.get("file_path", "")
    file_size = meta.get("file_size", 0)
    file_type = meta.get("file_type", "")
    file_available = bool(file_path) and os.path.exists(file_path)

    if file_available:
        load_vector(session_id)
        
    session["uploaded_filename"] = file_name
    session["uploaded_file_path"] = file_path if file_available else ""
    session["uploaded_file_size"] = file_size
    session["uploaded_file_type"] = file_type
    session["chat_session_id"] = session_id
    session["joined_from_home"] = True
    session["file_available"] = file_available

    existing_history = load_chat_history(session_id)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "file_name": file_name,
        "file_size": file_size,
        "file_type": file_type,
        "file_available": file_available,
        "history": existing_history,
        "redirect": url_for("chat_page")
    })


@app.route("/api/chat", methods=["POST"])
def api_chat():
    
    

    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()
    model = data.get("model", "Balanced Model")
    session_id = data.get("session_id", "")

    llm_model = set_llm_model(type=model)

    if not question:
        return jsonify({"success": False, "error": "Question is required"}), 400

    filename = session.get("uploaded_filename", "your document")

    save_message_to_history(session_id, "user", question)

    # TODO: Connect your Python AI/RAG backend here
    answer = get_response(question, session_id,llm_model)

    save_message_to_history(session_id, "ai", answer)
    
    return jsonify({
        "success": True,
        "answer": answer,
        "session_id": session_id,
        "model": model
    })


@app.route("/api/chat/stream", methods=["POST"])
def api_chat_stream():
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()
    model    = data.get("model", "Balanced Model")
    session_id = data.get("session_id", "")

    if not question:
        def err():
            yield f"data: {json.dumps({'type':'error','text':'Question is required'})}\n\n"
        return Response(stream_with_context(err()), mimetype="text/event-stream")

    llm_model = set_llm_model(type=model)
    save_message_to_history(session_id, "user", question)

    def generate():
        full_answer = ""
        for chunk in get_response_stream(question, session_id, llm_model):
            yield chunk
            # Extract full_text from done event to save history
            if chunk.startswith("data:"):
                try:
                    payload = json.loads(chunk[5:].strip())
                    if payload.get("type") == "done":
                        full_answer = payload.get("full_text", "")
                except Exception:
                    pass
        if full_answer:
            save_message_to_history(session_id, "ai", full_answer)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@app.route("/api/preview-file")
def api_preview_file():



    file_path = session.get("uploaded_file_path")
    if not file_path or not os.path.exists(file_path):
        return "File not found", 404

    original_filename = session.get("uploaded_filename", "document")
    mime_type, _ = mimetypes.guess_type(original_filename)
    if not mime_type:
        mime_type = "application/octet-stream"

    return send_file(file_path, mimetype=mime_type, download_name=original_filename)


@app.route("/api/session/close", methods=["POST"])
def api_close_session():
    session.clear()
    return jsonify({"success": True, "redirect": url_for("upload_page")})

@app.route("/api/session/end", methods=["POST"])
def api_end_session():
    session_id = session.get("chat_session_id", "")

    if session_id:
        try:
            history = get_history(session_id)
            history.clear()
        except Exception as e:
            print("DB delete error:", e)


    if session_id:
        delete_chat_file(session_id)
    
    uploaded_path = session.get("uploaded_file_path", "")
    if uploaded_path and os.path.exists(uploaded_path):
        try:
            os.remove(uploaded_path)
        except Exception as e:
            current_app.logger.exception(f"File delete failed: {uploaded_path} | {e}")

    
    if session_id:
        # ✅ Sab kuch session folder ke andar hai — sirf folder delete karo
        import shutil
        session_dir = os.path.join("faiss_indexes", session_id)
        if os.path.isdir(session_dir):
            try:
                shutil.rmtree(session_dir)
            except Exception as e:
                current_app.logger.exception(f"Failed to delete session dir {session_dir}: {e}")
                
    session.clear()
    return jsonify({"success": True, "redirect": url_for("upload_page")})

@app.route("/api/reset", methods=["POST"])
def api_reset():
    session.clear()
    return jsonify({"success": True, "redirect": url_for("upload_page")})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)