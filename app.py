import sys
import os
import uuid
import traceback

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()

import orchestrator

app = Flask(__name__)
app.secret_key = os.urandom(24)

# session_id → {"context": PatientContext, "state": str}
# states: "intake" | "specialist" | "cancellation" | "done"
_sessions: dict = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        session_id = data.get("session_id") or ""

        if not message:
            return jsonify({"error": "Empty message"}), 400

        # Unknown session (server restarted) → start fresh
        if session_id and session_id not in _sessions:
            session_id = ""

        # ── New conversation ──────────────────────────────────────────────────
        if not session_id:
            session_id = str(uuid.uuid4())

            # Detect cancellation intent on first message
            if orchestrator.is_cancellation_intent(message):
                context, reply, done = orchestrator.start_cancellation(message)
                _sessions[session_id] = {
                    "context": context,
                    "state": "done" if done else "cancellation",
                }
                return jsonify({
                    "session_id": session_id,
                    "reply": reply,
                    "done": done,
                    "urgency": None,
                })

            context, reply, urgency_determined = orchestrator.start_conversation(message)

            if urgency_determined:
                _sessions[session_id] = {"context": context, "state": "specialist"}
                context, reply, done = orchestrator.route_to_specialist(context)
                _sessions[session_id]["context"] = context
                _sessions[session_id]["state"] = "done" if done else "specialist"
                return jsonify({
                    "session_id": session_id,
                    "reply": reply,
                    "done": done,
                    "urgency": context.urgency.value,
                })

            _sessions[session_id] = {"context": context, "state": "intake"}
            return jsonify({
                "session_id": session_id,
                "reply": reply,
                "done": False,
                "urgency": None,
            })

        # ── Existing conversation ─────────────────────────────────────────────
        sess = _sessions[session_id]
        context = sess["context"]
        state = sess["state"]

        if state == "done":
            return jsonify({
                "session_id": session_id,
                "reply": "This conversation is complete. Refresh the page to start a new one.",
                "done": True,
                "urgency": getattr(context.urgency, "value", None),
            })

        # Cancellation also detectable mid-intake
        if state == "intake" and orchestrator.is_cancellation_intent(message):
            context2, reply, done = orchestrator.start_cancellation(message)
            sess["context"] = context2
            sess["state"] = "done" if done else "cancellation"
            return jsonify({
                "session_id": session_id,
                "reply": reply,
                "done": done,
                "urgency": None,
            })

        if state == "cancellation":
            context, reply, done = orchestrator.continue_cancellation(message, context)
            sess["context"] = context
            if done:
                sess["state"] = "done"
            return jsonify({
                "session_id": session_id,
                "reply": reply,
                "done": done,
                "urgency": None,
            })

        if state == "intake":
            context, reply, urgency_determined = orchestrator.continue_intake(message, context)
            sess["context"] = context

            if urgency_determined:
                sess["state"] = "specialist"
                context, reply, done = orchestrator.route_to_specialist(context)
                sess["context"] = context
                if done:
                    sess["state"] = "done"
                return jsonify({
                    "session_id": session_id,
                    "reply": reply,
                    "done": done,
                    "urgency": context.urgency.value,
                })

            return jsonify({
                "session_id": session_id,
                "reply": reply,
                "done": False,
                "urgency": None,
            })

        # state == "specialist"
        context, reply, done = orchestrator.next_specialist_turn(message, context)
        sess["context"] = context
        if done:
            sess["state"] = "done"
        return jsonify({
            "session_id": session_id,
            "reply": reply,
            "done": done,
            "urgency": context.urgency.value,
        })

    except Exception as exc:
        traceback.print_exc()
        return jsonify({
            "error": str(exc),
            "reply": f"Server error: {exc}",
            "done": False,
        }), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)
