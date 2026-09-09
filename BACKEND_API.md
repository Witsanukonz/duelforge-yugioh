# Backend API

All JSON write requests use `Content-Type: application/json`. Browser clients
must first request `GET /api/auth/csrf/` and send the resulting `csrftoken`
cookie value in the `X-CSRFToken` header on unsafe requests.

## Authentication

- `GET /api/auth/csrf/` — set the CSRF cookie.
- `POST /api/auth/signup/` — create a session (`username`, `password1`, `password2`).
- `POST /api/auth/login/` — create a session (`username`, `password`).
- `POST /api/auth/logout/` — end the current session.
- `GET /api/auth/me/` — return the signed-in user.

## Cards and ban lists

- `GET /api/cards/` — paginated catalog. Supports `q`, `type`, `frame_type`,
  `attribute`, `race`, `archetype`, `ordering`, `page`, and `page_size`.
- `GET /api/cards/<card_id>/` — card detail using the public YGOPRODeck ID.
- `GET /api/banlists/` — list ban lists. Supports `format` and `active`.
- `GET /api/banlists/current/?format=TCG` — current effective TCG or OCG list.
- `GET /api/banlists/<id>/` — entries with `q`, `status`, and pagination.

## Decks

- `GET /api/decks/` — decks visible to the current user. Add `mine=true` for
  owned decks. Supports `q`, `format`, and pagination.
- `POST /api/decks/` — create a deck.
- `GET|PATCH|DELETE /api/decks/<id>/` — read or manage one deck.
- `POST /api/decks/<id>/cards/` — create or replace one card/section entry.
- `PATCH|DELETE /api/decks/<id>/cards/<entry_id>/` — update or remove an entry.
- `GET /api/decks/<id>/validate/` — report Main/Extra/Side size and copy-limit issues.

Deck writes require ownership. Main Deck is capped at 60 cards; Extra and Side
Decks at 15 each. A card can have at most three copies across all sections, or
fewer when the selected ban list restricts it. The validation endpoint also
requires at least 40 Main Deck cards before a deck is tournament-valid.

## Collection

- `GET|POST /api/collection/` — list or add cards for the signed-in user.
- `GET|PATCH|DELETE /api/collection/<id>/` — manage one owned collection item.

Collection listing supports `q`, `condition`, `favorite`, `ordering`, and pagination.
