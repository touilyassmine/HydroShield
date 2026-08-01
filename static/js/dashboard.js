(() => {
    const CIRCUMFERENCE = 163.36;
    let refreshInterval = null;

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
        card.querySelector('[data-role="rain-val"]').textContent = f.last_rain ? "Detected" : "None";

        card.querySelector('[data-role="auto-checkbox"]').checked = !!f.auto_mode;
    }

    // ---------- FETCH LATEST DATA FOR A SINGLE FIELD ----------
    async function refreshField(card) {
        const fieldId = card.dataset.fieldId;
        try {
            const res = await fetch(`/api/fields/${fieldId}`);
            if (!res.ok) return;
            const field = await res.json();
            applyFieldState(card, field);
        } catch (e) {
            // silent fail – keep old data
        }
    }

    // ---------- REFRESH ALL FIELDS ----------
    async function refreshAllFields() {
        const cards = document.querySelectorAll(".field-card");
        for (const card of cards) {
            await refreshField(card);
        }
    }

    // ---------- SETUP EVENT LISTENERS ----------
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

    // ---------- START AUTO-REFRESH ----------
    if (document.querySelector(".field-card")) {
        // Initial refresh
        refreshAllFields();

        // Refresh every 5 seconds (5000 ms)
        refreshInterval = setInterval(refreshAllFields, 5000);

        // Optional: stop refreshing when the page is hidden (saves resources)
        document.addEventListener("visibilitychange", () => {
            if (document.hidden) {
                clearInterval(refreshInterval);
            } else {
                refreshInterval = setInterval(refreshAllFields, 5000);
            }
        });
    }
})();
