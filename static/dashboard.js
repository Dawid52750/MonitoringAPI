let resourcesChart = null;
let latencyChart = null;
let refreshTimer = null;

function formatTime(isoString) {
    if (!isoString) return "-";
    return new Date(isoString).toLocaleTimeString("pl-PL");
}

function formatDateTime(isoString) {
    if (!isoString) return "-";
    return new Date(isoString).toLocaleString("pl-PL");
}

function setBar(barId, valId, percent) {
    const clamped = Math.max(0, Math.min(100, Number(percent) || 0));
    const bar = document.getElementById(barId);
    bar.style.width = clamped + "%";
    if (clamped >= 85) {
        bar.style.backgroundColor = "#dc2626";
    } else if (clamped >= 65) {
        bar.style.backgroundColor = "#d97706";
    } else {
        bar.style.backgroundColor = "#2563eb";
    }
    document.getElementById(valId).textContent = clamped.toFixed(1) + "%";
}

function updateCharts(historyItems) {
    const ordered = [...historyItems].reverse();
    const labels = ordered.map((item) => formatTime(item.timestamp));
    const cpuData = ordered.map((item) => item.cpu_percent);
    const ramData = ordered.map((item) => item.ram_percent);
    const diskData = ordered.map((item) => item.disk_percent);
    const latencyData = ordered.map((item) => item.response_time_ms);

    const resCtx = document.getElementById("resourcesChart").getContext("2d");
    if (resourcesChart) {
        resourcesChart.data.labels = labels;
        resourcesChart.data.datasets[0].data = cpuData;
        resourcesChart.data.datasets[1].data = ramData;
        resourcesChart.data.datasets[2].data = diskData;
        resourcesChart.update();
    } else {
        resourcesChart = new Chart(resCtx, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    { label: "CPU (%)", data: cpuData, borderColor: "#2563eb", tension: 0.25 },
                    { label: "RAM (%)", data: ramData, borderColor: "#16a34a", tension: 0.25 },
                    { label: "Dysk (%)", data: diskData, borderColor: "#d97706", tension: 0.25 }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { y: { min: 0, max: 100 } }
            }
        });
    }

    const latCtx = document.getElementById("latencyChart").getContext("2d");
    if (latencyChart) {
        latencyChart.data.labels = labels;
        latencyChart.data.datasets[0].data = latencyData;
        latencyChart.update();
    } else {
        latencyChart = new Chart(latCtx, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Czas odpowiedzi (ms)",
                        data: latencyData,
                        borderColor: "#7c3aed",
                        backgroundColor: "rgba(124, 58, 237, 0.12)",
                        fill: true,
                        tension: 0.25
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { y: { beginAtZero: true } }
            }
        });
    }
}

function renderIncidents(items) {
    const tbody = document.getElementById("incidentsBody");
    if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="6">Brak zarejestrowanych incydentów.</td></tr>';
        return;
    }
    tbody.innerHTML = items
        .map((inc) => {
            const pillClass = inc.status === "RESOLVED" ? "pill-ok" : "pill-error";
            const duration = inc.duration_seconds !== null ? inc.duration_seconds : "w trakcie";
            return `<tr>
                <td>#${inc.id}</td>
                <td>${formatDateTime(inc.started_at)}</td>
                <td>${formatDateTime(inc.resolved_at)}</td>
                <td>${duration}</td>
                <td>${inc.reason}</td>
                <td><span class="pill ${pillClass}">${inc.status}</span></td>
            </tr>`;
        })
        .join("");
}

function renderHistory(items) {
    const tbody = document.getElementById("historyBody");
    if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="7">Brak zapisanych pomiarów.</td></tr>';
        return;
    }
    tbody.innerHTML = items
        .slice(0, 15)
        .map((row) => {
            const pillClass = row.status === "OK" ? "pill-ok" : "pill-error";
            return `<tr>
                <td>${formatDateTime(row.timestamp)}</td>
                <td><span class="pill ${pillClass}">${row.status}</span></td>
                <td>${row.http_code}</td>
                <td>${row.cpu_percent}%</td>
                <td>${row.ram_percent}%</td>
                <td>${row.disk_percent}%</td>
                <td>${row.response_time_ms} ms</td>
            </tr>`;
        })
        .join("");
}

async function loadDashboardData() {
    const [statsRes, histRes, incRes] = await Promise.all([
        fetch("/api/stats"),
        fetch("/api/history?limit=30"),
        fetch("/api/incidents?limit=20")
    ]);

    const stats = await statsRes.json();
    const historyData = await histRes.json();
    const incidentsData = await incRes.json();
    const historyItems = historyData.items || [];
    const incidentItems = incidentsData.items || [];

    document.getElementById("kpiAvailability").textContent = stats.availability_percent + "%";
    document.getElementById("kpiChecks").textContent = `${stats.successful_checks} / ${stats.total_checks} pomiarów OK`;
    document.getElementById("kpiMttr").textContent = stats.avg_mttr_seconds + " s";
    document.getElementById("kpiIncidents").textContent = `Incydenty: ${stats.total_incidents} (aktywne: ${stats.open_incidents})`;
    document.getElementById("kpiLatency").textContent = stats.avg_response_time_ms + " ms";

    if (historyItems.length > 0) {
        const latest = historyItems[0];
        setBar("barCpu", "valCpu", latest.cpu_percent);
        setBar("barRam", "valRam", latest.ram_percent);
        setBar("barDisk", "valDisk", latest.disk_percent);

        const badge = document.getElementById("statusBadge");
        if (latest.status === "OK") {
            badge.textContent = "STATUS: OK (200)";
            badge.className = "badge badge-ok";
        } else {
            badge.textContent = "STATUS: AWARIA (500)";
            badge.className = "badge badge-error";
        }
    }

    updateCharts(historyItems);
    renderIncidents(incidentItems);
    renderHistory(historyItems);
}

async function triggerHealthCheck() {
    await fetch("/health");
    await loadDashboardData();
}

async function sendControlAction(endpoint) {
    const apiKey = document.getElementById("apiKeyInput").value.trim();
    const reason = document.getElementById("reasonInput").value.trim();
    const feedback = document.getElementById("actionFeedback");

    const response = await fetch(endpoint, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-API-Key": apiKey
        },
        body: JSON.stringify({ reason: reason })
    });

    const data = await response.json();
    if (response.ok) {
        feedback.textContent = `Sukces (${response.status}): ${data.message}`;
        feedback.className = "feedback feedback-ok";
        await triggerHealthCheck();
    } else {
        feedback.textContent = `Błąd (${response.status}): ${data.message}`;
        feedback.className = "feedback feedback-error";
    }
}

function setupAutoRefresh() {
    const toggle = document.getElementById("autoRefreshToggle");
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
    if (toggle.checked) {
        refreshTimer = setInterval(triggerHealthCheck, 10000);
    }
}

document.getElementById("checkNowBtn").addEventListener("click", triggerHealthCheck);
document.getElementById("breakBtn").addEventListener("click", () => sendControlAction("/break"));
document.getElementById("fixBtn").addEventListener("click", () => sendControlAction("/fix"));
document.getElementById("autoRefreshToggle").addEventListener("change", setupAutoRefresh);

triggerHealthCheck();
setupAutoRefresh();