import logging
import time
from functools import wraps
from flask import Flask, jsonify, render_template, request
from config import Config
from database import (
    get_incidents,
    get_recent_metrics,
    get_summary_stats,
    init_db,
    save_metric,
    sync_incident,
)
from telemetry import collect_system_metrics, evaluate_health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
init_db()

system_state = {
    "is_healthy": True,
    "failure_reason": "",
}


def require_api_key(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        provided_key = request.headers.get("X-API-Key")
        if provided_key != Config.API_KEY:
            logger.warning("Nieautoryzowana proba dostepu do %s", request.path)
            return jsonify({"status": "ERROR", "message": "Brak poprawnego klucza API"}), 401
        return func(*args, **kwargs)

    return wrapper


@app.route("/", methods=["GET"])
@app.route("/dashboard", methods=["GET"])
def dashboard():
    return render_template("dashboard.html", service_name=Config.SERVICE_NAME)


@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify(
        {
            "service": Config.SERVICE_NAME,
            "status": "OK" if system_state["is_healthy"] else "ERROR",
            "message": "System monitorowania dostepnosci uslug chmurowych dziala poprawnie.",
        }
    ), 200


@app.route("/health", methods=["GET"])
def health_check():
    started = time.perf_counter()
    metrics = collect_system_metrics()
    is_ok, message = evaluate_health(
        metrics,
        system_state["is_healthy"],
        system_state["failure_reason"],
    )
    response_time_ms = round((time.perf_counter() - started) * 1000, 2)
    status_label = "OK" if is_ok else "ERROR"
    http_code = 200 if is_ok else 500

    save_metric(
        status=status_label,
        http_code=http_code,
        cpu_percent=metrics["cpu_percent"],
        ram_percent=metrics["ram_percent"],
        disk_percent=metrics["disk_percent"],
        response_time_ms=response_time_ms,
        message=message,
    )
    sync_incident(is_ok, message)

    logger.info(
        "Health check: %s (%s) | CPU=%s%% RAM=%s%% DISK=%s%%",
        status_label,
        http_code,
        metrics["cpu_percent"],
        metrics["ram_percent"],
        metrics["disk_percent"],
    )

    return jsonify(
        {
            "status": status_label,
            "message": message,
            "ram_usage": f"{metrics['ram_percent']}%",
            "cpu_usage": f"{metrics['cpu_percent']}%",
            "disk_usage": f"{metrics['disk_percent']}%",
            "uptime_seconds": metrics["uptime_seconds"],
            "response_time_ms": response_time_ms,
            "thresholds": {
                "ram": Config.RAM_THRESHOLD,
                "cpu": Config.CPU_THRESHOLD,
                "disk": Config.DISK_THRESHOLD,
            },
        }
    ), http_code


@app.route("/break", methods=["POST"])
@require_api_key
def break_system():
    payload = request.get_json(silent=True) or {}
    reason = payload.get("reason", "Recznie wywolana symulacja awarii wezla")
    system_state["is_healthy"] = False
    system_state["failure_reason"] = reason
    sync_incident(False, reason)
    logger.error("Wywolano symulacje awarii: %s", reason)
    return jsonify(
        {
            "status": "ERROR",
            "message": "Zasymulowano awarie systemu. Endpoint /health zwraca teraz blad 500.",
            "reason": reason,
        }
    ), 200


@app.route("/fix", methods=["POST"])
@require_api_key
def fix_system():
    system_state["is_healthy"] = True
    system_state["failure_reason"] = ""
    sync_incident(True, "System przywrocony do normy")
    logger.info("Przywrocono poprawne dzialanie systemu")
    return jsonify(
        {
            "status": "OK",
            "message": "Naprawiono system. Endpoint /health dziala normalnie.",
        }
    ), 200


@app.route("/api/history", methods=["GET"])
def api_history():
    limit = request.args.get("limit", default=50, type=int)
    limit = max(1, min(limit, 500))
    return jsonify({"items": get_recent_metrics(limit)}), 200


@app.route("/api/incidents", methods=["GET"])
def api_incidents():
    limit = request.args.get("limit", default=50, type=int)
    limit = max(1, min(limit, 200))
    return jsonify({"items": get_incidents(limit)}), 200


@app.route("/api/stats", methods=["GET"])
def api_stats():
    return jsonify(get_summary_stats()), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT)