import time
import psutil
from config import Config

START_TIME = time.time()


def collect_system_metrics():
    ram_usage = psutil.virtual_memory().percent
    cpu_usage = psutil.cpu_percent(interval=0.1)
    disk_usage = psutil.disk_usage("/").percent
    uptime_seconds = round(time.time() - START_TIME, 2)

    return {
        "ram_percent": ram_usage,
        "cpu_percent": cpu_usage,
        "disk_percent": disk_usage,
        "uptime_seconds": uptime_seconds,
    }


def evaluate_health(metrics, is_healthy, failure_reason):
    if not is_healthy:
        return False, failure_reason

    if metrics["ram_percent"] > Config.RAM_THRESHOLD:
        return False, f"Krytyczne zuzycie pamieci RAM: {metrics['ram_percent']}%"

    if metrics["cpu_percent"] > Config.CPU_THRESHOLD:
        return False, f"Krytyczne obciazenie procesora CPU: {metrics['cpu_percent']}%"

    if metrics["disk_percent"] > Config.DISK_THRESHOLD:
        return False, f"Krytyczne zapelnienie dysku: {metrics['disk_percent']}%"

    return True, "System stabilny"