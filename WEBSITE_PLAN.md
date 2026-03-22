# DokyDoc Website Plan
### Company: VizaiLabs | Product: DokyDoc

---

## 1. OVERVIEW

**Goal:** A high-converting marketing website that positions DokyDoc as the go-to AI-powered document analysis and governance platform for engineering and product teams.

**Target Audience:**
- CTOs / CXOs at mid-to-large tech companies
- Engineering Leads / Developers
- Business Analysts
- Product Managers
- Compliance / Audit teams

**Primary CTA:** "Start Free Trial" / "Request a Demo"

---

## 2. TECH STACK RECOMMENDATION

| Layer | Choice | Reason |
|---|---|---|
| Framework | Next.js 15 (App Router) | SSR/SSG, SEO, matches existing frontend stack |
| Styling | Tailwind CSS 4 | Matches existing codebase |
| Animations | Framer Motion | Smooth scroll animations, hero effects |
| Icons | Lucide React | Already used in product |
| Diagrams / Visuals | Mermaid.js | Match product's own diagram style |
| Forms | React Hook Form + Zod | Validation for demo request / contact |
| Email | Resend API | Demo request notifications |
| Analytics | PostHog or Plausible | Privacy-friendly, easy to set up |
| Deployment | Vercel | One-click deploy, edge CDN |
| CMS (optional) | Notion API or MDX files | Blog / changelog content |

---

## 3. COLOR SYSTEM

Derived from the existing product design system:

```css
/* Primary Palette */
--color-primary:       #1E3A5F   /* Deep Navy Blue — trust, enterprise */
--color-primary-light: #2D5F9E   /* Lighter navy for hover states */
--color-accent:        #4F6EF7   /* Electric indigo — CTAs, highlights */
--color-accent-glow:   #7B96FF   /* Glow effect on dark backgrounds */

/* Neutrals */
--color-bg-dark:       #0B0F1A   /* Hero / dark sections */
--color-bg-mid:        #111827   /* Card backgrounds in dark mode */
--color-bg-light:      #F8FAFC   /* Light section backgrounds */
--color-white:         #FFFFFF

/* Text */
--color-text-primary:  #0F172A   /* Headings on light bg */
--color-text-muted:    #64748B   /* Subtext, captions */
--color-text-inverse:  #F1F5F9   /* Text on dark bg */

/* Status */
--color-success:       #22C55E
--color-warning:       #F59E0B
--color-error:         #EF4444

/* Gradients */
--gradient-hero: linear-gradient(135deg, #0B0F1A 0%, #1E2D4F 50%, #0B0F1A 100%);
--gradient-cta:  linear-gradient(90deg, #4F6EF7, #7B96FF);
--gradient-card: linear-gradient(145deg, #111827, #1a2332);
```

**Typography:**
- Font Family: `Geist Sans` (headings + body), `Geist Mono` (code snippets)
- Heading scale: 64px / 48px / 36px / 28px / 22px / 18px
- Body: 16px (1.6 line-height), Small: 14px

---

## 4. SITE ARCHITECTURE

```
/                     → Landing Page (Home)
/features             → Full Features Page
/use-cases            → Use Cases by Role
/pricing              → Pricing Page
/docs                 → Documentation (links to Swagger or MDX docs)
/blog                 → Blog / Changelog
/about                → About VizaiLabs
/contact              → Contact / Demo Request
/privacy              → Privacy Policy
/terms                → Terms of Service
```

---

## 5. PAGE-BY-PAGE PLAN

---

### PAGE 1: HOME (`/`)

#### Section 1 — Navigation (Sticky Header)
- **Left:** VizaiLabs logo + "DokyDoc" wordmark
- **Center Nav Links:** Features | Use Cases | Pricing | Docs | Blog
- **Right:** `Log In` (ghost button) + `Start Free Trial` (filled accent button)
- **Behavior:** Transparent on top, white/blur on scroll. Mobile: hamburger menu.

---

#### Section 2 — Hero
- **Layout:** Full-width dark background (`--color-bg-dark`), centered content
- **Badge:** Small pill badge → `✦ Now in Early Access`
- **H1 (64px bold):**
  ```
  Your Documents Know More
  Than You Think.
  ```
- **Subheading (20px, muted):**
  ```
  DokyDoc uses multi-pass AI to turn your documents and code
  into a living knowledge graph — with governance, alignment
  checks, and an AI assistant built in.
  ```
- **CTA Row:** `Start Free Trial` (accent gradient button) + `Watch Demo` (ghost with play icon)
- **Social Proof Bar:** `Trusted by teams at —` + 4-5 placeholder company logos (grayscale)
- **Hero Visual:** Animated dashboard mockup — showing the ontology graph with glowing nodes, document analysis in progress. Use a browser-frame mockup with subtle floating cards showing:
  - "87 concepts mapped"
  - "3 mismatches detected"
  - "Analysis complete ✓"

---

#### Section 3 — Problem Statement ("The Problem We Solve")
- **Layout:** Light background, 2-column
- **Left:** Bold stat callouts:
  ```
  68% of engineering docs are outdated within 3 months.
  $2.4M+ lost annually per company from documentation debt.
  Developers spend 19% of their time searching for information.
  ```
- **Right:** Short paragraph:
  ```
  Documentation is the backbone of every product — but it's
  always falling behind. Code changes. Requirements shift.
  Teams grow. DokyDoc keeps your knowledge base alive,
  accurate, and queryable.
  ```

---

#### Section 4 — How It Works (3-Step Flow)
- **Layout:** Dark section, centered, horizontal 3-step flow with connecting line
- **Step 1 — Upload:**
  Icon: Upload cloud
  Title: `Connect Your Sources`
  Body: `Upload PDFs, link Git repositories, or sync from Notion, Jira, and Slack.`

- **Step 2 — Analyze:**
  Icon: Brain/sparkles
  Title: `AI Analyzes Everything`
  Body: `Our multi-pass AI engine extracts concepts, maps relationships, and detects mismatches between your code and docs.`

- **Step 3 — Govern:**
  Icon: Shield check
  Title: `Govern & Query`
  Body: `Ask questions in plain English via AskyDoc, enforce approval workflows, and track every change with a full audit trail.`

---

#### Section 5 — Core Features (Feature Grid)
- **Layout:** Light background, 6-card grid (2 rows × 3 columns)
- **Card Design:** White card, icon (accent color), title, 2-line description

| Icon | Title | Description |
|---|---|---|
| 🧠 | Multi-Pass AI Analysis | 4-pass document processing with semantic enrichment and cost tracking |
| 🔗 | Code-Doc Alignment | Detect mismatches between your codebase and documentation in real time |
| 🌐 | Business Ontology Engine | Dual knowledge graphs (documents + code) linked by AI-validated concept mapping |
| 💬 | AskyDoc AI Assistant | Ask your organization's knowledge base anything in plain English |
| 🛡️ | Role-Based Governance | 20+ permissions, RBAC, approval workflows, and full audit trails |
| 🏢 | Multi-Tenant SaaS | Complete data isolation with prepaid/postpaid billing enforcement |

---

#### Section 6 — Feature Deep-Dive (Alternating Sections)
Three alternating left-right sections, each with a visual on one side and text on the other.

**Section A — Knowledge Graph**
- Visual: Animated graph with nodes/edges (use D3 or Mermaid screenshot)
- Title: `A Living Map of Your Organization's Knowledge`
- Body: `DokyDoc builds two separate knowledge graphs — one for your documents, one for your code — then links them using a 3-tier matching algorithm (exact, fuzzy, AI-validated). The result: a single source of truth across your entire tech stack.`
- Tag pills: `Business Ontology Engine` `Concept Mapping` `97% cost savings on matching`

**Section B — AskyDoc Chat**
- Visual: Chat UI mockup with sample Q&A:
  - Q: "Which requirements are not covered by any code component?"
  - A: "3 requirements from PRD-v2.pdf have no linked code: payment retry logic, session timeout..."
- Title: `Your Organization's Personal GPT`
- Body: `AskyDoc assembles context from your documents and code, then synthesizes answers using Gemini or Claude. No hallucinations — every answer is grounded in your actual data with source citations.`
- Tag pills: `RAG Architecture` `Source Citations` `DB-First Intelligence`

**Section C — Governance & Audit**
- Visual: Audit trail table mockup with timestamps, user actions, diffs
- Title: `Complete Governance Out of the Box`
- Body: `Every change is tracked. Every document goes through an approval chain. Every access is logged. DokyDoc gives compliance teams a full audit trail without any extra configuration.`
- Tag pills: `Approval Workflows` `RBAC` `Audit Trail`

---

#### Section 7 — Use Cases by Role
- **Layout:** Tabbed interface (tabs: CXO | Developer | Business Analyst | Product Manager | Auditor)
- **Each tab shows:**
  - Left: Role-specific description + bullet points of what they can do
  - Right: Dashboard screenshot/mockup for that role

| Role | Key Points |
|---|---|
| CXO | Business impact analysis, billing visibility, strategic knowledge insights |
| Developer | Code-doc mismatch detection, repository analysis, semantic code search |
| Business Analyst | Requirements traceability, gap analysis, coverage metrics |
| Product Manager | Feature documentation, analysis viewing, ontology browsing |
| Auditor | Read-only audit logs, compliance reporting, change history |

---

#### Section 8 — Social Proof / Testimonials
- **Layout:** Dark section, 3-column testimonial cards
- **Each card:** Quote, name, role, company logo
- *(Use placeholder testimonials for launch, replace when real ones exist)*

```
"DokyDoc cut our documentation review time by 60%. The mismatch
 detection alone saved us 2 sprints of rework."
— Engineering Lead, Series B Startup

"AskyDoc is like having a documentation expert available 24/7.
 Our analysts love it."
— Head of Product, Enterprise SaaS

"Finally, a platform that treats docs as first-class citizens
 in the dev workflow."
— CTO, Tech Consultancy
```

---

#### Section 9 — Integration Logos
- **Layout:** Light section, "Works with your stack" heading
- **Logo grid:** GitHub, GitLab, Notion, Jira, Slack, Google Drive, Confluence
- Subtitle: `More integrations coming soon.`

---

#### Section 10 — Pricing Teaser
- **Layout:** Light background, centered
- **Heading:** `Simple, Transparent Pricing`
- **3 cards:** Starter / Pro / Enterprise
- Link to full `/pricing` page

| Plan | Price | Highlights |
|---|---|---|
| Starter | Free / $0 | 3 users, 10 docs, 1 repo, community support |
| Pro | $49/mo per org | 20 users, unlimited docs, 5 repos, AskyDoc |
| Enterprise | Custom | Unlimited, SSO, on-prem option, dedicated support |

---

#### Section 11 — CTA Banner
- **Layout:** Full-width, gradient background (`--gradient-cta`)
- **Heading:** `Start Governing Your Knowledge Today`
- **Subtext:** `Free trial. No credit card required. Up and running in minutes.`
- **Buttons:** `Start Free Trial` (white filled) + `Talk to Sales` (white ghost)

---

#### Section 12 — Footer
- **Columns:**
  - Col 1: VizaiLabs logo + tagline + social links (Twitter/X, LinkedIn, GitHub)
  - Col 2: Product — Features, Pricing, Changelog, Roadmap
  - Col 3: Company — About, Blog, Careers, Press
  - Col 4: Resources — Docs, API Reference, Status, Support
  - Col 5: Legal — Privacy Policy, Terms of Service, Security

- **Bottom bar:** `© 2026 VizaiLabs. All rights reserved.`

---

### PAGE 2: FEATURES (`/features`)

Full detailed breakdown of every feature with:
- Hero: "Everything you need to govern your documentation"
- Feature categories as anchor-linked sections:
  1. Document Analysis Engine
  2. Code Intelligence
  3. Business Ontology Engine
  4. AskyDoc AI Assistant
  5. Governance & Compliance
  6. Multi-Tenancy & Billing
  7. Integrations
- Each feature: icon + title + 3-4 sentence description + screenshot/mockup

---

### PAGE 3: USE CASES (`/use-cases`)

- **Hero:** "DokyDoc works for every role in your organization"
- **6 use-case cards** (each links to a dedicated sub-page):
  - `/use-cases/engineering` — Code-doc alignment for dev teams
  - `/use-cases/business-analysis` — Requirements traceability
  - `/use-cases/product` — Product knowledge management
  - `/use-cases/compliance` — Audit trail and governance
  - `/use-cases/knowledge-management` — Cross-project ontology
  - `/use-cases/ai-assistant` — Natural language querying

---

### PAGE 4: PRICING (`/pricing`)

- **Hero:** "Pricing that scales with your team"
- **Toggle:** Monthly / Annual (Annual = 20% discount)
- **3 pricing tiers** (detailed cards):

**Starter — Free**
- 3 team members
- 10 documents
- 1 repository
- Basic AI analysis (10 runs/month)
- Community support
- CTA: `Get Started Free`

**Pro — $49/month/org**
- 20 team members
- Unlimited documents
- 5 repositories
- Full AI analysis (200 runs/month)
- AskyDoc AI assistant (100 queries/month)
- Email support + 48h SLA
- CTA: `Start Free Trial`

**Enterprise — Custom**
- Unlimited everything
- SSO / SAML
- On-premise deployment option
- Dedicated CSM
- SLA guarantee
- Custom AI cost limits
- CTA: `Talk to Sales`

- **FAQ Section** (8-10 questions about billing, AI costs, data privacy, etc.)
- **Comparison Table** at bottom showing feature-by-feature breakdown

---

### PAGE 5: ABOUT (`/about`)

- Company story: VizaiLabs — who we are, why we built DokyDoc
- Mission statement: "Making organizational knowledge reliable, queryable, and alive"
- Team section (photos, names, roles)
- Values: Speed, Trust, Transparency, Intelligence
- CTA: Join the team (link to careers)

---

### PAGE 6: CONTACT / DEMO (`/contact`)

- **Left side:** Contact info + what to expect in a demo
- **Right side:** Form with fields:
  - Full Name
  - Work Email
  - Company Name
  - Team Size (dropdown: 1-10 / 11-50 / 51-200 / 200+)
  - Primary Use Case (dropdown)
  - Message (optional)
  - Submit button: `Request a Demo`
- On submit: send email via Resend API + show success state

---

## 6. COMPONENT LIBRARY

```
/components
  /layout
    Navbar.tsx          ← sticky, transparent → blur on scroll
    Footer.tsx
    MobileMenu.tsx
  /sections
    Hero.tsx
    ProblemStatement.tsx
    HowItWorks.tsx
    FeatureGrid.tsx
    FeatureDeepDive.tsx
    UseCaseTabs.tsx
    Testimonials.tsx
    IntegrationLogos.tsx
    PricingCards.tsx
    CTABanner.tsx
  /ui
    Button.tsx          ← variants: primary, ghost, outline
    Badge.tsx           ← pill tags
    Card.tsx
    Tabs.tsx
    Accordion.tsx       ← FAQ
    AnimatedCounter.tsx ← for stat numbers
    GradientText.tsx    ← for hero headings
    BrowserMockup.tsx   ← wraps dashboard screenshots
    ChatMockup.tsx      ← AskyDoc demo
  /icons
    (custom SVG icons for each feature)
```

---

## 7. ANIMATIONS & INTERACTIONS

| Element | Animation | Library |
|---|---|---|
| Hero heading | Fade up + stagger on load | Framer Motion |
| Hero dashboard mockup | Subtle float + glow pulse | CSS keyframes |
| Stats in Problem section | Count-up animation on scroll | Custom hook + Intersection Observer |
| How-It-Works steps | Draw connecting line on scroll | Framer Motion path animation |
| Feature cards | Fade-in-up on scroll | Framer Motion whileInView |
| Ontology graph | Animated nodes with Spring physics | D3.js or react-force-graph |
| Chat mockup | Typewriter effect for AI response | Custom component |
| CTA button | Gradient shimmer on hover | CSS animation |
| Navbar | Backdrop blur transition | CSS transition |

---

## 8. SEO STRATEGY

### Meta Tags (per page)
```html
<!-- Home -->
<title>DokyDoc — AI-Powered Document Analysis & Governance | VizaiLabs</title>
<meta name="description" content="DokyDoc transforms your documents and code into a living knowledge graph with AI analysis, mismatch detection, and an AI assistant. Built for engineering teams." />

<!-- Features -->
<title>Features — DokyDoc AI Document Intelligence Platform</title>

<!-- Pricing -->
<title>Pricing — DokyDoc | Start Free, Scale as You Grow</title>
```

### Target Keywords
- Primary: `AI document analysis`, `documentation governance platform`, `code documentation alignment`
- Secondary: `knowledge graph software`, `document intelligence`, `AI document management`
- Long-tail: `how to keep documentation in sync with code`, `AI-powered knowledge base for engineering teams`

### Technical SEO
- Sitemap: `/sitemap.xml` (auto-generated by Next.js)
- Robots: `/robots.txt`
- Open Graph images: Custom OG image per page (1200×630px)
- Structured data: `SoftwareApplication` schema for the product
- Core Web Vitals: Target LCP < 2.5s, CLS < 0.1, INP < 200ms

---

## 9. RESPONSIVE DESIGN BREAKPOINTS

```
Mobile:  375px–767px   → Single column, hamburger nav, stacked cards
Tablet:  768px–1023px  → 2-column grids, simplified hero
Desktop: 1024px–1279px → Full layout
Wide:    1280px+       → Max-width 1280px centered, wider spacing
```

---

## 10. PERFORMANCE TARGETS

- Lighthouse Score: ≥ 90 on all categories
- First Contentful Paint: < 1.5s
- Images: WebP format, lazy loading, Next.js `<Image>` component
- Fonts: Self-hosted Geist (subset), `font-display: swap`
- JS bundle: Code-split per route, dynamic imports for heavy components (D3, Mermaid)

---

## 11. FOLDER STRUCTURE

```
dokydoc-website/
├── app/
│   ├── layout.tsx          ← root layout, fonts, analytics
│   ├── page.tsx            ← Home
│   ├── features/page.tsx
│   ├── use-cases/
│   │   ├── page.tsx
│   │   └── [slug]/page.tsx
│   ├── pricing/page.tsx
│   ├── about/page.tsx
│   ├── contact/page.tsx
│   ├── blog/
│   │   ├── page.tsx
│   │   └── [slug]/page.tsx
│   ├── privacy/page.tsx
│   └── terms/page.tsx
├── components/
│   ├── layout/
│   ├── sections/
│   └── ui/
├── lib/
│   ├── utils.ts
│   └── resend.ts           ← email sending
├── public/
│   ├── images/
│   │   ├── logo.svg
│   │   ├── hero-mockup.png
│   │   └── og-default.png
│   └── fonts/
├── styles/
│   └── globals.css         ← Tailwind + CSS variables
├── content/
│   └── blog/               ← MDX blog posts
├── next.config.ts
├── tailwind.config.ts
└── package.json
```

---

## 12. CONTENT COPY — KEY HEADLINES

```
Hero H1:         "Your Documents Know More Than You Think."
Hero Sub:        "DokyDoc uses multi-pass AI to turn your documents and code
                  into a living knowledge graph — with governance, alignment
                  checks, and an AI assistant built in."

Features H2:     "Everything Your Team Needs to Know, Always Up to Date."

How It Works H2: "From Chaos to Clarity in Three Steps."

Ontology H2:     "A Living Map of Your Organization's Knowledge."

AskyDoc H2:      "Ask Anything. Get Answers From Your Own Data."

Governance H2:   "Compliance Without the Overhead."

CTA H2:          "Start Governing Your Knowledge Today."

Pricing H2:      "Simple Pricing. Serious Power."

About H2:        "We Built DokyDoc Because We Felt the Pain."
```

---

## 13. LAUNCH CHECKLIST FOR DEVELOPER

- [ ] Init Next.js 15 project with App Router
- [ ] Install dependencies: Tailwind 4, Framer Motion, Lucide React, React Hook Form, Zod, Resend
- [ ] Set up global CSS variables and Tailwind config with color system above
- [ ] Self-host Geist fonts (download from Vercel Fonts)
- [ ] Build Navbar + Footer components first
- [ ] Build all UI primitives (Button, Card, Badge, Tabs)
- [ ] Build Home page section by section (top to bottom)
- [ ] Create dashboard mockup images (Figma or screenshots) for visuals
- [ ] Build Features, Use Cases, Pricing, About, Contact pages
- [ ] Set up Resend for contact form emails
- [ ] Add PostHog snippet for analytics
- [ ] Configure `next-sitemap` for sitemap generation
- [ ] Add OG images using `next/og`
- [ ] Test on mobile (375px), tablet (768px), desktop (1280px)
- [ ] Run Lighthouse audit and fix issues
- [ ] Deploy to Vercel, add custom domain
- [ ] Submit sitemap to Google Search Console

---

## 14. ESTIMATED EFFORT (FOR PLANNING)

| Phase | Scope | Effort |
|---|---|---|
| Phase 1 | Setup + Home page | 3–4 days |
| Phase 2 | Features + Use Cases + Pricing | 2–3 days |
| Phase 3 | About + Contact + Blog skeleton | 1–2 days |
| Phase 4 | Animations + polish + responsive | 2 days |
| Phase 5 | SEO + performance + deployment | 1 day |
| **Total** | | **~9–12 days (1 developer)** |

---

*Plan authored for VizaiLabs / DokyDoc — March 2026*
