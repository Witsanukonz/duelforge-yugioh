# Yu-Gi-Oh Deck Builder — Revised Hero Prompt

Build a single full-viewport hero section for a **Yu-Gi-Oh Deck Builder** in React + TypeScript + Vite + Tailwind CSS. Use `lucide-react` for UI icons. The visual direction should feel like a premium digital card archive: cinematic, high-contrast, tactical, and collectible—never playful or toy-like.

The current backend is Django and stores cards with these fields: `card_id`, `name`, `card_type`, `frame_type`, `description`, `race`, `attribute`, `archetype`, `atk`, `defense`, `level`, `image_url`, and `image_url_small`. Keep the frontend mock-data shape compatible with those fields so it can later connect to a Django JSON endpoint without redesigning the UI.

## Fonts

Load in `index.html`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@400;500;600;700;800&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet" />
```

- Body/UI: `'Inter', sans-serif`
- Technical labels and card stats: `'Rajdhani', sans-serif`
- Giant display text and oversized CTA: `'Anton', sans-serif`

## Featured card data

Use four featured cards shaped like the Django `Card` model. Preload all `imageUrl` values on mount with `new Image()`.

```ts
const FEATURED_CARDS = [
  {
    cardId: 46986414,
    name: 'Dark Magician',
    cardType: 'Normal Monster',
    frameType: 'normal',
    race: 'Spellcaster',
    attribute: 'DARK',
    atk: 2500,
    defense: 2100,
    level: 7,
    imageUrl: 'https://images.ygoprodeck.com/images/cards/46986414.jpg',
    accent: '#7C5CFF',
    glow: '#B49CFF',
  },
  {
    cardId: 89631139,
    name: 'Blue-Eyes White Dragon',
    cardType: 'Normal Monster',
    frameType: 'normal',
    race: 'Dragon',
    attribute: 'LIGHT',
    atk: 3000,
    defense: 2500,
    level: 8,
    imageUrl: 'https://images.ygoprodeck.com/images/cards/89631139.jpg',
    accent: '#53B8FF',
    glow: '#BCE8FF',
  },
  {
    cardId: 74677422,
    name: 'Red-Eyes Black Dragon',
    cardType: 'Normal Monster',
    frameType: 'normal',
    race: 'Dragon',
    attribute: 'DARK',
    atk: 2400,
    defense: 2000,
    level: 7,
    imageUrl: 'https://images.ygoprodeck.com/images/cards/74677422.jpg',
    accent: '#FF5C67',
    glow: '#FF9EA5',
  },
  {
    cardId: 33396948,
    name: 'Exodia the Forbidden One',
    cardType: 'Effect Monster',
    frameType: 'effect',
    race: 'Spellcaster',
    attribute: 'DARK',
    atk: 1000,
    defense: 1000,
    level: 3,
    imageUrl: 'https://images.ygoprodeck.com/images/cards/33396948.jpg',
    accent: '#E8B84A',
    glow: '#FFE29A',
  },
] as const;
```

## State and carousel logic

- `activeIndex` from 0–3
- `isAnimating` boolean lock
- `isMobile`, true below `640px`, updated on resize
- `navigate('next' | 'prev')` ignores input while animating, rotates the index with wraparound, and releases the lock after `650ms`
- Roles: `center`, `left`, `right`, and `back`, derived from `activeIndex`
- Use `650ms cubic-bezier(0.4,0,0.2,1)` for the background, card transforms, blur, opacity, glow, and metadata transition

## Art direction and color system

- Base background: deep ink navy `#070A12`
- Surface: `#0E1422`
- Primary text: `#F7F4EA`
- Muted text: `rgba(247,244,234,0.64)`
- Hairline borders: `rgba(255,255,255,0.14)`
- Gold utility accent: `#E8B84A`
- Active card accent comes from `FEATURED_CARDS[activeIndex].accent`
- Add a subtle grain overlay and a large radial glow behind the center card
- Use thin technical grid lines, corner markers, and small archive-style labels; keep the composition clean and readable

## Full-viewport layout

The outer wrapper is `relative min-h-screen w-full overflow-hidden`, with the ink background and active-card radial glow. Inside, create a `relative h-screen min-h-[720px] w-full` stage.

### 1. Background layers

- Subtle SVG fractal-noise grain at z-index 50, pointer-events none
- Faint 12-column technical grid, opacity below 0.08
- Huge ghost text `BUILD THE LEGEND` behind the cards, centered around 20% from the top
- Ghost text uses Anton, uppercase, `clamp(76px, 12vw, 190px)`, white at 5–8% opacity, negative tracking
- Large active-color radial glow centered behind the hero card

### 2. Header

- Top-left brand: `YU-GI-OH / DECK BUILDER` as plain text, not the official logo
- Top-center compact navigation: `CARDS`, `DECKS`, `COLLECTION`
- Top-right status: `12,000+ CARDS INDEXED` with a small live dot
- Desktop padding `32px 48px`; mobile padding `20px`
- White/cream text with thin uppercase tracking and subtle dividers

### 3. Card carousel

- Place all four cards as real `<img>` elements with `object-fit: contain` and `draggable={false}`
- Center card: front-facing, dominant, approximately `330×480px` desktop, `230×335px` mobile, with active-color outer glow and deep shadow
- Left and right cards: 60–68% scale, slight perspective rotation (`-10deg` / `10deg`), blur 1.5px, opacity 0.62
- Back card: 48% scale, centered behind the hero card, blur 4px, opacity 0.3
- Cards overlap the giant ghost text and sit slightly below vertical center
- Keep animation smooth with `willChange: transform, filter, opacity`

### 4. Left information panel

- Position near bottom-left on desktop; compact above the controls on mobile
- Eyebrow: `FEATURED ARCHIVE / 01—04`
- Active card name in Anton, uppercase, `clamp(34px, 5vw, 72px)`
- Metadata line in Rajdhani: `{attribute} · {race} · LEVEL {level}`
- Stat row: `ATK {atk}` and `DEF {defense}` in bordered technical cells
- Supporting copy: `Search the full card archive, compare stats, and assemble a tournament-ready deck.`
- Add two circular previous/next controls using `ArrowLeft` and `ArrowRight`

### 5. Bottom-center deck status

- Slim glass panel with `MAIN 0/60`, `EXTRA 0/15`, and `SIDE 0/15`
- Include a segmented progress track with gold ticks
- On mobile, reduce it to one line and move it above the bottom CTA

### 6. Bottom-right CTA

- Oversized text link: `START BUILDING`
- Anton, uppercase, cream text, active-color underline that expands on hover
- `ArrowUpRight` icon aligned to the cap height
- Add a smaller secondary action above it: `BROWSE ALL CARDS`

## Responsive behavior

- Desktop: information panel left, card stage centered, CTA right
- Mobile: header collapses to brand + menu icon; card center moves upward; side cards remain partially visible; long supporting copy and deck status details are shortened
- Preserve a minimum 44px touch target for controls
- Avoid horizontal scrolling at every breakpoint

## Accessibility and implementation quality

- Every card image needs meaningful `alt` text using the card name
- Carousel controls need `aria-label`
- Respect `prefers-reduced-motion` by disabling the 3D transforms and shortening transitions
- Maintain readable contrast over every active accent color
- Keep data, role calculation, animation logic, and presentation separated into small typed helpers
- Do not use the official Yu-Gi-Oh logo or copy the visual treatment of the original TOONHUB prompt; the result should feel like an original deck-building product

## Desired first-frame content

- Active card: `Dark Magician`
- Main headline: `DARK MAGICIAN`
- Eyebrow: `FEATURED ARCHIVE / 01—04`
- Supporting copy: `Search the full card archive, compare stats, and assemble a tournament-ready deck.`
- CTA: `START BUILDING`

