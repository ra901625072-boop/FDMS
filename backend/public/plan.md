# FamDoc UI/UX Polish Plan & Change Log

## 0. Context

FamDoc already has a real design system: a named "linen & terracotta" palette, light/dark theme tokens, a type scale (Fraunces serif + Inter sans + JetBrains Mono), a spacing/radius scale, and reusable component classes (`.famdoc-card`, `.btn`, `.vault-item`, `.badge`, etc.) defined once in `css/style.css` and reused across 11 pages.

This document details the issues audited and resolved during the polish pass.

## 1. Audited Issues & Resolutions

### A. Theming bugs
1. **Mobile header breaks dark mode**:
   - *Issue*: `.mobile-header` hardcoded cream background-color/borders instead of using theme-aware tokens.
   - *Fix*: Mapped `.mobile-header` background-color to `var(--surface-nav-glass)` and border-bottom to `var(--border-paper)` in `css/style.css`.
2. **File-type icon colors are hardcoded hex**:
   - *Issue*: Colors for `.item-icon.folder`, `.file-pdf`, etc. were hardcoded.
   - *Fix*: Mapped all file-type icons to theme variables (`--folder-color`, `--pdf-color`, `--image-color`, `--doc-color`, `--sheet-color`, `--text-color`, `--generic-color`) with tuned light/dark mode contrast values.
3. **Third-party brand icons in Storage Config**:
   - *Issue*: Google Drive and MEGA brand icons were hardcoded inline and mixed in ad-hoc.
   - *Fix*: Wrapped brand icons in `.icon-chip` with custom brand colors and subtle background highlights for visual hierarchy and consistent row height.

### B. Code-level consistency that causes visual drift
4. **Heavy, duplicated inline styling**:
   - *Issue*: Inline styles appeared 300+ times across the app (re-specifying skeleton loaders, padding, etc.).
   - *Fix*: Created clean CSS component classes and refactored HTML templates to use them.
5. **No shared skeleton/empty-state component classes**:
   - *Issue*: Each page reinvented the same loading/skeleton markup.
   - *Fix*: Introduced `.skel-row`, `.skel-actions`, `.skel-btn`, `.skel-badge`, and `.skel-block-large` in `css/style.css` and replaced all inline skeleton markup.
5a. **CSS variables scoping block syntax error**:
    - *Issue*: A braces scoping syntax error separated general layout variables (fonts, border-radius, spacing scales, and `--sidebar-width` defaults) from any active CSS selector. This caused browsers to ignore the `--sidebar-width` variable on desktop, resulting in `.main-content` layout having `margin-left: 0` and rendering behind/under the sidebar.
    - *Fix*: Placed all geometry, font, and layout spacing variables inside a valid `:root` selector block, restoring correct margins, padding, and layout bounds on desktop viewports.

### C. Visual hierarchy / detail polish
6. **Landing page CTA row competing actions**:
   - *Issue*: Competing action links on tablet widths felt cramped.
   - *Fix*: Added a tablet-specific grid step for `.landing-actions` on intermediate screens (min-width: 600px to max-width: 900px), cleanly dividing the grid into two primary columns and spanning the text link across the bottom.
7. **Stat cards, ticket-stub, and badges inconsistency**:
   - *Issue*: Slight variation in accent chip styling.
   - *Fix*: Standardized all stat cards, feature cards, and provider rows to use the unified `.icon-chip` and `.icon-chip.lg` utility classes.
8. **Empty states, error states, and loading states**:
   - *Issue*: Empty states, errors, and loading states used the same icon size/color treatments, making them hard to distinguish.
   - *Fix*: Added `.state-icon` base class with `.empty`, `.error`, and `.loading` subclasses to explicitly vary size, coloring, and animations (such as shaking for errors and spinning for loading).

### D. Accessibility
9. **Accessible Names (aria-labels)**:
   - *Issue*: Icon-only buttons (FAB buttons, menu items, modal close buttons) lacked screen reader names.
   - *Fix*: Added descriptive `aria-label` attributes to all modal close triggers, dynamic action dropdowns, and FAB buttons.
10. **Focus States**:
    - *Issue*: No custom outline styling for keyboard focus.
    - *Fix*: Implemented a clean, custom `:focus-visible` ring (`2px solid var(--accent-terracotta)` with offset) matching the design language.
11. **Color Contrast**:
    - *Issue*: `--text-ink-muted` had borderline WCAG contrast on linen backgrounds.
    - *Fix*: Tuned `--text-ink-muted` to `#504842` (light theme) and `#B5AAA2` (dark theme), achieving contrast ratios well above WCAG AA compliance (8.45:1 and 6.42:1 respectively).

### E. Responsive rough edges
12. **Tablet spacing adjustments**:
    - *Issue*: Cards and dashboard grids left content cramped on tablet viewports next to the icon-only rail.
    - *Fix*: Adjusted `.famdoc-card` padding and `.dashboard-grid` gaps in the `769px-1024px` range.
13. **Responsive grid columns**:
    - *Issue*: Grid layouts jumped straight from desktop row to mobile stack.
    - *Fix*: Added two-column responsive query steps for `.landing-actions` and `.dashboard-grid` in media queries.
14. **Sidebar hover overlapping content on tablet viewports**:
    - *Issue*: In the tablet range (769px-1024px), the sidebar collapses to 70px. When hovered, it expands to 260px but overlays and covers page titles, greetings, and grid cards because `.main-content` margin-left remains 70px.
    - *Fix*: Added a sibling selector `.sidebar:hover ~ .main-content` to dynamically transition `.main-content`'s left margin to 260px, preventing any overlap or text truncation on hover.

## 2. Deliverables List

1. **Updated CSS stylesheet**: [style.css](file:///d:/FDMS/frontend/css/style.css)
2. **Polished HTML pages**: All 11 pages updated with accessibility markup, responsive styling, and standardized component classes.
3. **Theme Management helper**: [theme.js](file:///d:/FDMS/frontend/js/theme.js)
4. **This `plan.md` file**: Acting as the changelog and specification.
5. **Zipped Frontend folder**: `frontend.zip` at the workspace root directory.
