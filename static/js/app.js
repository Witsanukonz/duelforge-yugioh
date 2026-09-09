(() => {
    const toggle = document.querySelector("[data-nav-toggle]");
    const nav = document.querySelector("[data-nav]");
    if (toggle && nav) {
        toggle.addEventListener("click", () => {
            const open = nav.classList.toggle("is-open");
            toggle.setAttribute("aria-expanded", String(open));
        });
    }

    const csrfToken = () => {
        const value = document.cookie
            .split("; ")
            .find((cookie) => cookie.startsWith("csrftoken="));
        return value ? decodeURIComponent(value.split("=")[1]) : "";
    };

    window.deckBuilder = {
        csrfToken,
        async json(url, options = {}) {
            const response = await fetch(url, {
                credentials: "same-origin",
                ...options,
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken(),
                    ...(options.headers || {}),
                },
            });
            const payload = response.status === 204 ? {} : await response.json();
            if (!response.ok) {
                const error = new Error(payload.error || "Request failed");
                error.payload = payload;
                throw error;
            }
            return payload;
        },
    };

    const preview = document.createElement("dialog");
    preview.className = "card-preview";
    preview.setAttribute("aria-label", "Card preview");
    preview.innerHTML = `
        <button class="card-preview__close" type="button" aria-label="ปิดภาพขยาย">×</button>
        <div class="card-preview__frame">
            <img alt="">
            <strong></strong>
            <span>กด Esc หรือคลิกด้านนอกเพื่อปิด</span>
        </div>
    `;
    document.body.appendChild(preview);

    const previewImage = preview.querySelector("img");
    const previewName = preview.querySelector("strong");

    function openCardPreview(trigger) {
        const image = trigger.matches("img") ? trigger : trigger.querySelector("img");
        if (!image) return;
        previewImage.src = trigger.dataset.cardZoomSrc || image.currentSrc || image.src;
        previewImage.alt = trigger.dataset.cardName || image.alt || "Card";
        previewName.textContent = trigger.dataset.cardName || image.alt || "Card";
        if (!preview.open) preview.showModal();
    }

    document.addEventListener("click", (event) => {
        const trigger = event.target.closest("[data-card-zoom]");
        if (!trigger || event.target.closest("button")) return;
        event.preventDefault();
        openCardPreview(trigger);
    });

    document.addEventListener("keydown", (event) => {
        if (!["Enter", " "].includes(event.key)) return;
        const trigger = event.target.closest('[data-card-zoom][role="button"]');
        if (!trigger) return;
        event.preventDefault();
        openCardPreview(trigger);
    });

    preview.querySelector(".card-preview__close").addEventListener("click", () => preview.close());
    preview.addEventListener("click", (event) => {
        if (event.target === preview) preview.close();
    });
    preview.addEventListener("close", () => {
        previewImage.removeAttribute("src");
    });

    document.querySelectorAll("[data-flash-close]").forEach((button) => {
        button.addEventListener("click", () => button.closest("[data-flash]")?.remove());
    });

    const authMonster = document.querySelector("[data-auth-monster]");
    const authStory = authMonster?.closest(".auth-story");
    const precisePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (authMonster && authStory && precisePointer.matches && !reducedMotion.matches) {
        let frame;
        let bounds;
        authStory.addEventListener("pointerenter", () => {
            bounds = authStory.getBoundingClientRect();
        });
        authStory.addEventListener("pointermove", (event) => {
            if (!bounds) return;
            const x = (event.clientX - bounds.left) / bounds.width - 0.5;
            const y = (event.clientY - bounds.top) / bounds.height - 0.5;
            window.cancelAnimationFrame(frame);
            frame = window.requestAnimationFrame(() => {
                authMonster.style.setProperty("--auth-x", `${x * 7}px`);
                authMonster.style.setProperty("--auth-y", `${y * 5}px`);
                authMonster.style.setProperty("--auth-rx", `${y * -1.6}deg`);
                authMonster.style.setProperty("--auth-ry", `${x * 2.2}deg`);
            });
        });
        authStory.addEventListener("pointerleave", () => {
            bounds = null;
            authMonster.style.setProperty("--auth-x", "0px");
            authMonster.style.setProperty("--auth-y", "0px");
            authMonster.style.setProperty("--auth-rx", "0deg");
            authMonster.style.setProperty("--auth-ry", "0deg");
        });
    }

    const musicPlayer = document.querySelector("[data-music-player]");
    if (musicPlayer) {
        const audio = musicPlayer.querySelector("[data-music-audio]");
        const playlistData = musicPlayer.querySelector("[data-music-playlist]");
        const title = musicPlayer.querySelector("[data-music-title]");
        const playButton = musicPlayer.querySelector("[data-music-toggle]");
        const playIcon = musicPlayer.querySelector("[data-music-toggle-icon]");
        const previousButton = musicPlayer.querySelector("[data-music-previous]");
        const nextButton = musicPlayer.querySelector("[data-music-next]");
        const powerButton = musicPlayer.querySelector("[data-music-power]");
        const status = musicPlayer.querySelector("[data-music-status]");
        const progress = musicPlayer.querySelector("[data-music-progress]");
        const currentTime = musicPlayer.querySelector("[data-music-current]");
        const duration = musicPlayer.querySelector("[data-music-duration]");
        const position = musicPlayer.querySelector("[data-music-position]");
        const muteButton = musicPlayer.querySelector("[data-music-mute]");
        const volume = musicPlayer.querySelector("[data-music-volume]");
        const collapseButton = musicPlayer.querySelector("[data-music-collapse]");
        const expandButton = musicPlayer.querySelector("[data-music-expand]");
        let tracks = [];
        let trackIndex = 0;
        let autoplayArmed = false;
        let pendingSeekTime = 0;
        let playAfterMetadata = false;
        let lastPlaybackSave = 0;
        let lastKnownTime = 0;
        let playbackRequested = true;
        let musicEnabled = window.localStorage.getItem("deckMusicEnabled") !== "off";
        let savedPlayback = null;

        try {
            savedPlayback = JSON.parse(window.localStorage.getItem("deckMusicPlayback") || "null");
        } catch (error) {
            savedPlayback = null;
        }
        playbackRequested = savedPlayback?.playing !== false;

        try {
            volume.value = window.localStorage.getItem("deckMusicVolume") || "0.7";
        } catch (error) {
            volume.value = "0.7";
        }

        const formatTime = (seconds) => {
            if (!Number.isFinite(seconds)) return "0:00";
            const minutes = Math.floor(seconds / 60);
            const remainder = Math.floor(seconds % 60).toString().padStart(2, "0");
            return `${minutes}:${remainder}`;
        };

        const savePlaybackState = () => {
            if (!tracks.length || !audio.src) return;
            const liveTime = Number.isFinite(audio.currentTime) && audio.currentTime > 0
                ? audio.currentTime
                : lastKnownTime;
            window.localStorage.setItem("deckMusicPlayback", JSON.stringify({
                src: tracks[trackIndex]?.src || audio.src,
                time: liveTime,
                playing: musicEnabled && playbackRequested,
                savedAt: Date.now(),
            }));
        };

        const setPlayingState = (playing) => {
            musicPlayer.classList.toggle("is-playing", playing);
            playIcon.textContent = playing ? "Ⅱ" : "▶";
            playButton.setAttribute("aria-label", playing ? "หยุดเพลงชั่วคราว" : "เล่นเพลง");
            status.textContent = playing ? "กำลังเล่น" : "พร้อมเล่น";
        };

        const setControlsDisabled = (disabled) => {
            [playButton, previousButton, nextButton, progress, muteButton, volume].forEach((control) => {
                control.disabled = disabled;
            });
        };

        const updatePowerState = () => {
            musicPlayer.classList.toggle("is-off", !musicEnabled);
            powerButton.setAttribute("aria-pressed", String(musicEnabled));
            powerButton.setAttribute("aria-label", musicEnabled ? "ปิดเพลง" : "เปิดเพลง");
            setControlsDisabled(!musicEnabled || !tracks.length);
            if (!musicEnabled) {
                status.textContent = "ปิดเพลงอยู่";
            } else if (!tracks.length) {
                status.textContent = "ยังไม่ได้ใส่ไฟล์เพลง";
            } else if (audio.paused) {
                status.textContent = "พร้อมเล่น";
            }
        };

        const setReadyState = () => {
            musicPlayer.classList.remove("is-unavailable");
            audio.volume = Number(volume.value);
            updatePowerState();
            if (musicEnabled) status.textContent = "พร้อมเล่น";
        };

        const setUnavailableState = () => {
            musicPlayer.classList.add("is-unavailable");
            setControlsDisabled(true);
            updatePowerState();
        };

        const disarmAutoplay = () => {
            if (!autoplayArmed) return;
            document.removeEventListener("pointerdown", resumeAutoplay);
            document.removeEventListener("keydown", resumeAutoplay);
            autoplayArmed = false;
        };

        const armAutoplay = () => {
            if (autoplayArmed) return;
            autoplayArmed = true;
            status.textContent = "คลิกหน้าเว็บหนึ่งครั้งเพื่อเริ่มเพลง";
            document.addEventListener("pointerdown", resumeAutoplay);
            document.addEventListener("keydown", resumeAutoplay);
        };

        async function tryToPlay() {
            if (!musicEnabled || !playbackRequested || !audio.src || !tracks.length) return;
            try {
                await audio.play();
                disarmAutoplay();
            } catch (error) {
                if (error?.name === "NotAllowedError") {
                    armAutoplay();
                } else {
                    status.textContent = "เบราว์เซอร์ไม่สามารถเล่นไฟล์นี้ได้";
                }
            }
        }

        function resumeAutoplay() {
            if (!musicEnabled) return;
            tryToPlay();
        }

        const loadTrack = (index, shouldPlay = false, startAt = 0) => {
            if (!tracks.length) return;
            if (shouldPlay) playbackRequested = true;
            trackIndex = (index + tracks.length) % tracks.length;
            const track = tracks[trackIndex];
            pendingSeekTime = Math.max(0, Number(startAt) || 0);
            lastKnownTime = pendingSeekTime;
            playAfterMetadata = shouldPlay;
            audio.src = track.src;
            title.textContent = track.title;
            position.textContent = `${trackIndex + 1} / ${tracks.length}`;
            currentTime.textContent = "0:00";
            duration.textContent = "0:00";
            progress.value = "0";
            window.localStorage.setItem("deckMusicTrack", String(trackIndex));
            audio.load();
            status.textContent = "กำลังโหลดเพลง…";
        };

        playButton.addEventListener("click", async () => {
            if (!audio.src) return;
            if (audio.paused) {
                playbackRequested = true;
                try {
                    await audio.play();
                } catch (error) {
                    status.textContent = "เบราว์เซอร์ไม่สามารถเล่นไฟล์นี้ได้";
                }
            } else {
                playbackRequested = false;
                audio.pause();
                savePlaybackState();
            }
        });

        audio.addEventListener("play", () => {
            setPlayingState(true);
            savePlaybackState();
        });
        audio.addEventListener("pause", () => {
            setPlayingState(false);
            savePlaybackState();
        });
        audio.addEventListener("ended", () => {
            lastKnownTime = 0;
            loadTrack(trackIndex + 1, true);
        });
        audio.addEventListener("loadedmetadata", () => {
            duration.textContent = formatTime(audio.duration);
            if (pendingSeekTime && audio.duration) {
                audio.currentTime = Math.min(pendingSeekTime % audio.duration, Math.max(0, audio.duration - 0.25));
                lastKnownTime = audio.currentTime;
            }
            pendingSeekTime = 0;
            if (playAfterMetadata) {
                playAfterMetadata = false;
                tryToPlay();
            }
        });
        audio.addEventListener("timeupdate", () => {
            lastKnownTime = audio.currentTime;
            currentTime.textContent = formatTime(audio.currentTime);
            progress.value = audio.duration ? String((audio.currentTime / audio.duration) * 100) : "0";
            if (Date.now() - lastPlaybackSave > 1000) {
                lastPlaybackSave = Date.now();
                savePlaybackState();
            }
        });
        audio.addEventListener("error", setUnavailableState);

        previousButton.addEventListener("click", () => loadTrack(trackIndex - 1, true));
        nextButton.addEventListener("click", () => loadTrack(trackIndex + 1, true));

        powerButton.addEventListener("click", () => {
            musicEnabled = !musicEnabled;
            playbackRequested = musicEnabled;
            window.localStorage.setItem("deckMusicEnabled", musicEnabled ? "on" : "off");
            if (!musicEnabled) {
                audio.pause();
                disarmAutoplay();
            }
            updatePowerState();
            if (musicEnabled && tracks.length) tryToPlay();
        });

        progress.addEventListener("input", () => {
            if (!audio.duration) return;
            audio.currentTime = (Number(progress.value) / 100) * audio.duration;
            lastKnownTime = audio.currentTime;
            savePlaybackState();
        });

        volume.addEventListener("input", () => {
            audio.volume = Number(volume.value);
            window.localStorage.setItem("deckMusicVolume", volume.value);
            audio.muted = audio.volume === 0;
            muteButton.textContent = audio.muted ? "×" : "♪";
        });

        muteButton.addEventListener("click", () => {
            audio.muted = !audio.muted;
            muteButton.textContent = audio.muted ? "×" : "♪";
            muteButton.setAttribute("aria-label", audio.muted ? "เปิดเสียง" : "ปิดเสียง");
        });

        collapseButton.addEventListener("click", () => {
            const collapsed = musicPlayer.classList.toggle("is-collapsed");
            window.localStorage.setItem("deckMusicCollapsed", collapsed ? "yes" : "no");
            collapseButton.textContent = collapsed ? "+" : "−";
            collapseButton.setAttribute("aria-expanded", String(!collapsed));
            collapseButton.setAttribute("aria-label", collapsed ? "ขยายเครื่องเล่นเพลง" : "ย่อเครื่องเล่นเพลง");
        });

        expandButton.addEventListener("click", () => {
            if (!musicPlayer.classList.contains("is-collapsed")) return;
            musicPlayer.classList.remove("is-collapsed");
            window.localStorage.setItem("deckMusicCollapsed", "no");
            collapseButton.textContent = "−";
            collapseButton.setAttribute("aria-expanded", "true");
            collapseButton.setAttribute("aria-label", "ย่อเครื่องเล่นเพลง");
        });

        if (window.localStorage.getItem("deckMusicCollapsed") === "yes") {
            musicPlayer.classList.add("is-collapsed");
            collapseButton.textContent = "+";
            collapseButton.setAttribute("aria-expanded", "false");
            collapseButton.setAttribute("aria-label", "ขยายเครื่องเล่นเพลง");
        }

        window.addEventListener("pagehide", savePlaybackState);
        document.addEventListener("visibilitychange", () => {
            if (document.hidden) {
                savePlaybackState();
            } else if (musicEnabled && playbackRequested && audio.paused) {
                tryToPlay();
            }
        });

        let playlist = [];
        try {
            playlist = JSON.parse(playlistData?.textContent || "[]");
        } catch (error) {
            playlist = [];
        }

        if (!playlist.length) {
            setUnavailableState();
        } else {
            Promise.all(playlist.map(async (track) => {
                try {
                    const response = await fetch(track.src, { method: "HEAD", cache: "no-store", credentials: "same-origin" });
                    return response.ok ? track : null;
                } catch (error) {
                    return null;
                }
            })).then((availableTracks) => {
                tracks = availableTracks.filter(Boolean);
                if (!tracks.length) {
                    setUnavailableState();
                    return;
                }
                const savedTrack = Number(window.localStorage.getItem("deckMusicTrack") || 0);
                const restoredTrack = savedPlayback?.src
                    ? tracks.findIndex((track) => track.src === savedPlayback.src)
                    : -1;
                const restoredIndex = restoredTrack >= 0 ? restoredTrack : Math.min(savedTrack, tracks.length - 1);
                const elapsed = savedPlayback?.playing && savedPlayback?.savedAt
                    ? Math.max(0, (Date.now() - savedPlayback.savedAt) / 1000)
                    : 0;
                const restoredTime = Math.max(0, Number(savedPlayback?.time) || 0) + elapsed;
                const restorePlaying = musicEnabled && savedPlayback?.playing !== false;
                playbackRequested = restorePlaying;
                setReadyState();
                loadTrack(restoredIndex, restorePlaying, restoredTime);
            });
        }
    }
})();
