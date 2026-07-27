(() => {
    const cropLabelInput = document.getElementById("crop-label");
    const suggestList = document.getElementById("suggest-list");
    const nameInput = document.getElementById("field-name");
    const areaInput = document.getElementById("field-area");
    const ageInput = document.getElementById("field-age");
    const originInput = document.getElementById("field-origin");

    const photoInput = document.getElementById("photo-input");
    const photoPreview = document.getElementById("photo-preview");
    const photoDropText = document.getElementById("photo-drop-text");
    const aiResult = document.getElementById("ai-result");
    const healthResult = document.getElementById("health-result");

    const soilSelect = document.getElementById("soil-select");
    const soilPhotoInput = document.getElementById("soil-photo-input");
    const soilPhotoPreview = document.getElementById("soil-photo-preview");
    const soilPhotoDropText = document.getElementById("soil-photo-drop-text");
    const soilAiResult = document.getElementById("soil-ai-result");

    const addBtn = document.getElementById("add-field-btn");
    const addedList = document.getElementById("added-fields");
    const fieldCount = document.getElementById("field-count");
    const continueBtn = document.getElementById("continue-btn");

    let ageSource = "manual";
    let originSource = "manual";
    let soilSource = "manual";
    let healthStatus = null, healthNote = null, healthSource = "manual";
    let addedFields = [];
    let suggestTimer = null;

    async function fetchSuggestions(q) {
        try {
            const res = await fetch(`/api/plants/suggest?q=${encodeURIComponent(q)}`);
            return res.ok ? await res.json() : [];
        } catch {
            return [];
        }
    }

    function renderSuggestions(items) {
        if (!items.length) {
            suggestList.classList.remove("open");
            suggestList.innerHTML = "";
            return;
        }
        suggestList.innerHTML = items.map(label => `<div class="suggest-item">${label}</div>`).join("");
        suggestList.classList.add("open");
    }

    cropLabelInput.addEventListener("input", () => {
        clearTimeout(suggestTimer);
        const q = cropLabelInput.value.trim();
        if (q.length < 2) { renderSuggestions([]); return; }
        suggestTimer = setTimeout(async () => renderSuggestions(await fetchSuggestions(q)), 220);
    });

    suggestList.addEventListener("click", (e) => {
        const item = e.target.closest(".suggest-item");
        if (!item) return;
        cropLabelInput.value = item.textContent;
        renderSuggestions([]);
    });

    document.addEventListener("click", (e) => {
        if (!e.target.closest(".field-row") || !suggestList.contains(e.target)) {
            if (e.target !== cropLabelInput) renderSuggestions([]);
        }
    });

    function renderAiResult() {
        const bits = [];
        if (ageInput.value) bits.push(`<strong>${ageInput.value} days</strong> old`);
        if (originInput.value) bits.push(`likely from <strong>${originInput.value}</strong>`);
        if (bits.length) {
            aiResult.style.display = "flex";
            aiResult.innerHTML = `<span class="badge">AI</span><span>${bits.join(", ")}. Adjust anything that looks off.</span>`;
        }
    }

    function renderHealthResult() {
        if (!healthStatus) { healthResult.style.display = "none"; return; }
        healthResult.style.display = "flex";
        if (healthStatus === "healthy") {
            healthResult.innerHTML = `<span class="badge badge-good">OK</span><span>Looks healthy from the photo.</span>`;
        } else if (healthStatus === "possible_issue") {
            healthResult.innerHTML = `<span class="badge badge-warn">!</span><span>${healthNote || "Possible issue spotted in the photo."}</span>`;
        } else {
            healthResult.innerHTML = `<span class="badge">i</span><span>Couldn't tell from that photo — keep an eye on it.</span>`;
        }
    }

    photoInput.addEventListener("change", async () => {
        const file = photoInput.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = () => {
            photoPreview.src = reader.result;
            photoPreview.style.display = "block";
            photoDropText.textContent = file.name;
        };
        reader.readAsDataURL(file);

        if (!cropLabelInput.value.trim()) {
            aiResult.style.display = "flex";
            aiResult.innerHTML = `<span class="badge">i</span><span>Type the plant's name above first so the AI knows what it's looking at.</span>`;
            return;
        }

        aiResult.style.display = "flex";
        aiResult.innerHTML = `<span class="badge">AI</span><span>Analyzing the photo…</span>`;
        healthResult.style.display = "none";

        const formData = new FormData();
        formData.append("photo", file);
        formData.append("crop_label", cropLabelInput.value.trim());

        try {
            const res = await fetch("/api/analyze-photo", { method: "POST", body: formData });
            const data = await res.json();

            if (data.estimated_age_days) { ageInput.value = data.estimated_age_days; ageSource = "ai_photo"; }
            if (data.likely_origin) { originInput.value = data.likely_origin; originSource = "ai_photo"; }
            healthStatus = data.health_status || null;
            healthNote = data.health_note || null;
            healthSource = data.source === "ai_photo" ? "ai_photo" : "manual";

            if (data.estimated_age_days || data.likely_origin) {
                renderAiResult();
            } else {
                aiResult.innerHTML = `<span class="badge">i</span><span>${data.note || "Could not estimate from that photo — enter details manually."}</span>`;
            }
            renderHealthResult();
        } catch {
            aiResult.innerHTML = `<span class="badge">i</span><span>Analysis failed — enter details manually.</span>`;
        }
    });

    ageInput.addEventListener("input", () => { ageSource = "manual"; });
    originInput.addEventListener("input", () => { originSource = "manual"; });

    soilPhotoInput.addEventListener("change", async () => {
        const file = soilPhotoInput.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = () => {
            soilPhotoPreview.src = reader.result;
            soilPhotoPreview.style.display = "block";
            soilPhotoDropText.textContent = file.name;
        };
        reader.readAsDataURL(file);

        soilAiResult.style.display = "flex";
        soilAiResult.innerHTML = `<span class="badge">AI</span><span>Looking at the soil…</span>`;

        const formData = new FormData();
        formData.append("photo", file);

        try {
            const res = await fetch("/api/estimate-soil", { method: "POST", body: formData });
            const data = await res.json();
            if (data.soil_type) { soilSelect.value = data.soil_type; soilSource = "ai_photo"; }
            else { soilSource = "manual"; }
            soilAiResult.innerHTML = `<span class="badge">${data.soil_type ? "AI" : "i"}</span><span>${data.note || ""}</span>`;
        } catch {
            soilAiResult.innerHTML = `<span class="badge">i</span><span>Estimate failed — pick the soil type manually.</span>`;
        }
    });

    soilSelect.addEventListener("change", () => { soilSource = "manual"; });

    addBtn.addEventListener("click", async () => {
        const cropLabel = cropLabelInput.value.trim();
        if (!cropLabel) {
            alert("Tell us what plant is growing in this field first.");
            return;
        }
        addBtn.disabled = true;
        addBtn.textContent = "Adding…";

        const formData = new FormData();
        formData.append("crop_label", cropLabel);
        formData.append("name", nameInput.value.trim());
        if (areaInput.value) formData.append("area_hectares", areaInput.value);
        if (ageInput.value) formData.append("estimated_age_days", ageInput.value);
        formData.append("age_source", ageSource);
        if (originInput.value.trim()) formData.append("crop_origin", originInput.value.trim());
        formData.append("origin_source", originSource);
        if (soilSelect.value) formData.append("soil_type", soilSelect.value);
        formData.append("soil_source", soilSource);
        if (healthStatus) formData.append("health_status", healthStatus);
        if (healthNote) formData.append("health_note", healthNote);
        formData.append("health_source", healthSource);

        try {
            const res = await fetch("/api/fields", { method: "POST", body: formData });
            const field = await res.json();
            if (!res.ok) throw new Error(field.error || "Could not add field");

            addedFields.push(field);
            renderAddedFields();
            resetForm();
        } catch (err) {
            alert(err.message);
        } finally {
            addBtn.disabled = false;
            addBtn.textContent = "+ Add this field";
        }
    });

    function resetForm() {
        ageSource = "manual"; originSource = "manual"; soilSource = "manual";
        healthStatus = null; healthNote = null; healthSource = "manual";

        cropLabelInput.value = "";
        nameInput.value = "";
        areaInput.value = "";
        ageInput.value = "";
        originInput.value = "";

        photoInput.value = "";
        photoPreview.style.display = "none";
        photoDropText.textContent = "Tap to take or choose a photo of a plant in this field";
        aiResult.style.display = "none";
        healthResult.style.display = "none";

        soilSelect.value = "";
        soilPhotoInput.value = "";
        soilPhotoPreview.style.display = "none";
        soilPhotoDropText.textContent = "Optional: tap to take or choose a photo of the soil";
        soilAiResult.style.display = "none";
    }

    function renderAddedFields() {
        addedList.innerHTML = addedFields.map(f => `
            <div class="added-field-row" data-id="${f.id}">
                <img class="crop-icon" src="/static/img/crops/${f.icon}.svg" alt="">
                <div>
                    <strong>${f.name}</strong><br>
                    <span>${f.crop_label}${f.crop_origin ? " (" + f.crop_origin + ")" : ""}${f.area_hectares ? " · " + f.area_hectares + " ha" : ""}${f.estimated_age_days ? " · " + f.estimated_age_days + " days old" : ""}${f.soil_label ? " · " + f.soil_label.split(" — ")[0] + " soil" : ""}${f.health_status === "possible_issue" ? " · ⚠ possible issue" : ""}</span>
                </div>
                <span class="remove" data-id="${f.id}">Remove</span>
            </div>
        `).join("");
        fieldCount.textContent = `${addedFields.length} field${addedFields.length === 1 ? "" : "s"} added`;
        continueBtn.disabled = addedFields.length === 0;
    }

    addedList.addEventListener("click", async (e) => {
        const removeEl = e.target.closest(".remove");
        if (!removeEl) return;
        const id = removeEl.dataset.id;
        await fetch(`/api/fields/${id}`, { method: "DELETE" });
        addedFields = addedFields.filter(f => String(f.id) !== id);
        renderAddedFields();
    });

    continueBtn.addEventListener("click", () => {
        window.location.href = window.DASHBOARD_URL;
    });
})();
