(async () => {
    const root = document.querySelector("[data-builder]");
    if (!root) return;

    const canEdit = root.dataset.canEdit === "true";
    let deckId = root.dataset.deckId || null;
    const initialNode = document.querySelector("#deck-data");
    let deck = initialNode ? JSON.parse(initialNode.textContent) : {
        name: "",
        description: "",
        deck_type: "",
        format: "TCG",
        ban_list: null,
        is_public: false,
        cards: [],
        counts: {MAIN: 0, EXTRA: 0, SIDE: 0},
    };
    const feedback = document.querySelector("[data-builder-feedback]");
    const title = document.querySelector("[data-deck-title]");
    const saveButton = document.querySelector("[data-save-deck]");
    const deleteButton = document.querySelector("[data-delete-deck]");
    const rulesetSelect = document.querySelector('[data-field="ruleset"]');
    const searchInput = document.querySelector("[data-card-search]");
    const results = document.querySelector("[data-search-results]");
    const dropZones = Array.from(document.querySelectorAll("[data-drop-zone]"));
    const validationPanel = document.querySelector("[data-validation]");
    const legalityStatus = document.querySelector("[data-legality-status]");
    const banListMeta = document.querySelector("[data-banlist-meta]");
    let searchTimer;
    let activeSearch = null;
    let draggedCard = null;
    let lastValidation = null;
    let suppressCardClick = false;

    const escapeHtml = (value) => String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");

    function openCardDetail(cardId) {
        const returnUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
        window.location.assign(`/cards/${encodeURIComponent(cardId)}/?return=${encodeURIComponent(returnUrl)}`);
    }

    function formPayload() {
        const selectedRuleset = rulesetSelect.selectedOptions[0];
        return {
            name: document.querySelector('[data-field="name"]').value.trim(),
            description: document.querySelector('[data-field="description"]').value.trim(),
            deck_type: document.querySelector('[data-field="deck_type"]').value.trim(),
            format: selectedRuleset?.dataset.format || deck.format || "TCG",
            ban_list: rulesetSelect.value || null,
            is_public: document.querySelector('[data-field="is_public"]').checked,
        };
    }

    function formatEffectiveDate(value) {
        if (!value) return "ไม่ระบุวันที่มีผล";
        return new Intl.DateTimeFormat("th-TH", {
            day: "numeric", month: "short", year: "numeric",
        }).format(new Date(`${value}T00:00:00`));
    }

    function updateBanListMeta() {
        if (!banListMeta || !rulesetSelect) return;
        const option = rulesetSelect.selectedOptions[0];
        banListMeta.textContent = option?.value
            ? `${option.dataset.name} · มีผล ${formatEffectiveDate(option.dataset.effective)}`
            : "N/A · ไม่ตรวจ Ban List";
    }

    function showFeedback(message, state = "") {
        if (!feedback) return;
        feedback.textContent = message;
        feedback.dataset.state = state;
    }

    async function saveDeck({quiet = false} = {}) {
        const payload = formPayload();
        if (!payload.name) {
            showFeedback("Give this deck a name first.", "error");
            document.querySelector('[data-field="name"]').focus();
            throw new Error("Deck name required");
        }
        const response = await window.deckBuilder.json(
            deckId ? `/api/decks/${deckId}/` : "/api/decks/",
            {method: deckId ? "PATCH" : "POST", body: JSON.stringify(payload)},
        );
        deck = {...deck, ...response.deck, cards: deck.cards || []};
        if (!deckId) {
            deckId = String(response.deck.id);
            root.dataset.deckId = deckId;
            window.history.replaceState({}, "", `/decks/${deckId}/`);
            if (saveButton) saveButton.textContent = "บันทึกเด็ค";
            if (deleteButton) deleteButton.hidden = false;
        }
        title.textContent = response.deck.name;
        if (!quiet) showFeedback("Deck saved to your vault.", "success");
        return deckId;
    }

    function renderDeck() {
        const counts = {MAIN: 0, EXTRA: 0, SIDE: 0};
        const violationsByCard = new Map(
            (lastValidation?.violations || [])
                .filter((violation) => violation.card_id)
                .map((violation) => [Number(violation.card_id), violation]),
        );
        ["MAIN", "EXTRA", "SIDE"].forEach((section) => {
            const zone = document.querySelector(`[data-zone-cards="${section}"]`);
            const entries = (deck.cards || []).filter((entry) => entry.section === section);
            counts[section] = entries.reduce((total, entry) => total + entry.quantity, 0);
            document.querySelector(`[data-count="${section}"]`).textContent = counts[section];
            if (!entries.length) {
                zone.innerHTML = `<p class="deck-zone__empty">${canEdit ? "Drop cards here" : "No cards in this section"}</p>`;
                return;
            }
            zone.innerHTML = entries.flatMap((entry) => {
                const violation = violationsByCard.get(Number(entry.card.card_id));
                const warning = violation
                    ? `${violation.status || violation.type}: ใช้ ${violation.used ?? "-"} / ได้ ${violation.allowed ?? "-"}`
                    : "";
                return Array.from({length: entry.quantity}, () => `
                    <article class="builder-card${violation ? " is-illegal" : ""}" data-entry-id="${entry.id}" data-extra-deck-card="${entry.card.is_extra_deck_card}" data-card-detail-id="${entry.card.card_id}" data-card-name="${escapeHtml(entry.card.name)}" role="link" tabindex="0" draggable="${canEdit}" title="${escapeHtml(warning ? `คลิกเพื่ออ่านเอฟเฟกต์ · ${warning}` : "คลิกเพื่ออ่านเอฟเฟกต์การ์ด")}">
                        <img src="${escapeHtml(entry.card.local_image_url)}" alt="${escapeHtml(entry.card.name)}">
                        <div class="builder-card__overlay"><span>${escapeHtml(entry.card.name)}</span></div>
                        ${violation ? `<span class="builder-card__warning">!</span>` : ""}
                        ${canEdit ? `<div class="builder-card__actions"><button type="button" data-remove-copy aria-label="นำการ์ดใบนี้ออก">×</button></div>` : ""}
                    </article>
                `);
            },
            ).join("");
        });
        deck.counts = counts;
    }

    async function addCard(cardId, section) {
        try {
            if (!deckId) await saveDeck({quiet: true});
            const existing = (deck.cards || []).find(
                (entry) => entry.card.card_id === cardId && entry.section === section,
            );
            if (existing?.quantity >= 3) {
                showFeedback(`${existing.card.name} already has the maximum of 3 copies.`, "error");
                return;
            }
            const quantity = existing ? Math.min(3, existing.quantity + 1) : 1;
            const response = await window.deckBuilder.json(`/api/decks/${deckId}/cards/`, {
                method: "POST",
                body: JSON.stringify({card_id: cardId, section, quantity}),
            });
            if (existing) Object.assign(existing, response.deck_card);
            else deck.cards.push(response.deck_card);
            renderDeck();
            await refreshValidation({quiet: true});
            showFeedback(`Added ${response.deck_card.card.name} to ${section.toLowerCase()}.`, "success");
        } catch (error) {
            showFeedback(error.payload?.error ? `${error.payload.error} ${JSON.stringify(error.payload.details || "")}` : error.message, "error");
        }
    }

    function searchResultMarkup(card) {
        const status = card.ban_status;
        const statusLabel = status?.replace("_", "-");
        return `
            <article class="search-result-card" draggable="${canEdit}" data-search-card="${card.card_id}" data-extra-deck-card="${card.is_extra_deck_card}" data-card-name="${escapeHtml(card.name)}" data-card-detail-id="${card.card_id}" role="link" tabindex="0" title="คลิกเพื่ออ่านเอฟเฟกต์ · ลากไปวางในโซนเด็ค">
                <img src="${escapeHtml(card.local_image_url)}" alt="${escapeHtml(card.name)}" loading="lazy">
                <div class="search-result-card__caption"><strong>${escapeHtml(card.name)}</strong><span>${escapeHtml(card.card_type)}</span></div>
                ${status ? `<span class="ban-status-badge ban-status-badge--${status.toLowerCase()}">${statusLabel}</span>` : ""}
                <span class="search-result-card__drag" aria-hidden="true">↗</span>
            </article>
        `;
    }

    function updateSearchProgress(state) {
        const grid = results.querySelector("[data-search-grid]");
        const summary = results.querySelector("[data-search-summary]");
        const footer = results.querySelector("[data-search-footer]");
        const loaded = grid?.children.length || 0;
        if (summary) summary.textContent = `แสดง ${loaded} จาก ${state.total} ใบ`;
        if (footer) {
            footer.textContent = state.page < state.pages
                ? "เลื่อนลงเพื่อดูการ์ดเพิ่มเติม"
                : `แสดงครบทั้ง ${state.total} ใบแล้ว`;
        }
    }

    async function loadNextSearchPage(state) {
        if (!state || state !== activeSearch || state.loading || state.page >= state.pages) return;
        state.loading = true;
        const nextPage = state.page + 1;
        try {
            const banListParameter = state.banListId ? `&ban_list=${encodeURIComponent(state.banListId)}` : "";
            const response = await fetch(`/api/cards/?q=${encodeURIComponent(state.query)}&page_size=30&page=${nextPage}${banListParameter}`);
            if (!response.ok) throw new Error("Card search failed");
            const payload = await response.json();
            if (state !== activeSearch) return;

            state.page = payload.pagination.page;
            state.pages = payload.pagination.pages;
            state.total = payload.pagination.total;
            if (nextPage === 1) {
                if (!payload.results.length) {
                    results.innerHTML = '<p class="panel-hint">ไม่พบการ์ด ลองใช้ชื่อที่สั้นลงหรือสะกดใหม่</p>';
                    return;
                }
                results.innerHTML = `
                    <p class="search-result-summary" data-search-summary></p>
                    <div class="search-result-grid" data-search-grid>${payload.results.map(searchResultMarkup).join("")}</div>
                    <p class="search-result-footer" data-search-footer></p>
                `;
            } else {
                results.querySelector("[data-search-grid]")?.insertAdjacentHTML(
                    "beforeend",
                    payload.results.map(searchResultMarkup).join(""),
                );
            }
            updateSearchProgress(state);
        } catch {
            if (state !== activeSearch) return;
            const footer = results.querySelector("[data-search-footer]");
            if (footer) footer.textContent = "โหลดการ์ดเพิ่มเติมไม่สำเร็จ ลองเลื่อนอีกครั้ง";
            else results.innerHTML = '<p class="panel-hint">ไม่สามารถค้นหาการ์ดได้ในขณะนี้</p>';
        } finally {
            state.loading = false;
        }
    }

    function searchCards(query) {
        if (query.length < 2) {
            activeSearch = null;
            results.innerHTML = '<p class="panel-hint">พิมพ์อย่างน้อย 2 ตัวอักษรเพื่อค้นหา</p>';
            return;
        }
        results.innerHTML = '<p class="panel-hint">กำลังค้นหาการ์ด…</p>';
        activeSearch = {query, banListId: rulesetSelect?.value || "", page: 0, pages: 1, total: 0, loading: false};
        loadNextSearchPage(activeSearch);
    }

    async function removeCopy(entryId) {
        const entry = deck.cards.find((item) => item.id === Number(entryId));
        if (!entry) return;
        if (entry.quantity === 1) {
            await window.deckBuilder.json(`/api/decks/${deckId}/cards/${entry.id}/`, {method: "DELETE"});
            deck.cards = deck.cards.filter((item) => item.id !== entry.id);
        } else {
            const response = await window.deckBuilder.json(`/api/decks/${deckId}/cards/${entry.id}/`, {
                method: "PATCH",
                body: JSON.stringify({quantity: entry.quantity - 1}),
            });
            Object.assign(entry, response.deck_card);
        }
        renderDeck();
        await refreshValidation({quiet: true});
    }

    async function moveEntry(entryId, section) {
        const entry = deck.cards.find((item) => item.id === Number(entryId));
        if (!entry || entry.section === section) return;
        try {
            const response = await window.deckBuilder.json(`/api/decks/${deckId}/cards/${entry.id}/`, {
                method: "PATCH",
                body: JSON.stringify({section, move_quantity: 1}),
            });
            deck.cards = response.deck_cards;
            renderDeck();
            await refreshValidation({quiet: true});
            showFeedback(`Moved one copy of ${entry.card.name} to ${section.toLowerCase()}.`, "success");
        } catch (error) {
            showFeedback(error.payload?.error ? `${error.payload.error} ${JSON.stringify(error.payload.details || "")}` : error.message, "error");
        }
    }

    function sectionAllowsCard(section, isExtraDeckCard) {
        return isExtraDeckCard ? section === "EXTRA" : section !== "EXTRA";
    }

    function clearDragState() {
        document.querySelectorAll(".is-dragging").forEach((element) => element.classList.remove("is-dragging"));
        dropZones.forEach((zone) => zone.classList.remove("is-drop-ready", "is-drop-invalid", "is-drop-active"));
        root.classList.remove("has-active-drag");
        draggedCard = null;
    }

    function beginDrag(event, payload, sourceElement) {
        suppressCardClick = true;
        draggedCard = payload;
        sourceElement.classList.add("is-dragging");
        root.classList.add("has-active-drag");
        event.dataTransfer.effectAllowed = payload.source === "deck" ? "move" : "copy";
        event.dataTransfer.setData("text/plain", JSON.stringify(payload));
        dropZones.forEach((zone) => {
            const allowed = sectionAllowsCard(zone.dataset.section, payload.isExtraDeckCard);
            zone.classList.toggle("is-drop-ready", allowed);
            zone.classList.toggle("is-drop-invalid", !allowed);
        });
    }

    function applyValidation(report) {
        lastValidation = report;
        if (!validationPanel || !legalityStatus) return;
        const draftIssue = report.violations.find(
            (item) => item.code === "main_deck_size" && item.used < item.allowed_min,
        );
        const blockingViolations = report.violations.filter((item) => item !== draftIssue);
        const isDraft = Boolean(draftIssue) && blockingViolations.length === 0;
        validationPanel.classList.toggle("is-valid", report.is_legal);
        validationPanel.classList.toggle("is-draft", isDraft);
        validationPanel.classList.toggle("is-invalid", !report.is_legal && !isDraft);
        legalityStatus.textContent = report.is_legal
            ? "พร้อมใช้งาน"
            : isDraft ? "กำลังจัดเด็ค" : "ต้องแก้ไข";
        const message = validationPanel.querySelector("p");
        if (report.is_legal) {
            message.textContent = report.banlist
                ? `${report.format} · ${report.banlist.name} · ผ่านกฎเด็คทั้งหมด`
                : `${report.format} · N/A · ผ่านกฎจำนวนและตำแหน่งการ์ด`;
        } else if (isDraft) {
            message.textContent = `บันทึกได้ · Main Deck มี ${report.counts.MAIN} / 40 ใบ`;
        } else {
            const cardViolations = blockingViolations.filter((item) => item.card_id).length;
            const summary = blockingViolations.slice(0, 2).map((item) => item.message).join(" ");
            message.textContent = `${blockingViolations.length} จุดที่ต้องแก้${cardViolations ? ` · การ์ด ${cardViolations} รายการ` : ""} — ${summary}`;
        }
        renderDeck();
    }

    async function refreshValidation({quiet = false} = {}) {
        if (!deckId) return;
        try {
            const response = await fetch(`/api/decks/${deckId}/validate/`);
            if (!response.ok) throw new Error("Deck validation failed");
            applyValidation((await response.json()).validation);
        } catch (error) {
            if (!quiet) showFeedback(error.message, "error");
        }
    }

    async function persistRuleSelection() {
        updateBanListMeta();
        lastValidation = null;
        renderDeck();
        if (searchInput?.value.trim().length >= 2) searchCards(searchInput.value.trim());
        if (!deckId || !canEdit) return;
        try {
            await saveDeck({quiet: true});
            await refreshValidation({quiet: true});
            showFeedback("อัปเดต Ban List แล้ว", "success");
        } catch (error) {
            showFeedback(error.payload?.error || error.message, "error");
        }
    }

    saveButton?.addEventListener("click", async () => {
        saveButton.disabled = true;
        try {
            await saveDeck();
            await refreshValidation({quiet: true});
        }
        catch (error) { if (error.payload) showFeedback(error.message, "error"); }
        finally { saveButton.disabled = false; }
    });

    rulesetSelect?.addEventListener("change", persistRuleSelection);

    deleteButton?.addEventListener("click", async () => {
        const confirmed = window.confirm(`ลบเด็ค “${deck.name}” ถาวรหรือไม่?`);
        if (!confirmed) return;
        deleteButton.disabled = true;
        try {
            await window.deckBuilder.json(`/api/decks/${deckId}/`, {method: "DELETE"});
            window.location.assign("/decks/");
        } catch (error) {
            showFeedback(error.payload?.error || "ลบเด็คไม่สำเร็จ", "error");
            deleteButton.disabled = false;
        }
    });

    searchInput?.addEventListener("input", () => {
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(() => searchCards(searchInput.value.trim()), 280);
    });

    results?.addEventListener("scroll", () => {
        if (results.scrollTop + results.clientHeight >= results.scrollHeight - 180) {
            loadNextSearchPage(activeSearch);
        }
    });

    results?.addEventListener("dragstart", (event) => {
        const card = event.target.closest("[data-search-card]");
        if (!card || !canEdit) return;
        beginDrag(event, {
            source: "search",
            cardId: Number(card.dataset.searchCard),
            cardName: card.dataset.cardName,
            isExtraDeckCard: card.dataset.extraDeckCard === "true",
        }, card);
    });

    root.addEventListener("dragstart", (event) => {
        const card = event.target.closest("[data-entry-id]");
        if (!card || !canEdit) return;
        const entry = deck.cards.find((item) => item.id === Number(card.dataset.entryId));
        if (!entry) return;
        beginDrag(event, {
            source: "deck",
            entryId: entry.id,
            cardName: entry.card.name,
            isExtraDeckCard: entry.card.is_extra_deck_card,
        }, card);
    });

    root.addEventListener("dragend", () => {
        clearDragState();
        window.setTimeout(() => { suppressCardClick = false; }, 0);
    });

    dropZones.forEach((zone) => {
        zone.addEventListener("dragover", (event) => {
            if (!draggedCard || !sectionAllowsCard(zone.dataset.section, draggedCard.isExtraDeckCard)) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = draggedCard.source === "deck" ? "move" : "copy";
            zone.classList.add("is-drop-active");
        });
        zone.addEventListener("dragleave", (event) => {
            if (!event.relatedTarget || !zone.contains(event.relatedTarget)) {
                zone.classList.remove("is-drop-active");
            }
        });
        zone.addEventListener("drop", async (event) => {
            if (!draggedCard || !sectionAllowsCard(zone.dataset.section, draggedCard.isExtraDeckCard)) return;
            event.preventDefault();
            const payload = draggedCard;
            const section = zone.dataset.section;
            clearDragState();
            if (payload.source === "search") await addCard(payload.cardId, section);
            if (payload.source === "deck") await moveEntry(payload.entryId, section);
        });
    });

    root.addEventListener("click", async (event) => {
        const removeButton = event.target.closest("[data-remove-copy]");
        if (removeButton) {
            const card = removeButton.closest("[data-entry-id]");
            if (!card) return;
            try { await removeCopy(card.dataset.entryId); }
            catch (error) { showFeedback(error.payload?.error || "Could not update this card.", "error"); }
            return;
        }

        const card = event.target.closest("[data-card-detail-id]");
        if (!card || suppressCardClick) return;
        openCardDetail(card.dataset.cardDetailId);
    });

    root.addEventListener("keydown", (event) => {
        if (!['Enter', ' '].includes(event.key) || event.target.closest("button")) return;
        const card = event.target.closest("[data-card-detail-id]");
        if (!card) return;
        event.preventDefault();
        openCardDetail(card.dataset.cardDetailId);
    });

    document.querySelector("[data-validate]")?.addEventListener("click", () => refreshValidation());

    updateBanListMeta();
    if (deckId) {
        await refreshValidation({quiet: true});
        if (deck.cards?.length && !document.querySelector("[data-entry-id]")) renderDeck();
    } else {
        renderDeck();
    }
})();
