# Sample / Featured Deck Sources

This directory is the local, offline source for the Featured Deck Library.
The website reads only local files and the database; it never contacts an
upstream repository during a page request.

## Character deck source

- Repository: https://github.com/isaiasgv/yugi-decks
- Branch: `main`
- Included eras: Duel Monsters, GX, 5D's, ZEXAL, ARC-V, and VRAINS
- Excluded: `decks/rush/` because Rush Duel cards are outside this project's
  supported card pool and deck rules
- License note: no standalone license file or GitHub-detected SPDX license was
  present when this integration was implemented. The upstream README states
  that card data is copyright Konami; the repository itself contains `.ydk`
  deck-list passcodes. Keep the source attribution when redistributing the
  downloaded lists.

Downloaded files are stored under the downloader-owned directory:

```text
isaiasgv-yugi-decks/<era>/*.ydk
```

`source_manifest.json` records the upstream path, local path, era, checksum,
and attribution. `metadata.json` supplies display names and descriptions to the
existing importer. The downloader updates only files it owns through the
manifest and never deletes `.ydk` files added manually by a user.

## Commands

Download or update the local source files:

```console
python manage.py download_sample_decks
```

Import all local `.ydk` files into the Featured Deck Library:

```console
python manage.py import_sample_decks
```

Run both steps explicitly in one command:

```console
python manage.py download_sample_decks --import
```

The download and import steps remain separate so importing never requires
network access. Import is strict about card IDs: a deck is skipped when an ID
does not exist in the local card database. Structural import does not claim
that a character deck is legal for current tournament play; the normal deck
validator remains responsible for format and ban-list legality.

## Character cover images

Character deck tiles can use local PNG covers downloaded from the official
Yu-Gi-Oh! DUEL LINKS character pages. Run:

```console
python manage.py download_character_covers
```

The command stores files below `media/deck_covers/characters/` and assigns one
portrait to every matching version of the same character. Z-ARC is the sole
fallback sourced from the Yu-Gi-Oh! ARC-V Wiki because an official Duel Links
portrait is not currently available. These copyrighted images are intended for
this non-commercial course demonstration; keep the source attribution.

You may add your own `.ydk` files anywhere below this directory. Give a custom
file a matching entry in `metadata.json` when you want a polished display name,
archetype, description, or format.
