import os


class Config:
    PORT = int(os.environ.get("PORT", 5000))
    API_KEY = os.environ.get("API_KEY", "dev-secret-key-2026")
    DB_PATH = os.environ.get("DB_PATH", "monitoring.db")
    RAM_THRESHOLD = float(os.environ.get("RAM_THRESHOLD", 90.0))
    CPU_THRESHOLD = float(os.environ.get("CPU_THRESHOLD", 85.0))
    DISK_THRESHOLD = float(os.environ.get("DISK_THRESHOLD", 90.0))
    SERVICE_NAME = os.environ.get("SERVICE_NAME", "Cloud Monitoring Node")