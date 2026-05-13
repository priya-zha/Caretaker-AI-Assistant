import re
import sys


def _strip_markup(text: str) -> str:
    return re.sub(r"\[/?[^\]]*\]", "", text)


def _safe_print(msg: str):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)
    except Exception:
        pass


class _Console:
    """Drop-in replacement for Rich Console that never crashes."""
    def print(self, msg: str = "", **_):
        _safe_print(_strip_markup(msg))

    def rule(self, msg: str = "", **_):
        clean = _strip_markup(msg)
        _safe_print(f"\n{'─' * 30} {clean} {'─' * 30}\n")


console = _Console()


def log_bot_turn(bot_name: str, role: str, message: str):
    preview = message[:120] + ("..." if len(message) > 120 else "")
    _safe_print(f"[{bot_name}] {preview}")


def log_job(context, _=""):
    _safe_print(
        f"[Job] {context.patient_name} | "
        f"{context.urgency.value} | "
        f"{context.department.value} | "
        f"severity={context.severity_score}"
    )
