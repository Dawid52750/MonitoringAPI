from flask import Flask, jsonify
import os

app = Flask(__name__)

# Globalna zmienna określająca stan serwera
is_healthy = True

@app.route('/')
def home():
    """Główny endpoint aplikacji"""
    return jsonify({"message": "Witaj w aplikacji medycznej. System dziala poprawnie."}), 200

@app.route('/health')
def health_check():
    """Endpoint, który będzie sprawdzany przez system monitoringu"""
    global is_healthy
    if is_healthy:
        return jsonify({"status": "OK", "uptime": "100%"}), 200
    else:
        # Ten kod zwróci błąd HTTP 500, co uruchomi alarm w UptimeRobot
        return jsonify({"status": "ERROR", "message": "Awaria bazy danych!"}), 500

@app.route('/break')
def break_system():
    """Ukryty endpoint do celowego wywołania awarii"""
    global is_healthy
    is_healthy = False
    return jsonify({"message": "Zepsuto system. Endpoint /health zwraca teraz blad 500."}), 200

@app.route('/fix')
def fix_system():
    """Ukryty endpoint do naprawy awarii"""
    global is_healthy
    is_healthy = True
    return jsonify({"message": "Naprawiono system. Endpoint /health dziala normalnie."}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
