ERA_SIZE = 7


def _monster(name, subtitle, image, accent, glow, deep, search_query, era):
    return {
        "name": name,
        "subtitle": subtitle,
        "image": f"monsters/{image}",
        "accent": accent,
        "glow": glow,
        "deep": deep,
        "searchQuery": search_query,
        "exploreLabel": f"EXPLORE {search_query.upper()} CARDS",
        "era": era,
    }


FEATURED_MONSTERS = (
    # Duel Monsters
    _monster("Blue-Eyes White Dragon", "Legendary Dragon", "blue-eyes.png", "#7DDCFF", "#FFFFFF", "#2B85C8", "Blue-Eyes", "DUEL MONSTERS"),
    _monster("Dark Magician", "Ultimate Wizard", "dark-magician.png", "#B96CFF", "#E5B1FF", "#4B2088", "Dark Magician", "DUEL MONSTERS"),
    _monster("Red-Eyes Black Dragon", "Ferocious Dragon", "red-eyes.png", "#FF4A3D", "#FF9187", "#4D0707", "Red-Eyes", "DUEL MONSTERS"),
    _monster("Exodia the Forbidden One", "Forbidden One", "Exodia.png", "#D8952F", "#FFD789", "#704013", "Exodia", "DUEL MONSTERS"),
    _monster("Slifer the Sky Dragon", "Egyptian God", "Slifer.png", "#FF3434", "#FF8A72", "#7D0909", "Slifer", "DUEL MONSTERS"),
    _monster("Obelisk the Tormentor", "Egyptian God", "obelisk.png", "#147BFF", "#7EDCFF", "#063A98", "Obelisk", "DUEL MONSTERS"),
    _monster("The Winged Dragon of Ra", "Egyptian God", "ra.png", "#FFAA00", "#FFF0A0", "#9A5700", "Winged Dragon of Ra", "DUEL MONSTERS"),

    # GX
    _monster("Elemental HERO Neos", "Neo-Spacian Hero", "elemental-hero-neos.png", "#79D7FF", "#FFFFFF", "#A9363B", "Neos", "GX"),
    _monster("Elemental HERO Flame Wingman", "Skyscraper Hero", "elemental-hero-flame-wingman.png", "#FF7747", "#74E7FF", "#8C2D14", "HERO", "GX"),
    _monster("Cyber Dragon", "Mechanical Evolution", "cyber-dragon.png.png", "#72E5FF", "#ECFFFF", "#2A6680", "Cyber Dragon", "GX"),
    _monster("Cyber End Dragon", "Cybernetic Behemoth", "Cyber End Dragon.png", "#8CDFFF", "#F6FFFF", "#355E7B", "Cyber Dragon", "GX"),
    _monster("Rainbow Dragon", "Crystal Vanguard", "rainbow-dragon.png.png", "#E9F7FF", "#DCA8FF", "#3B89A6", "Crystal Beast", "GX"),
    _monster("Yubel", "Eternal Nightmare", "yubel.png", "#D65BFF", "#FF79C9", "#59166F", "Yubel", "GX"),
    _monster("Armed Dragon LV10", "Thunderous LV Monster", "armed-dragon-lv10.png", "#FF9A45", "#FFE08D", "#843617", "Armed Dragon", "GX"),

    # 5D's
    _monster("Stardust Dragon", "Cosmic Synchro", "stardust-dragon.png", "#63E1FF", "#E6FCFF", "#3178A3", "Stardust", "5D'S"),
    _monster("Red Dragon Archfiend", "Crimson King", "red-dragon-archfiend.png", "#F23F44", "#FF9A80", "#6F101B", "Red Dragon Archfiend", "5D'S"),
    _monster("Black Rose Dragon", "Rose Witch Dragon", "black-rose-dragon.png", "#F65E9D", "#FFC0DB", "#762249", "Rose Dragon", "5D'S"),
    _monster("Black-Winged Dragon", "Dark Wing Synchro", "black-winged-dragon.png", "#7C8DFF", "#C8D0FF", "#252A68", "Blackwing", "5D'S"),
    _monster("Ancient Fairy Dragon", "Spirit of the Forest", "ancient-fairy-dragon.png", "#85EDB9", "#EEFFD8", "#33785A", "Ancient Fairy", "5D'S"),
    _monster("Life Stream Dragon", "Courageous Synchro", "life-stream-dragon.png", "#5FD5A7", "#ECFFB5", "#2C6D50", "Morphtronic", "5D'S"),
    _monster("Shooting Star Dragon", "Accel Synchro", "shooting-star-dragon.png", "#6BBFFF", "#FFFFFF", "#344C9C", "Stardust", "5D'S"),

    # ZEXAL
    _monster("Number 39: Utopia", "King of Wishes", "number-39-utopia.png", "#F4D45D", "#FFFFFF", "#8D6C19", "Utopia", "ZEXAL"),
    _monster("Number C39: Utopia Ray", "Chaos of Hope", "number-c39-utopia-ray.png", "#EBAA42", "#FFF4C2", "#7D3F20", "Utopia", "ZEXAL"),
    _monster("Galaxy-Eyes Photon Dragon", "Photon Vanguard", "galaxy-eyes-photon-dragon.png", "#789DFF", "#D8D8FF", "#3D2D91", "Galaxy-Eyes", "ZEXAL"),
    _monster("Number 62: Galaxy-Eyes Prime Photon Dragon", "Prime Photon", "number-62-galaxy-eyes-prime-photon-dragon.png", "#739EFF", "#E4E2FF", "#372B92", "Galaxy-Eyes", "ZEXAL"),
    _monster("Number 32: Shark Drake", "Predator of the Deep", "number-32-shark-drake.png", "#42C9E8", "#B8FAFF", "#205D85", "Shark", "ZEXAL"),
    _monster("Number 107: Galaxy-Eyes Tachyon Dragon", "Master of Tachyon", "number-107-galaxy-eyes-tachyon-dragon.png", "#A15FFF", "#E0C7FF", "#412074", "Tachyon", "ZEXAL"),
    _monster("Number 101: Silent Honor ARK", "Silent Overseer", "number-101-silent-honor-ark.png", "#4FC7FF", "#D7F6FF", "#23547A", "Number 101", "ZEXAL"),

    # ARC-V
    _monster("Odd-Eyes Pendulum Dragon", "Pendulum Dragon", "odd-eyes-pendulum-dragon.png", "#F24F62", "#BF7CFF", "#591A5E", "Odd-Eyes", "ARC-V"),
    _monster("Dark Rebellion Xyz Dragon", "Rebellious Fang", "dark-rebellion-xyz-dragon.png", "#8B51FF", "#D6B4FF", "#32135F", "Dark Rebellion", "ARC-V"),
    _monster("Clear Wing Synchro Dragon", "Crystal Wing", "clear-wing-synchro-dragon.png", "#53E3D1", "#C8FFF5", "#246B6C", "Clear Wing", "ARC-V"),
    _monster("Starving Venom Fusion Dragon", "Venomous Fusion", "starving-venom-fusion-dragon.png", "#C34EFF", "#FF8DD6", "#541668", "Starving Venom", "ARC-V"),
    _monster("D/D/D Doom King Armageddon", "Abyssal King", "ddd-doom-king-armageddon.png", "#AF57FF", "#FF8D8D", "#4E1D68", "D/D/D", "ARC-V"),
    _monster("Raidraptor - Rise Falcon", "Revolution Falcon", "raidraptor-rise-falcon.png", "#D24D61", "#FFB0A4", "#591B2E", "Raidraptor", "ARC-V"),
    _monster("Frightfur Bear", "Toybox Nightmare", "frightfur-bear.png", "#E85E99", "#FFD0E7", "#71304E", "Frightfur", "ARC-V"),

    # VRAINS
    _monster("Decode Talker", "Code Talker", "decode-talker.png", "#38D9FF", "#D8FBFF", "#1D5A8B", "Code Talker", "VRAINS"),
    _monster("Firewall Dragon", "Cyberse Guardian", "firewall-dragon.png", "#43C8FF", "#E8FFFF", "#214B9D", "Firewall", "VRAINS"),
    _monster("Borreload Dragon", "Topologic Revolver", "borreload-dragon.png", "#456EFF", "#FF6868", "#1D245C", "Borrel", "VRAINS"),
    _monster("Salamangreat Heatleo", "Burning Cyberse", "salamangreat-heatleo.png", "#FF7B32", "#FFD077", "#8D2714", "Salamangreat", "VRAINS"),
    _monster("The Arrival Cyberse @Ignister", "Ultimate Ignister", "the-arrival-cyberse-ignister.png", "#B8F8FF", "#FFFFFF", "#5266A5", "@Ignister", "VRAINS"),
    _monster("Gouki The Great Ogre", "Champion of the Ring", "gouki-the-great-ogre.png", "#E9A645", "#FFE29A", "#774018", "Gouki", "VRAINS"),
    _monster("Trickstar Holly Angel", "Radiant Trickstar", "trickstar-holly-angel.png.png", "#FF6EC7", "#FFE0F5", "#7B285A", "Trickstar", "VRAINS"),
)
