from flask import Flask, jsonify
import os
import psutil

app = Flask(__name__)

is_healthy = True
RAM_THRESHOLD = 90.0


@app.route('/')
def home():
    return jsonify({"message": "Witaj w aplikacji medycznej. System dziala poprawnie."}), 200


@app.route('/health')
def health_check():
    global is_healthy

    if not is_healthy:
        return jsonify({"status": "ERROR", "message": "Recznie wywolana awaria bazy danych!"}), 500

    ram_usage = psutil.virtual_memory().percent

    if ram_usage > RAM_THRESHOLD:
        return jsonify({
            "status": "ERROR",
            "message": f"Krytyczne zuzycie pamieci RAM: {ram_usage}%"
        }), 500

    return jsonify({
        "status": "OK",
        "ram_usage": f"{ram_usage}%",
        "message": "System stabilny"
    }), 200


@app.route('/break')
def break_system():
    global is_healthy
    is_healthy = False
    return jsonify({"message": "Zepsuto system. Endpoint /health zwraca teraz blad 500."}), 200


@app.route('/fix')
def fix_system():
    global is_healthy
    is_healthy = True
    return jsonify({"message": "Naprawiono system. Endpoint /health dziala normalnie."}), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)