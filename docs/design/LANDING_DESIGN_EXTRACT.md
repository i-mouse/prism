# Prism Landing Page - Design System Extraction

This document provides a read-only audit and extraction of the design system values from the `prism-landing` codebase. All extractions are cited using exact values from the actual code.

## SECTION 1 — COLOR TOKENS

### Explicit Tailwind `@theme` Definitions
*Found in `src/app/globals.css` (Lines 7-54)*
```css
@theme inline {
  --color-brand: var(--color-orange-500);
  --color-supported: var(--color-emerald-500);
  --color-partial: var(--color-amber-500);
  --color-refused: var(--color-rose-500);
  --color-other: var(--color-slate-500);
  
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-card-foreground: var(--card-foreground);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-secondary: var(--secondary);
  --color-secondary-foreground: var(--secondary-foreground);
  --color-muted: var(--muted);
  --color-muted-foreground: var(--muted-foreground);
  --color-accent: var(--accent);
  --color-accent-foreground: var(--accent-foreground);
  --color-destructive: var(--destructive);
  --color-border: var(--border);
  --color-input: var(--input);
  --color-ring: var(--ring);
  /* ...sidebar and chart tokens... */
}
```

### OKLCH Theme Variables (Light & Dark Variants)
*Found in `src/app/globals.css` (Lines 56-127)*

**Light Mode (`:root`)**
- `--background`: `oklch(1 0 0)`
- `--foreground`: `oklch(0.145 0 0)`
- `--card`: `oklch(1 0 0)`
- `--card-foreground`: `oklch(0.145 0 0)`
- `--muted`: `oklch(0.97 0 0)`
- `--muted-foreground`: `oklch(0.556 0 0)`
- `--border`: `oklch(0.922 0 0)`

**Dark Mode (`.dark`)**
- `--background`: `oklch(0.145 0 0)` /* zinc-950 */
- `--foreground`: `oklch(0.985 0 0)` /* zinc-100 */
- `--card`: `oklch(0.205 0 0)` /* zinc-900 */
- `--card-foreground`: `oklch(0.985 0 0)`
- `--muted`: `oklch(0.269 0 0)`
- `--muted-foreground`: `oklch(0.708 0 0)`
- `--border`: `oklch(1 0 0 / 10%)`

### Semantic Mapping & Inconsistencies
- **Brand Accent:** `--color-brand` resolves to `orange-500`. It is widely used as `bg-brand` for primary CTAs and `text-brand` for highlights.
- **Verdict Labels:**
  - `supported`: Maps to `--color-emerald-500` (Light) and `--color-emerald-400` (Dark).
  - `partial`: Maps to `--color-amber-500` (Light) and `--color-amber-400` (Dark).
  - `refused`: Maps to `--color-rose-500` (Light) and `--color-rose-400` (Dark).
- **Backgrounds, Text, Borders:** Primarily mapped to `bg-background`, `text-foreground`, `text-muted-foreground`, and `border-border` globally. 
- **Inconsistencies & Hardcoded Values Bypassing Theme:**
  - `src/components/sections/how-it-works-section.tsx:9`: Forces a light-mode only background: `className="py-24 px-6 bg-zinc-50 dark:bg-zinc-50 text-zinc-900"`. Step cards force `bg-white/60`, and borders are forced to `border-zinc-200/50`.
  - `src/components/sections/wedge-section.tsx:5`: Hardcoded background bypassing theme (`bg-zinc-100 text-zinc-900 dark:bg-zinc-100`).
  - Various engineering links bypass semantic mapping, using `text-cyan-700 dark:text-cyan-400` instead of a primary/accent color token.

---

## SECTION 2 — TYPOGRAPHY

### Fonts Loaded
*Found in `src/app/layout.tsx` (Lines 6-14)*
- **Sans (Geist):** `Geist({ variable: "--font-sans", subsets: ["latin"] })`
- **Mono (JetBrains Mono):** `JetBrains_Mono({ variable: "--font-mono", subsets: ["latin"] })`

### Font Stack Fallbacks
*Found in `src/app/globals.css` (Lines 15-17)*
- `--font-sans`: `var(--font-sans)`
- `--font-heading`: `var(--font-sans)`
- `--font-mono`: `var(--font-mono)`

### Type Scale Used
- **H1 (Hero):** `text-5xl md:text-6xl lg:text-[72px] font-mono font-bold leading-tight tracking-tight text-balance` (`hero-section.tsx:14`)
- **H2 (Section Headlines):** `text-4xl md:text-5xl lg:text-[52px] font-bold tracking-tight` (`how-it-works-section.tsx:13`) or `text-4xl md:text-5xl font-bold tracking-tight mb-6` (`live-audit-upload.tsx:15`)
- **H3 (Card Titles):** `text-2xl font-bold tracking-tight text-foreground` (`scope-limitations-section.tsx:25`)
- **Body / Prose:** `text-[16px] md:text-[17px] leading-relaxed` (`hero-section.tsx:19`) or `text-lg max-w-md leading-relaxed` (`live-audit-upload.tsx:16`)
- **Small / Metadata:** `text-[12px]`, `text-[13px]` and `text-sm` used heavily for sub-labels and small prose.
- **Eyebrows:** `text-[13px] md:text-[14px] font-bold tracking-widest uppercase font-mono` (`live-audit-upload.tsx:14`, `scope-limitations-section.tsx:16`)

### Mono vs Sans Usage Rules
- **Sans (`font-sans`):** Default body text (`html { @apply font-sans; }` in `globals.css`), standard prose, component labels, "Scope & Limitations" lists, and regular reading text.
- **Mono (`font-mono`):** Used aggressively for "technical" interfaces: The hero headline (`hero-section.tsx`), engineering section descriptions (`footer-section.tsx`), eyebrows (`uppercase font-mono`), and the live audit demo outputs (Claim and Auditor texts).

---

## SECTION 3 — SPACING & LAYOUT

### Rhythms & Gaps
- **Section Padding:** Standard section padding is `py-24 px-6` (`how-it-works-section.tsx`, `scope-limitations-section.tsx`), `py-20 px-6` (`stats-section.tsx`, `footer-section.tsx`), or specifically for hero `pt-28 md:pt-36 pb-12 px-6` (`hero-section.tsx`).
- **Container Max-Widths:**
  - Standard max: `max-w-7xl mx-auto` (`navbar.tsx`, `footer-section.tsx`, `how-it-works-section.tsx`)
  - Narrow max: `max-w-6xl mx-auto` (`hero-section.tsx`, `scope-limitations-section.tsx`)
  - Content-specific max: `max-w-5xl mx-auto` (`live-audit-demo.tsx`)
- **Gaps:** `gap-8` for major grid layouts. `gap-16 lg:gap-24` for large split-sections (`how-it-works-section.tsx`). `gap-3` and `gap-4` for minor alignments.
- **Card Padding:** `p-8 lg:p-12` (`scope-limitations-section.tsx`) or `p-8` for standard cards (`live-audit-upload.tsx`).
- **Border Radii:**
  - Buttons/CTAs: `rounded-md` (`hero-section.tsx`)
  - Large Cards: `rounded-3xl` (`scope-limitations-section.tsx`) or `rounded-2xl` (`live-audit-upload.tsx`)
  - Minor Cards: `rounded-xl` (`live-audit-demo.tsx`)
  - Pills: `rounded-full` (`verdict-pill.tsx`)

---

## SECTION 4 — COMPONENT INVENTORY

### Nav bar (`src/components/layout/navbar.tsx`)
```tsx
<motion.nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 px-6 ${isScrolled ? "bg-background/90 border-b border-border backdrop-blur-md py-4" : "bg-transparent border-transparent py-6"}`}>
  <div className="max-w-7xl mx-auto flex flex-row items-center justify-between">
    <div className="flex items-center gap-3">
      <PrismLogo />
      <span className="font-bold text-lg tracking-tight text-foreground">{content.nav.logo}</span>
    </div>
    <div className="hidden lg:flex items-center gap-8">
      <div className="flex items-center gap-6 text-[13px] font-mono font-medium text-muted-foreground">
        {content.nav.links.map(link => (
          <Link key={link.label} href={link.href} className="hover:text-foreground transition-colors">{link.label}</Link>
        ))}
      </div>
      <div className="flex items-center gap-6">
        <a href="#live-audit" className="text-[13px] font-mono font-medium text-orange-500 hover:text-orange-400 transition-colors">{content.nav.cta}</a>
        <ThemeToggle />
      </div>
    </div>
  </div>
</motion.nav>
```

### Logo (`src/components/layout/navbar.tsx`)
```tsx
<div className="relative w-7 h-7">
  <svg viewBox="0 0 100 100" className="w-full h-full drop-shadow-[0_2px_8px_rgba(249,115,22,0.3)]">
    <defs>
      <linearGradient id="prism-grad-nav" x1="0%" y1="100%" x2="100%" y2="0%">
        <stop offset="0%" stopColor="var(--color-pink-500)" />
        <stop offset="50%" stopColor="var(--color-orange-500)" />
        <stop offset="100%" stopColor="var(--color-amber-400)" />
      </linearGradient>
    </defs>
    <path d="M 50 15 L 85 85 L 15 85 Z" fill="none" stroke="url(#prism-grad-nav)" strokeWidth="14" strokeLinejoin="round" />
  </svg>
</div>
```

### Primary CTA Button (`src/components/sections/hero-section.tsx`)
```tsx
<a href="#live-audit" className="bg-brand text-white px-6 py-3 rounded-md font-bold text-[15px] hover:bg-orange-500 transition-colors shadow-lg shadow-brand/20">
  {content.hero.ctaPrimary}
</a>
```

### Secondary Button Outline (`src/components/ui/button.tsx`)
```tsx
// Using class-variance-authority config:
"border border-input bg-background hover:bg-accent hover:text-accent-foreground inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
```

### Verdict Pills (`src/components/verdict-pill.tsx`)
```tsx
<span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold tracking-widest uppercase font-mono ${colorMap[color]}`}>
  {label}
</span>
// colorMap bindings:
// supported: 'bg-supported text-zinc-950'
// partial: 'bg-partial text-zinc-950'
// refused: 'bg-refused text-white dark:text-zinc-950'
```

### Section Eyebrows (`src/components/sections/live-audit-upload.tsx`)
```tsx
<span className="text-orange-600 dark:text-orange-500 text-[13px] md:text-[14px] font-bold tracking-widest uppercase mb-4 block font-mono">
  {content.upload.eyebrow}
</span>
```

### Section Headlines (`src/components/sections/live-audit-upload.tsx`)
```tsx
<h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-6 text-foreground">{content.upload.heading}</h2>
```

### Body Prose (`src/components/sections/how-it-works-section.tsx`)
```tsx
<p className="text-[17px] md:text-[18px] text-zinc-600">{content.howItWorks.subhead}</p>
```

### 10/14 Stat (`src/components/sections/stats-section.tsx`)
```tsx
<div className="font-mono text-[80px] md:text-[120px] font-bold leading-none tracking-tighter mb-4 text-center inline-block">
  <span className="text-amber-500">{content.stats.mainNumberParts[0]}</span>
  <span className="text-orange-500 mx-3">{content.stats.mainNumberParts[1]}</span>
  <span className="text-rose-500">{content.stats.mainNumberParts[2]}</span>
</div>
```

### Small Stat Rows (`src/components/sections/stats-section.tsx`)
```tsx
<div className="flex flex-col items-center text-center gap-2">
  <span className="text-2xl md:text-3xl text-amber-500 font-mono font-bold tracking-tight">{parts[0]}</span>
  <span className="text-muted-foreground text-[12px] font-mono leading-relaxed max-w-[180px]">{parts[1]}</span>
</div>
```

### Link with Arrow (`src/components/sections/stats-section.tsx`)
```tsx
<a href={content.stats.linkHref} className="font-mono text-[13px] text-brand border-b border-brand/50 pb-0.5 hover:text-orange-400 hover:border-orange-400 transition-colors">
  {content.stats.linkText}
</a>
```

### Scope & Limitations Cards (`src/components/sections/scope-limitations-section.tsx`)
```tsx
<div className="bg-card border border-border rounded-3xl p-8 lg:p-12 flex flex-col gap-8 shadow-xl relative group overflow-hidden">
  <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-rose-500/0 via-rose-500/50 to-rose-500/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
  <h3 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-3">
    <span className="w-8 h-8 rounded-full bg-rose-500/10 flex items-center justify-center border border-rose-500/20 text-rose-500">
      <XCircle size={16} />
    </span>
    {content.wontDo.heading}
  </h3>
  <!-- inner lists -->
</div>
```

### Upload Dropzone (`src/components/sections/live-audit-upload.tsx`)
```tsx
<div className="flex-1 w-full max-w-md mx-auto">
  <div className="border border-border bg-card rounded-2xl p-10 flex flex-col items-center justify-center text-center hover:border-brand/50 transition-colors cursor-pointer group shadow-sm">
    <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
      <UploadCloud className="text-muted-foreground group-hover:text-brand transition-colors" size={24} />
    </div>
    <h3 className="text-[15px] font-bold text-foreground mb-2 tracking-tight">Drop your PDF here</h3>
    <p className="text-[13px] text-muted-foreground mb-8">or click to browse</p>
    <div className="text-[10px] font-mono tracking-widest text-muted-foreground/60 uppercase mb-8">Up to 50MB · PDF only</div>
    <div className="text-[11px] font-mono font-bold tracking-widest uppercase text-brand flex items-center gap-2 opacity-80 group-hover:opacity-100 transition-opacity">
      → Opens the live demo in a new tab
    </div>
  </div>
</div>
```

### Theme Toggle (`src/components/theme-toggle.tsx`)
```tsx
<div className="flex items-center gap-2">
  <Sun size={16} className={theme === 'light' ? 'text-zinc-900' : 'text-zinc-500'} />
  <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} className="w-10 h-5 bg-zinc-800 rounded-full relative flex items-center px-1" aria-label="Toggle theme">
    <div className={`w-3 h-3 rounded-full bg-zinc-400 transition-transform duration-200 ${theme === 'dark' ? 'translate-x-5' : 'translate-x-0'}`} />
  </button>
  <Moon size={16} className={theme === 'dark' ? 'text-zinc-100' : 'text-zinc-500'} />
</div>
```

### Footer Row (`src/components/sections/footer-section.tsx`)
```tsx
<footer className="py-8 px-6 border-t border-border">
  <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
    <div className="flex flex-col md:flex-row items-center gap-4 md:gap-6">
      <div className="flex items-center gap-3">
        <PrismLogo />
        <span className="font-bold text-xl tracking-tight text-foreground">Prism</span>
      </div>
      <div className="hidden md:block w-px h-6 bg-border"></div>
      <div className="text-[12px] text-muted-foreground font-mono">{content.footer.copyright}</div>
    </div>
    <div className="flex items-center gap-6">
      <a href="..." className="text-muted-foreground hover:text-foreground text-[13px] transition-colors font-medium">Home</a>
    </div>
  </div>
</footer>
```

### Audit Demo Card (`src/components/live-audit-demo.tsx`)
```tsx
{/* Overall layout */}
<div className="w-full max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-8 relative z-10">
  {/* Left Column Container */}
  <div className="bg-card border border-border rounded-xl overflow-hidden flex flex-col">
    {/* Header */}
    <div className="p-4 border-b border-border flex items-center gap-2">
      <div className="w-2 h-2 rounded-full bg-brand"></div>
      <span className="text-xs font-mono font-bold tracking-widest text-brand uppercase">{content.liveAuditDemo.header}</span>
    </div>
    {/* Body */}
    <div className="p-8 flex-1 flex flex-col">
      <p className="text-muted-foreground font-mono text-sm mb-6">// Claim {activeExample.claimNum}</p>
      <div className="font-mono text-lg md:text-xl leading-relaxed text-foreground flex-1 min-h-[180px]">
        {/* Typewriter text rendered here */}
      </div>
    </div>
    {/* Footer */}
    <div className="p-4 border-t border-border flex items-center justify-between text-muted-foreground font-mono text-xs bg-muted/50">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
        Watching live
      </div>
      <div className="flex items-center gap-4">
        {/* Navigation controls */}
      </div>
    </div>
  </div>
  {/* Right column omitted for brevity */}
</div>
```

---

## SECTION 5 — ANIMATION & INTERACTION

### Hero Typing Animation (`live-audit-demo.tsx`)
- **Implementation:** Custom `TypewriterText` component using React `useState` and `useEffect` with a `setInterval` updating text length via `.slice(0, i)` every tick (0.02s to 0.04s).
- **Timing:** Hierarchical timeline managed by React state. The Auditor reasoning is scheduled to start typing midway through the main Claim text's typing (`claimDuration * 0.6`).
- **Reduced Motion Support:** Framer Motion's `useReducedMotion()` is explicitly checked. If enabled, the animation immediately `setDisplayedText(text)` and bypasses the `setInterval` logic.

### Scroll-triggered Reveals (`how-it-works-section.tsx`)
- **Framer Motion hooks:** `<motion.div whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} />`
- Sequential step delays are multiplied by iteration index: `transition={{ duration: 0.5, delay: i * 0.2 }}`

### Transitions & Hover States
- Standard classes: `transition-colors`, `transition-all duration-300`, `transition-opacity duration-500`
- Border hovers: `hover:border-brand/50` or `hover:border-orange-400`
- Background hovers: `hover:bg-accent` or `hover:bg-orange-500`
- Links: `hover:text-foreground` or `hover:text-red-400`
- Focus Rings (Buttons): `focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2`
- Active scaling: `group-hover:scale-110` applied to icons inside upload containers.

---

## SECTION 6 — GRADIENT & AURORA EFFECTS

### Orange→Rose Text Gradient
*Found in `src/components/sections/hero-section.tsx:16`*
```css
bg-clip-text text-transparent bg-gradient-to-r from-orange-500 to-rose-500
```
*(Note: The 10/14 stat explicitly does not use a single background-clip gradient, but instead splits individual numbers into different span colors `text-amber-500`, `text-orange-500`, and `text-rose-500`).*

### Radial Background Glow
*Found in `src/components/sections/hero-section.tsx:11`*
```html
<div className="absolute top-[20%] left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-[radial-gradient(ellipse_at_center,_var(--color-orange-500)_0%,_transparent_60%)] opacity-0 dark:opacity-[0.12] blur-3xl pointer-events-none -z-10"></div>
```

### Linear Grid Mask Background
*Found in `src/components/sections/stats-section.tsx:9`*
```html
<div className="absolute inset-0 bg-[linear-gradient(to_right,var(--color-border)_1px,transparent_1px),linear-gradient(to_bottom,var(--color-border)_1px,transparent_1px)] bg-[size:32px_32px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_20%,transparent_100%)]"></div>
```

---

## SECTION 7 — RESPONSIVE & THEME

### Breakpoint Patterns
- Standard Tailwind `md:` and `lg:` usage for layout flips.
- **Typography Resizing:** `text-5xl md:text-6xl lg:text-[72px]`.
- **Layout Reflows:** Content grids switch from single-column on mobile to dual-column on `md:` or `lg:` (e.g. `grid-cols-1 md:grid-cols-2`).
- **Navbar:** The menu links fold into a hidden state (`hidden lg:flex`) in favor of a mobile-responsive layout.

### Dark / Light Mode Strategy
- **Implementation:** Handled by `next-themes` toggling a `.dark` class on the `<html>` element.
- **Variable Injection:** Tailwind v4 `@theme inline` injects base CSS variables globally pointing to semantic tokens (`var(--foreground)`, `var(--background)`, `var(--border)`).
- **Overrides:** 
  - Several hardcoded instances dynamically adapt via classes like `text-cyan-700 dark:text-cyan-400` or `text-orange-600 dark:text-orange-500` bypassing standard structural theme mappings entirely.
  - Background blurs (`dark:opacity-[0.12]`) and gradients are explicitly restricted or toned down using the `dark:` prefix to prevent high-contrast bleeding during dark mode.
