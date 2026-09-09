(() => {
    const carousel = document.querySelector("[data-carousel]");
    const dataElement = document.getElementById("featured-monsters-data");
    if (!carousel || !dataElement) return;

    const monsters = JSON.parse(dataElement.textContent);
    if (!monsters.length) return;

    const pageSize = 7;
    const pageCount = Math.ceil(monsters.length / pageSize);
    const stage = carousel.querySelector("[data-monster-stage]");
    const infoPanel = carousel.querySelector(".monster-info");
    const nameElement = carousel.querySelector("[data-monster-name]");
    const typeElement = carousel.querySelector("[data-monster-type]");
    const eraElement = carousel.querySelector("[data-monster-era]");
    const counter = carousel.querySelector("[data-counter]");
    const indicatorContainer = carousel.querySelector("[data-era-indicators]");
    const exploreLink = carousel.querySelector("[data-explore-link]");
    const dustField = carousel.querySelector("[data-dust-field]");
    const menuToggle = carousel.querySelector("[data-home-nav-toggle]");
    const desktopNav = carousel.querySelector(".desktop-nav");
    const transitionDuration = 650;
    const loadedPages = new Set();
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    let activeIndex = 0;
    let isAnimating = false;
    let isMobile = window.innerWidth < 640;
    let autoplayTimer;
    let touchStartX = 0;
    let pointerFrame;
    let pointerRect;

    const slides = monsters.map((monster, index) => {
        const slide = document.createElement("article");
        slide.className = "monster-slide";
        slide.dataset.index = String(index);
        slide.dataset.name = monster.name;
        slide.dataset.accent = monster.accent;
        slide.style.setProperty("--glow-primary", monster.accent);
        slide.style.setProperty("--glow-secondary", monster.glow);
        slide.style.setProperty("--glow-deep", monster.deep);
        slide.innerHTML = `
            <a class="monster-link" href="${monster.exploreUrl}" aria-label="${monster.exploreLabel}">
                <span class="monster-glow" aria-hidden="true"></span>
                <span class="monster-sigil" aria-hidden="true"></span>
                <img class="monster-image" alt="${monster.name}" decoding="async">
                <span class="monster-fallback" aria-hidden="true"><b>◇</b><small>${monster.name}</small></span>
                <span class="monster-energy" aria-hidden="true"></span>
            </a>
        `;
        stage.appendChild(slide);
        return slide;
    });

    const eras = [...new Set(monsters.map((monster) => monster.era))];
    eras.forEach((era, pageIndex) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "carousel-indicator";
        button.setAttribute("aria-label", `Show ${era} monsters`);
        button.title = era;
        button.addEventListener("click", () => goTo(pageIndex * pageSize));
        indicatorContainer.appendChild(button);
    });
    const indicators = [...indicatorContainer.children];

    function loadPage(pageIndex) {
        const normalizedPage = (pageIndex + pageCount) % pageCount;
        if (loadedPages.has(normalizedPage)) return;
        loadedPages.add(normalizedPage);

        const start = normalizedPage * pageSize;
        monsters.slice(start, start + pageSize).forEach((monster, offset) => {
            const slide = slides[start + offset];
            const image = slide.querySelector(".monster-image");
            image.addEventListener("load", () => slide.classList.add("is-loaded"), { once: true });
            image.addEventListener("error", () => {
                slide.classList.add("is-loaded", "has-image-error");
                image.removeAttribute("src");
            }, { once: true });
            image.src = monster.imageUrl;
        });
    }

    function preparePages() {
        const pageIndex = Math.floor(activeIndex / pageSize);
        loadPage(pageIndex);
        if (activeIndex % pageSize >= pageSize - 3) loadPage(pageIndex + 1);
    }

    function relativePosition(index) {
        let distance = (index - activeIndex + slides.length) % slides.length;
        if (distance > Math.floor(slides.length / 2)) distance -= slides.length;
        return distance;
    }

    function updateGlow() {
        const monster = monsters[activeIndex];
        carousel.style.setProperty("--active-accent", monster.accent);
        dustField.style.setProperty("--particle-color", monster.accent);
    }

    function writeMonsterInfo() {
        const monster = monsters[activeIndex];
        nameElement.textContent = monster.name;
        typeElement.textContent = monster.subtitle;
        eraElement.textContent = monster.era;
        exploreLink.textContent = monster.exploreLabel;
        exploreLink.href = monster.exploreUrl;
    }

    function updateMonsterInfo(animate = true) {
        if (!animate || reduceMotion.matches) {
            writeMonsterInfo();
            return;
        }
        infoPanel.classList.add("is-changing");
        window.setTimeout(() => {
            writeMonsterInfo();
            infoPanel.classList.remove("is-changing");
        }, 180);
    }

    function updateCounter() {
        counter.textContent = `${String(activeIndex + 1).padStart(2, "0")} / ${String(monsters.length).padStart(2, "0")}`;
        const activePage = Math.floor(activeIndex / pageSize);
        indicators.forEach((indicator, index) => {
            const isActive = index === activePage;
            indicator.classList.toggle("is-active", isActive);
            indicator.setAttribute("aria-current", isActive ? "true" : "false");
        });
    }

    function updateCarousel(animateInfo = true) {
        preparePages();
        slides.forEach((slide, index) => {
            const position = relativePosition(index);
            slide.classList.remove("is-active", "is-prev", "is-next", "is-far-prev", "is-far-next");
            slide.setAttribute("aria-hidden", position === 0 ? "false" : "true");
            slide.querySelector(".monster-link").tabIndex = position === 0 ? 0 : -1;

            if (position === 0) slide.classList.add("is-active");
            else if (position === -1) slide.classList.add("is-prev");
            else if (position === 1) slide.classList.add("is-next");
            else if (!isMobile && position === -2) slide.classList.add("is-far-prev");
            else if (!isMobile && position === 2) slide.classList.add("is-far-next");
        });
        updateGlow();
        updateMonsterInfo(animateInfo);
        updateCounter();
    }

    function navigate(direction) {
        if (isAnimating) return;
        isAnimating = true;
        activeIndex = direction === "next"
            ? (activeIndex + 1) % slides.length
            : (activeIndex - 1 + slides.length) % slides.length;
        updateCarousel();
        resetAutoplay();
        window.setTimeout(() => { isAnimating = false; }, transitionDuration);
    }

    function goTo(index) {
        if (isAnimating || index === activeIndex) return;
        isAnimating = true;
        activeIndex = (index + slides.length) % slides.length;
        updateCarousel();
        resetAutoplay();
        window.setTimeout(() => { isAnimating = false; }, transitionDuration);
    }

    function resetPointer() {
        pointerRect = null;
        carousel.style.setProperty("--pointer-x", "0px");
        carousel.style.setProperty("--pointer-y", "0px");
        carousel.style.setProperty("--pointer-rotate-x", "0deg");
        carousel.style.setProperty("--pointer-rotate-y", "0deg");
    }

    stage.addEventListener("pointermove", (event) => {
        if (isMobile || reduceMotion.matches || event.pointerType === "touch") return;
        const link = event.target.closest(".monster-slide.is-active .monster-link");
        if (!link) return;
        if (!pointerRect) pointerRect = link.getBoundingClientRect();
        const x = (event.clientX - pointerRect.left) / pointerRect.width - 0.5;
        const y = (event.clientY - pointerRect.top) / pointerRect.height - 0.5;
        window.cancelAnimationFrame(pointerFrame);
        pointerFrame = window.requestAnimationFrame(() => {
            carousel.style.setProperty("--pointer-x", `${x * 8}px`);
            carousel.style.setProperty("--pointer-y", `${y * 6}px`);
            carousel.style.setProperty("--pointer-rotate-x", `${y * -2.4}deg`);
            carousel.style.setProperty("--pointer-rotate-y", `${x * 3.2}deg`);
        });
    });
    stage.addEventListener("pointerleave", resetPointer);

    function createDust() {
        const fragment = document.createDocumentFragment();
        const count = isMobile ? 18 : 34;
        dustField.replaceChildren();
        for (let i = 0; i < count; i += 1) {
            const particle = document.createElement("span");
            particle.className = "dust-particle";
            particle.style.left = `${5 + Math.random() * 90}%`;
            particle.style.setProperty("--size", `${1 + Math.random() * 2.4}px`);
            particle.style.setProperty("--duration", `${8 + Math.random() * 10}s`);
            particle.style.setProperty("--delay", `${Math.random() * -16}s`);
            particle.style.setProperty("--drift", `${-60 + Math.random() * 120}px`);
            particle.style.setProperty("--alpha", `${0.12 + Math.random() * 0.34}`);
            fragment.appendChild(particle);
        }
        dustField.appendChild(fragment);
    }

    function resetAutoplay() {
        window.clearInterval(autoplayTimer);
        if (!reduceMotion.matches) autoplayTimer = window.setInterval(() => navigate("next"), 8000);
    }

    carousel.querySelector("[data-carousel-prev]").addEventListener("click", () => navigate("prev"));
    carousel.querySelector("[data-carousel-next]").addEventListener("click", () => navigate("next"));

    menuToggle?.addEventListener("click", () => {
        const isOpen = desktopNav.classList.toggle("is-open");
        menuToggle.setAttribute("aria-expanded", String(isOpen));
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "ArrowLeft") navigate("prev");
        if (event.key === "ArrowRight") navigate("next");
    });

    carousel.addEventListener("touchstart", (event) => {
        touchStartX = event.changedTouches[0].clientX;
    }, { passive: true });
    carousel.addEventListener("touchend", (event) => {
        const distance = event.changedTouches[0].clientX - touchStartX;
        if (Math.abs(distance) > 48) navigate(distance > 0 ? "prev" : "next");
    }, { passive: true });

    window.addEventListener("resize", () => {
        const nextMobile = window.innerWidth < 640;
        if (nextMobile !== isMobile) {
            isMobile = nextMobile;
            createDust();
            resetPointer();
            updateCarousel(false);
        }
    });
    reduceMotion.addEventListener("change", () => {
        resetPointer();
        resetAutoplay();
    });

    loadPage(0);
    createDust();
    updateCarousel(false);
    resetAutoplay();
})();
