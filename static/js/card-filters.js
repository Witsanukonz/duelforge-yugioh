(() => {
    const form = document.querySelector("[data-card-filters]");
    const cardType = form?.querySelector("[data-card-type]");
    if (!form || !cardType) return;

    const dependentFields = Array.from(form.querySelectorAll("[data-filter-for]"));

    function updateDependentFilters({ reset = false } = {}) {
        const selectedType = cardType.value;
        dependentFields.forEach((field) => {
            const select = field.querySelector("select");
            const isRelevant = field.dataset.filterFor === selectedType;

            if (!isRelevant && reset && select) select.value = "";
            field.hidden = !isRelevant;
            if (select) select.disabled = !isRelevant;

            if (isRelevant) {
                field.classList.remove("is-entering");
                window.requestAnimationFrame(() => field.classList.add("is-entering"));
            }
        });
    }

    cardType.addEventListener("change", () => updateDependentFilters({ reset: true }));
    updateDependentFilters();
})();
