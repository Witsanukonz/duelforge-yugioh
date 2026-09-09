# Tailwind CSS in this Django project

This project uses **Django Tailwind 4.5** with **Tailwind CSS 4** through the
central `theme` Django app. The compiled stylesheet is loaded by
`templates/base.html` before the existing project stylesheet, so all pages can
use Tailwind utilities while retaining the original Yu-Gi-Oh design.

## Install dependencies

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe manage.py tailwind install
```

## Development

Run Django in one terminal:

```powershell
.\venv\Scripts\python.exe manage.py runserver
```

Run the Tailwind watcher in another terminal:

```powershell
.\venv\Scripts\python.exe manage.py tailwind start
```

## Production build

```powershell
.\venv\Scripts\python.exe manage.py tailwind build
```

Tailwind source and theme tokens live in
`theme/static_src/src/styles.css`. The build scans Django templates, Python,
and JavaScript files and writes the generated stylesheet to
`theme/static/css/dist/styles.css`.

Tailwind Preflight is disabled intentionally because the application already
has established element-level styles in `static/css/app.css`. This prevents a
framework migration from changing the current visual design.

## Rubric evidence

The project uses Tailwind on real Django form controls rather than adding demo-only
fields. The existing black-and-gold component classes remain in place, while the
Tailwind utilities provide responsive layout and accessible interaction states.

| Form component | Real use in the project | Template |
| --- | --- | --- |
| Text field | Deck name and deck type | `templates/decks/deck_builder.html` |
| Textarea | Editable deck strategy description | `templates/decks/deck_builder.html` |
| Checkbox | Public/private deck setting | `templates/decks/deck_builder.html` |
| Dropdown list | Ban List and progressive card filters | `templates/decks/deck_builder.html`, `templates/cards/card_list.html` |
| Search field | Card Archive, deck builder, and Collection search | `templates/cards/card_list.html`, `templates/collects/collection_list.html` |
| Number field | Collection card quantity | `templates/collects/collection_list.html` |

Tailwind utilities used directly by these interfaces include:

- Layout: `grid`, `grid-cols-1`, `md:grid-cols-2`, `xl:grid-cols-4`, `gap-3`, `flex`.
- Interaction: `transition-shadow`, `hover:shadow-lg`, `focus-visible:ring-2`, and `peer-focus-visible:ring-2`.
- Theme: `bg-arcane-ink`, `text-arcane-ivory`, `ring-arcane-gold/40`, and `ring-offset-arcane-ink`.

Run the automated proof with:

```powershell
.\venv\Scripts\python.exe manage.py tailwind build
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py test
```
