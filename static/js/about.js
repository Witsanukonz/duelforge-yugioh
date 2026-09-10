(() => {
    const switcher = document.querySelector("[data-about-language-switch]");
    if (!switcher) return;

    const buttons = [...switcher.querySelectorAll("[data-language-option]")];
    const copies = [...document.querySelectorAll("[data-language-copy]")];

    const setLanguage = (language) => {
        copies.forEach((copy) => {
            copy.hidden = copy.dataset.languageCopy !== language;
        });

        buttons.forEach((button) => {
            const isActive = button.dataset.languageOption === language;
            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-pressed", String(isActive));
        });

        document.documentElement.lang = language;
    };

    buttons.forEach((button) => {
        button.addEventListener("click", () => setLanguage(button.dataset.languageOption));
    });

    setLanguage("en");
})();
