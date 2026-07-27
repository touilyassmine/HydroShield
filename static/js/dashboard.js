(() => {
    const CIRCUMFERENCE = 163.36;

    function applyFieldState(card, f) {
        const pill = card.querySelector('[data-role="status-pill"]');
        pill.className = "status-pill " + (f.irrigation_on ? "on" : "off");
        pill.innerHTML = `<i></i>${f.irrigation_on ? "Irrigating" : "Idle"}`;

        const btn = card.querySelector('[data-role="irrigate-btn"]');
        btn.className = "irrigate-toggle " + (f.irrigation_on ? "is-on" : "is-off");
        btn.textContent = f.irrigation_on ? "■ Stop irrigation" : "▶ Start irrigation";

        const gaugeFill = card.querySelector('[data-role="gauge-fill"]');
        const pct = f.last_moisture != null ? f.last_moisture : 0;
        gaugeFill.setAttribute("stroke-dasharray", `${(pct / 100 * CIRCUMFERENCE).toFixed(1)} ${CIRCUMFERENCE}`);

        card.querySelector('[data-role="moisture-val"]').textContent =
            f.last_moisture != null ? `${f.last_moisture}%` : "—";
        card.querySelector('[data-role="temp-val"]').textContent =
            f.last_temperature != null ? `${f.last_temperature}°C` : "—";
        card.querySelector('[data-role="rain-val"]').textContent = f.last_rain ? "Detected" : "None";

        card.querySelector('[data-role="auto-checkbox"]').checked = !!f.auto_mode;
    }

    document.querySelectorAll(".field-card").forEach(card => {
        const fieldId = card.dataset.fieldId;

        card.querySelector('[data-role="irrigate-btn"]').addEventListener("click", async (e) => {
            const btn = e.currentTarget;
            btn.disabled = true;
            try {
                const res = await fetch(`/api/fields/${fieldId}/irrigation`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                });
                const field = await res.json();
                applyFieldState(card, field);
            } finally {
                btn.disabled = false;
            }
        });

        card.querySelector('[data-role="auto-checkbox"]').addEventListener("change", async (e) => {
            const res = await fetch(`/api/fields/${fieldId}/auto`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ auto: e.target.checked }),
            });
            const field = await res.json();
            applyFieldState(card, field);
        });
    });

    // Poll each field's latest sensor snapshot every 12s so cards stay live
    // once the ESP8266 boards start reporting.
    async function refreshAll() {
        const cards = document.querySelectorAll(".field-card");
        for (const card of cards) {
            const fieldId = card.dataset.fieldId;
            try {
                const res = await fetch(`/api/fields/${fieldId}`);
                if (!res.ok) continue;
                const field = await res.json();
                applyFieldState(card, field);
            } catch { /* skip a beat, try again next cycle */ }
        }
    }
    if (document.querySelector(".field-card")) {
        setInterval(refreshAll, 12000);
    }
})();
