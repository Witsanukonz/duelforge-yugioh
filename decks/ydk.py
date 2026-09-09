from collections import Counter
from dataclasses import dataclass
from pathlib import Path


SECTION_MARKERS = {
    "#main": "MAIN",
    "#extra": "EXTRA",
    "!side": "SIDE",
}
SECTION_ORDER = tuple(SECTION_MARKERS.values())
SECTION_HEADERS = {section: marker for marker, section in SECTION_MARKERS.items()}


class YDKParseError(ValueError):
    def __init__(self, errors):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class ParsedYDK:
    sections: dict[str, Counter]
    creator: str = ""

    @property
    def totals(self):
        return {
            section: sum(cards.values())
            for section, cards in self.sections.items()
        }

    @property
    def unique_card_ids(self):
        return {
            card_id
            for cards in self.sections.values()
            for card_id in cards
        }


def parse_ydk(text):
    sections = {section: Counter() for section in SECTION_ORDER}
    current_section = None
    creator = ""
    errors = []

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        marker = line.lower()
        if marker in SECTION_MARKERS:
            current_section = SECTION_MARKERS[marker]
            continue
        if marker.startswith("#created by"):
            creator = line[len("#created by"):].strip()
            continue
        if line.startswith("#"):
            continue
        if line.startswith("!"):
            errors.append(f"Line {line_number}: unknown section marker {line!r}.")
            continue
        if current_section is None:
            errors.append(f"Line {line_number}: card ID appears before a deck section.")
            continue
        if not line.isdecimal() or int(line) <= 0:
            errors.append(f"Line {line_number}: invalid card ID {line!r}.")
            continue

        sections[current_section][int(line)] += 1

    if errors:
        raise YDKParseError(errors)
    if not any(sections.values()):
        raise YDKParseError(["The .ydk file contains no card IDs."])
    return ParsedYDK(sections=sections, creator=creator)


def parse_ydk_file(path):
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise YDKParseError([f"Could not read {path}: {error}"]) from error
    return parse_ydk(text)


def serialize_ydk(sections, *, creator="DUELFORGE"):
    """Serialize section card counts to the standard YGOPro .ydk text format."""
    lines = []
    if creator:
        lines.append(f"#created by {creator}")

    for section in SECTION_ORDER:
        lines.append(SECTION_HEADERS[section])
        for card_id, quantity in sections.get(section, {}).items():
            lines.extend([str(card_id)] * quantity)

    return "\n".join(lines) + "\n"
