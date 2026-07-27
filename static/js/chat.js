(() => {
    const launcher = document.getElementById("chat-launcher");
    const panel = document.getElementById("chat-panel");
    if (!launcher || !panel) return; // chat widget not on this page

    const closeBtn = document.getElementById("chat-close");
    const messages = document.getElementById("chat-messages");
    const form = document.getElementById("chat-form");
    const input = document.getElementById("chat-input");

    const GREETING = "Hi, I'm the HydroShield assistant. Ask me about a field's readings, watering schedules, or anything else.";

    function addRow(text, who) {
        const row = document.createElement("div");
        row.className = "chat-row " + who;

        const avatar = document.createElement("div");
        avatar.className = "chat-avatar";
        avatar.textContent = who === "user" ? "You" : "HS";

        const bubble = document.createElement("div");
        bubble.className = "chat-bubble";
        bubble.textContent = text;

        row.append(avatar, bubble);
        messages.appendChild(row);
        messages.scrollTop = messages.scrollHeight;
        return bubble;
    }

    let opened = false;
    function openPanel() {
        panel.classList.add("open");
        if (!opened) {
            addRow(GREETING, "bot");
            opened = true;
        }
        input.focus();
    }
    function closePanel() { panel.classList.remove("open"); }

    launcher.addEventListener("click", () => {
        panel.classList.contains("open") ? closePanel() : openPanel();
    });
    closeBtn.addEventListener("click", closePanel);

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text) return;

        addRow(text, "user");
        input.value = "";

        const pending = addRow("", "bot");
        pending.classList.add("typing");
        pending.innerHTML = "<span></span><span></span><span></span>";

        try {
            const res = await fetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text }),
            });
            const data = await res.json();
            pending.classList.remove("typing");
            pending.textContent = data.reply;
        } catch {
            pending.classList.remove("typing");
            pending.textContent = "Something went wrong. Please try again.";
        }
        messages.scrollTop = messages.scrollHeight;
    });
})();
