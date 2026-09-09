import hashlib
import io
import json
import re
import unicodedata
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .ydk import YDKParseError, parse_ydk


SOURCE_REPOSITORY = "https://github.com/isaiasgv/yugi-decks"
SOURCE_BRANCH = "main"
SOURCE_ARCHIVE_URL = (
    "https://codeload.github.com/isaiasgv/yugi-decks/zip/refs/heads/main"
)
SOURCE_NAME = "isaiasgv/yugi-decks"
SOURCE_LOCAL_ROOT = "isaiasgv-yugi-decks"
MANIFEST_FILENAME = "source_manifest.json"
METADATA_FILENAME = "metadata.json"
LICENSE_STATUS = (
    "No standalone license or GitHub-detected SPDX license was present when "
    "the downloader was implemented. The upstream README states that card data "
    "is copyright Konami and the repository contains deck-list passcode references."
)

SUPPORTED_ERAS = {
    "dm": {"code": "DM", "name": "Duel Monsters"},
    "gx": {"code": "GX", "name": "Yu-Gi-Oh! GX"},
    "5ds": {"code": "5D'S", "name": "Yu-Gi-Oh! 5D's"},
    "zexal": {"code": "ZEXAL", "name": "Yu-Gi-Oh! Zexal"},
    "arcv": {"code": "ARC-V", "name": "Yu-Gi-Oh! Arc-V"},
    "vrains": {"code": "VRAINS", "name": "Yu-Gi-Oh! VRAINS"},
}


class SampleDeckDownloadError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpstreamDeck:
    source_path: str
    era_folder: str
    content: bytes


@dataclass
class SampleDeckDownloadResult:
    upstream_found: int = 0
    selected: int = 0
    rush_excluded: int = 0
    unsupported_excluded: int = 0
    downloaded: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: list[dict] = field(default_factory=list)


def fetch_source_archive(url=SOURCE_ARCHIVE_URL, *, timeout=60):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "YuGiOh-Deck-Builder-Sample-Downloader/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as error:
        raise SampleDeckDownloadError(f"Could not download {url}: {error}") from error


def inspect_source_archive(archive_bytes):
    selected = []
    upstream_found = 0
    rush_excluded = 0
    unsupported_excluded = 0
    try:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes))
    except (zipfile.BadZipFile, OSError) as error:
        raise SampleDeckDownloadError(f"Source archive is not a valid ZIP file: {error}") from error

    with archive:
        for member in sorted(archive.infolist(), key=lambda item: item.filename.lower()):
            if member.is_dir() or not member.filename.lower().endswith(".ydk"):
                continue
            parts = PurePosixPath(member.filename).parts
            try:
                decks_index = next(
                    index for index, part in enumerate(parts) if part.lower() == "decks"
                )
            except StopIteration:
                continue
            if len(parts) <= decks_index + 2:
                continue

            upstream_found += 1
            era_folder = parts[decks_index + 1].lower()
            source_path = "/".join(parts[decks_index:])
            if era_folder == "rush":
                rush_excluded += 1
                continue
            if era_folder not in SUPPORTED_ERAS:
                unsupported_excluded += 1
                continue
            selected.append(UpstreamDeck(
                source_path=source_path,
                era_folder=era_folder,
                content=archive.read(member),
            ))
    return selected, upstream_found, rush_excluded, unsupported_excluded


def slugify_filename(value):
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug or "deck"


def readable_deck_name(source_path):
    stem = PurePosixPath(source_path).stem.strip()
    match = re.fullmatch(r"(.+?)\s*\((.+)\)", stem)
    if match:
        return f"{match.group(1).strip()} — {match.group(2).strip()}"
    return stem


def source_descriptor(source_path):
    stem = PurePosixPath(source_path).stem.strip()
    match = re.fullmatch(r".+?\s*\((.+)\)", stem)
    return match.group(1).strip() if match else stem


def sha256_bytes(content):
    return hashlib.sha256(content).hexdigest()


def load_json_object(path, *, label):
    path = Path(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SampleDeckDownloadError(f"Could not read {label} at {path}: {error}") from error
    if not isinstance(payload, dict):
        raise SampleDeckDownloadError(f"{label} must contain a JSON object.")
    return payload


def safe_manifest_local_path(directory, relative_path):
    pure_path = PurePosixPath(relative_path)
    if pure_path.is_absolute() or ".." in pure_path.parts:
        raise SampleDeckDownloadError(f"Unsafe local path in source manifest: {relative_path}")
    target = (Path(directory) / Path(*pure_path.parts)).resolve()
    if not target.is_relative_to(Path(directory).resolve()):
        raise SampleDeckDownloadError(f"Unsafe local path in source manifest: {relative_path}")
    return target


def atomic_write_bytes(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def atomic_write_json(path, payload):
    content = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write_bytes(path, content)


def choose_local_path(deck, directory, manifest_files, reserved_paths):
    previous = manifest_files.get(deck.source_path, {})
    previous_path = previous.get("local_path") if isinstance(previous, dict) else None
    if previous_path:
        target = safe_manifest_local_path(directory, previous_path)
        reserved_paths.add(previous_path.lower())
        return previous_path, target

    slug = slugify_filename(PurePosixPath(deck.source_path).stem)
    relative = PurePosixPath(SOURCE_LOCAL_ROOT, deck.era_folder, f"{slug}.ydk").as_posix()
    target = safe_manifest_local_path(directory, relative)
    owned_paths = {
        str(item.get("local_path", "")).lower()
        for item in manifest_files.values()
        if isinstance(item, dict)
    }
    if relative.lower() in reserved_paths or (target.exists() and relative.lower() not in owned_paths):
        suffix = hashlib.sha256(deck.source_path.encode("utf-8")).hexdigest()[:10]
        relative = PurePosixPath(
            SOURCE_LOCAL_ROOT,
            deck.era_folder,
            f"{slug}-{suffix}.ydk",
        ).as_posix()
        target = safe_manifest_local_path(directory, relative)
    reserved_paths.add(relative.lower())
    return relative, target


def download_sample_decks(directory, *, archive_bytes=None, timeout=60, fetcher=None):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / MANIFEST_FILENAME
    metadata_path = directory / METADATA_FILENAME
    manifest = load_json_object(manifest_path, label="source manifest")
    metadata = load_json_object(metadata_path, label="sample deck metadata")
    manifest_files = manifest.get("files", {})
    if not isinstance(manifest_files, dict):
        raise SampleDeckDownloadError("source manifest files must be a JSON object.")

    if archive_bytes is None:
        fetcher = fetcher or fetch_source_archive
        archive_bytes = fetcher(timeout=timeout)
    selected, found, rush, unsupported = inspect_source_archive(archive_bytes)
    result = SampleDeckDownloadResult(
        upstream_found=found,
        selected=len(selected),
        rush_excluded=rush,
        unsupported_excluded=unsupported,
    )
    updated_manifest_files = dict(manifest_files)
    updated_metadata = dict(metadata)
    reserved_paths = {
        str(item.get("local_path", "")).lower()
        for item in manifest_files.values()
        if isinstance(item, dict) and item.get("local_path")
    }

    for deck in selected:
        try:
            text = deck.content.decode("utf-8-sig")
            parse_ydk(text)
            relative_path, local_path = choose_local_path(
                deck, directory, manifest_files, reserved_paths
            )
            digest = sha256_bytes(deck.content)
            if local_path.exists():
                if sha256_bytes(local_path.read_bytes()) == digest:
                    result.unchanged += 1
                else:
                    atomic_write_bytes(local_path, deck.content)
                    result.updated += 1
            else:
                atomic_write_bytes(local_path, deck.content)
                result.downloaded += 1

            era = SUPPORTED_ERAS[deck.era_folder]
            metadata_key = local_path.stem
            updated_metadata[metadata_key] = {
                "name": readable_deck_name(deck.source_path),
                "era": era["code"],
                "archetype": source_descriptor(deck.source_path),
                "format": "TCG",
                "source": SOURCE_NAME,
                "source_path": deck.source_path,
                "description": (
                    f"Character deck from the {era['name']} era. "
                    f"Source: {SOURCE_NAME}."
                ),
            }
            updated_manifest_files[deck.source_path] = {
                "local_path": relative_path,
                "era": era["code"],
                "sha256": digest,
            }
        except (UnicodeDecodeError, YDKParseError, OSError, SampleDeckDownloadError) as error:
            result.failed.append({"source_path": deck.source_path, "reason": str(error)})

    updated_manifest = {
        "source_repository": SOURCE_REPOSITORY,
        "source_branch": SOURCE_BRANCH,
        "source_archive": SOURCE_ARCHIVE_URL,
        "license_status": LICENSE_STATUS,
        "files": updated_manifest_files,
    }
    atomic_write_json(metadata_path, updated_metadata)
    atomic_write_json(manifest_path, updated_manifest)
    return result
