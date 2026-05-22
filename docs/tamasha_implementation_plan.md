# Tamasha Events — Implementation Plan
> Stack: Django 6.x · DRF (lightweight) · PostgreSQL · Bootstrap 5 · jQuery · Celery/Redis · AzamPay · Africa's Talking · PWA

---

## Architecture Decisions (Pre-Phase)

### Dual-Role User Model
A single `CustomUser` (AbstractBaseUser) carries both roles. A user is simultaneously a `Buyer` and a potential `Organizer` — no separate accounts.

```
CustomUser
├── is_organizer        → BooleanField (approved by admin)
├── organizer_status    → choices: NONE | PENDING | APPROVED | REJECTED
└── OrganizerProfile    → OneToOne (created on approval)
```

This eliminates the "two-account" problem entirely. Role checks happen at the view/service layer via mixins.

### App Decomposition

| App | Responsibility |
|---|---|
| `accounts` | CustomUser, auth, organizer onboarding |
| `events` | Event model, categories, slugs |
| `tickets` | TicketType, Order, OrderItem, QR generation |
| `payments` | AzamPay integration, transaction records |
| `checkin` | QR scan, venue staff interface |
| `dashboard` | Organizer + buyer dashboards |
| `notifications` | SMS via Africa's Talking, in-app |
| `seo` | Mixins, structured data, sitemap, metadata |
| `core` | Shared utilities, base views, context processors |

---

## Phase 1 — Project Bootstrap & Foundation
**Goal:** Runnable project, correct structure, no technical debt introduced from day one.

### 1.1 Project Scaffold
- [ ] `django-admin startproject tamasha .` inside `tamasha/`
- [ ] Create `tamasha/apps/` and register `INSTALLED_APPS` with full dotted paths
- [ ] Configure `django-environ` — `.env` + `.env.example` committed, secrets never in code
- [ ] `settings/` split: `base.py`, `development.py`, `production.py`
- [ ] PostgreSQL configured in `base.py` via env vars
- [ ] Static/media directory structure established
- [ ] `tamasha/static/css/theme.css` — CSS custom properties wired from `tamasha_palette.css`
- [ ] `tamasha/static/js/theme.js` — centralized theme toggle with FART prevention (inline `<script>` in `<head>` reads localStorage before first paint)
- [ ] Base template `tamasha/templates/base.html` — semantic, SEO-ready shell with theme `data-theme` on `<html>`

### 1.2 Custom User Model (`accounts`)
- [ ] `CustomUser` extends `AbstractBaseUser` + `PermissionsMixin`
- [ ] `CustomUserManager` — `create_user`, `create_superuser`
- [ ] Fields: `email` (USERNAME_FIELD), `full_name`, `phone`, `avatar`, `is_organizer`, `organizer_status`, `theme_preference`, `date_joined`, `is_active`
- [ ] `AUTH_USER_MODEL = 'accounts.CustomUser'`
- [ ] `OrganizerProfile` OneToOne — `bio`, `organization_name`, `website`, `approved_at`, `approved_by`
- [ ] Initial migration — **never touch again once in production**

### 1.3 Design System Foundation
- [ ] `theme.css` tokens mapped from palette — all components use `var(--*)` only
- [ ] `base.css` — resets, typography scale, shared utility classes
- [ ] Navbar component (glassmorphism, blur backdrop, theme-aware)
- [ ] Footer component
- [ ] Button variants (`btn-primary`, `btn-secondary`, `btn-outline-primary`) as defined in palette
- [ ] Toast notification component (JS-driven, ARIA-compliant)
- [ ] Skeleton loader CSS component
- [ ] Responsive breakpoints: 320 / 375 / 425 / 768 / 1024 / 1440px

### 1.4 SEO App (`seo`)
- [ ] `SEOMixin` — injects `title`, `description`, `canonical`, OG, Twitter Card into context
- [ ] `StructuredDataMixin` — JSON-LD generator base class
- [ ] `SitemapView` — dynamic XML sitemap (events, public pages)
- [ ] `robots.txt` view — excludes `/admin/`, `/dashboard/`, `/api/`
- [ ] SEO partials: `_seo_meta.html`, `_og_tags.html`, `_json_ld.html`

---

## Phase 2 — Authentication & Organizer Onboarding
**Goal:** Full auth flow + dual-role onboarding working end-to-end.

### 2.1 Auth Flows
- [ ] Signup (email + password) — AJAX form, inline validation
- [ ] Login — email/password, remember-me, redirect-next
- [ ] Logout
- [ ] Password reset via email (Django's built-in + custom templates)
- [ ] Email verification on signup (token-based, Celery task in prod / django-q2 in dev)
- [ ] Profile page — edit `full_name`, `phone`, `avatar`, `theme_preference`

### 2.2 Become an Organizer Flow
- [ ] `OrganizerRequestForm` — `organization_name`, `bio`, `phone`, `website`, reason/pitch
- [ ] Submission sets `organizer_status = PENDING`
- [ ] Admin action in Django Admin to `approve` / `reject` — triggers:
  - `is_organizer = True` + `OrganizerProfile` created on approval
  - SMS notification via Africa's Talking
  - Status update email
- [ ] User sees their application status on profile page (badge: Pending / Approved / Rejected)
- [ ] `OrganizerRequest` model stores every submission as a separate row — never overwrite; `organizer_status` on `CustomUser` is always derived from the latest request's state, giving admin full audit trail of all attempts and what changed between submissions
- [ ] Rejected users can re-apply immediately — admin must provide a rejection reason, user reads it on their profile/status page and resubmits
- [ ] `rejection_reason` is a mandatory `TextField` enforced at model/form level when action is `REJECT` — admin cannot reject without providing a reason or the action fails with a validation error

### 2.3 Permission Architecture
- [ ] `OrganizerRequiredMixin` — checks `user.is_organizer`
- [ ] `VerifiedUserMixin` — checks email verification
- [ ] `AnonymousRedirectMixin` — redirects to login with `?next=` for protected actions
- [ ] All permission checks in mixins/service layer — never in templates

---

## Phase 3 — Events
**Goal:** Full event lifecycle — creation, discovery, detail, SEO.

### 3.1 Event Model (`events`)
- [ ] `Category` — name, slug, icon (Bootstrap Icon name), sort_order
- [ ] `Venue` — name, address, city, coordinates (lat/lng for structured data), capacity
- [ ] `EventCollaborator` — FK `Event`, FK `OrganizerProfile`, `added_at`, `added_by` (FK primary organizer); read-only access — can view all event analytics, orders, attendees, and check-in data but cannot edit the event or trigger any writes
- [ ] `Event` model:
  - `title`, `slug` (unique, auto-generated with collision handling)
  - `organizer` → FK `OrganizerProfile`
  - `category` → FK `Category`
  - `venue` → FK `Venue`
  - `description` (rich text via `django-markdownx` or plain text)
  - `banner` (validated upload: type + size, served via `/media/`)
  - `starts_at`, `ends_at` (timezone-aware)
  - `status` → choices: `DRAFT | PUBLISHED | CANCELLED | COMPLETED`
  - `is_featured` BooleanField
  - `max_capacity` (nullable — unlimited if null)
  - `tags` (ManyToMany `Tag` model)
  - `seo_title`, `seo_description` (optional overrides)
- [ ] URL: `/events/<slug>/` — human-readable, never ID-only

### 3.2 Event Views
- [ ] `EventListView` — browse, filter by category/date/city, search, pagination
- [ ] `EventDetailView` — full event page with structured data JSON-LD (`@type: Event`)
- [ ] `EventCreateView` — organizer-only, multi-step or single rich form
- [ ] `EventOwnerMixin` — enforces primary organizer ownership at the view layer; collaborator hitting any write URL (edit, delete, manage ticket types) receives a hard 403, not just a hidden UI element; both layers enforced: server-side 403 + UI write actions hidden for collaborators
- [ ] `EventDeleteView` (soft delete — sets `status = CANCELLED`, primary organizer only)
- [ ] `EventCollaboratorManageView` — primary organizer adds/removes collaborators by searching approved organizer accounts; collaborators shown with credits on the public event page
- [ ] Featured events section on homepage/listing

### 3.3 Event Discovery
- [ ] Search: title, tags, category, city (full-text via PostgreSQL `SearchVector`)
- [ ] Filters: category, date range, price range, city
- [ ] Sorting: date, popularity, price
- [ ] Upcoming events widget
- [ ] "Near you" section (optional Phase 3 stretch goal — based on city)

---

## Phase 4 — Ticketing
**Goal:** Ticket types, order creation, QR generation, ticket delivery.

### 4.1 Ticket Models (`tickets`)
- [ ] `TicketType` — FK `Event`, `name` (e.g., VIP, General), `price`, `quantity`, `quantity_sold`, `sale_starts_at`, `sale_ends_at`, `max_per_order`
- [ ] `Order` — FK `CustomUser`, `event`, `status` (PENDING / PAID / CANCELLED / REFUNDED), `reference` (UUID4), `total_amount`, `platform_fee` (3%), `organizer_amount` (97%), `created_at`
- [ ] `OrderItem` — FK `Order`, FK `TicketType`, `quantity`, `unit_price`, `subtotal`
- [ ] `Ticket` — FK `OrderItem`, `token` (UUID4, single-use), `is_used`, `used_at`, `used_by` (FK staff user), `qr_image` (generated server-side via `qrcode` lib)
- [ ] Commission rate loaded from settings/db — never hardcoded

### 4.2 Ticket Purchase Flow
- [ ] Ticket selection UI on event detail page (AJAX quantity picker)
- [ ] Order creation endpoint — validates availability, locks quantity (select_for_update)
- [ ] CSRF protected; rate-limited (django-ratelimit)
- [ ] Redirect to payment

### 4.3 QR Generation & Delivery
- [ ] Server-side QR code generated per `Ticket.token` on order confirmation
- [ ] Stored as image in `/media/tickets/qr/`
- [ ] Async delivery (Celery/django-q2): SMS link + in-app ticket view
- [ ] Ticket detail page: `/tickets/<order_reference>/` — mobile-optimized, PWA-cached for offline viewing

---

## Phase 5 — Payments (AzamPay)
**Goal:** Secure payment flow, webhook handling, commission tracking.

### 5.1 Payment Models (`payments`)
- [ ] `Transaction` — FK `Order`, `provider` (AZAMPAY), `provider_reference`, `amount`, `currency`, `status` (INITIATED / SUCCESS / FAILED), `raw_payload` (JSONField), `created_at`, `updated_at`
- [ ] `OrganizerPayout` — FK `OrganizerProfile`, `amount`, `status` (PENDING / PAID), `triggered_by` (FK admin user), `paid_at`

### 5.2 AzamPay Integration
- [ ] AzamPay service class in `payments/services.py` — token fetch, push USSD, callback verification
- [ ] All API keys via `django-environ`
- [ ] Webhook endpoint — verifies signature, updates `Transaction` + `Order` status
- [ ] Idempotent webhook handling (duplicate callbacks ignored via `provider_reference` unique constraint)
- [ ] On payment success: async task triggers ticket QR generation + SMS delivery

### 5.3 Commission
- [ ] `Order.platform_fee = total * COMMISSION_RATE` — `COMMISSION_RATE` from settings
- [ ] `Order.organizer_amount = total - platform_fee`
- [ ] Payout dashboard for admin — shows pending payouts per organizer
- [ ] Manual payout trigger by Super Admin (Phase 1 of payout — automated later)

---

## Phase 6 — Admin Portal (`dashboard/admin_*` or dedicated `admin_portal` app)
**Goal:** Full custom admin interface replacing Django's default `/admin/`. Superusers and designated staff manage the entire platform from here.

### 6.1 Access & Layout
- [ ] Dedicated URL prefix `/portal/` — entirely separate from `/admin/` (Django admin disabled or restricted to superuser-only for emergencies)
- [ ] `SuperAdminRequiredMixin` — `is_staff + is_superuser` gate on all portal views
- [ ] `StaffRequiredMixin` — `is_staff` gate for limited staff views (e.g. read-only reports)
- [ ] Portal base template — sidebar navigation, breadcrumbs, theme-aware, fully responsive

### 6.2 Dashboard Overview
- [ ] Platform-level KPIs: total users, total organizers, total events, total revenue, total tickets sold, platform commission earned
- [ ] Recent signups, recent orders, recent organizer applications
- [ ] Revenue chart (daily/weekly/monthly — Chart.js, theme-aware)
- [ ] Quick-action shortcuts: pending organizer applications, flagged events, pending payouts

### 6.3 User Management
- [ ] Users list — searchable, filterable by role, status, date joined
- [ ] User detail — full profile, organizer status, order history, tickets, login history
- [ ] Activate / deactivate user account
- [ ] Manually verify email
- [ ] Assign / revoke `is_staff` flag
- [ ] Impersonate user (read-only view — for support purposes)

### 6.4 Organizer Application Management
- [ ] Applications list — filterable by status (PENDING / APPROVED / REJECTED)
- [ ] Application detail — full submission, user history, prior rejections with reasons
- [ ] Approve action — creates `OrganizerProfile`, sets `is_organizer = True`, triggers SMS + email notification via Celery
- [ ] Reject action — `rejection_reason` mandatory field enforced; cannot reject without supplying reason; triggers SMS + email notification
- [ ] Full audit trail per applicant — all prior submissions visible inline

### 6.5 Organizer Management
- [ ] Organizers list — search, filter by status, event count, revenue
- [ ] Organizer detail — profile, all their events, total revenue earned, payout history
- [ ] Revoke organizer status (with confirmation + reason)
- [ ] Edit organizer profile fields

### 6.6 Event Management
- [ ] Events list — searchable, filterable by status, category, organizer, date
- [ ] Event detail — full preview, ticket types, sales data, collaborators
- [ ] Force-publish / force-cancel any event
- [ ] Feature / un-feature event (`is_featured` toggle)
- [ ] Delete event (hard delete — superuser only, with confirmation)
- [ ] Moderate event content (flag inappropriate banners or descriptions)

### 6.7 Taxonomy Management
- [ ] **Categories** — CRUD: name, slug, icon (Bootstrap Icon name), sort_order; reorder via drag-and-drop or sort_order field
- [ ] **Tags** — CRUD: name, slug; merge duplicate tags
- [ ] **Venues** — CRUD: name, address, city, lat/lng, capacity; view all events at a venue

### 6.8 Ticket & Order Management
- [ ] Orders list — searchable by reference, user, event; filterable by status
- [ ] Order detail — items, payment transaction, tickets, QR status
- [ ] Manually mark order as PAID (edge case: payment confirmed offline)
- [ ] Issue refund (updates order status to REFUNDED, triggers notification)
- [ ] Tickets list — search by token, filter by event, check-in status
- [ ] Manually invalidate a ticket token (lost/fraudulent)

### 6.9 Payment & Payout Management
- [ ] Transactions list — filterable by status, provider, date range
- [ ] Transaction detail — raw AzamPay payload, timeline
- [ ] Payouts dashboard — per-organizer breakdown: gross revenue, platform fee, organizer amount, paid vs. pending
- [ ] Trigger payout action — marks `OrganizerPayout` as PAID, logs admin user + timestamp
- [ ] Platform commission summary — total earned, by period

### 6.10 Notifications & SMS Logs
- [ ] `NotificationLog` list — filterable by type, status, recipient
- [ ] Retry failed SMS delivery
- [ ] Compose and send a broadcast SMS to all users or a filtered segment (e.g. all ticket holders for a specific event)

### 6.11 Site Configuration
- [ ] `SiteConfig` model (singleton) — editable via portal:
  - `COMMISSION_RATE` (default 3%)
  - `SITE_NAME`, `SITE_DESCRIPTION`, `SUPPORT_EMAIL`
  - Maintenance mode toggle
  - Organizer application open/closed toggle
- [ ] Changes take effect immediately without deployment

### 6.12 Reports & Exports
- [ ] Export any list view to CSV (users, orders, tickets, payouts)
- [ ] Revenue report by date range, category, organizer
- [ ] Attendance report per event

---

## Phase 7 — Dashboards
**Goal:** Organizer analytics + buyer ticket management.

### 7.1 Organizer Dashboard
- [ ] Event list — status badges, quick actions
- [ ] Per-event analytics: tickets sold, revenue, capacity fill %, sales over time (Chart.js, theme-aware)
- [ ] Orders table — searchable, filterable, exportable (CSV)
- [ ] Payout summary — earned vs. pending vs. paid
- [ ] Attendee list per event
- [ ] Collaborator view — same analytics/orders/attendee data as primary organizer but all write actions (edit event, manage ticket types, manage collaborators) hidden/disabled; clearly labelled "Collaborator Access" in the UI

### 7.2 Buyer Dashboard
- [ ] My Tickets — upcoming + past events
- [ ] Ticket detail + QR code display (offline-capable via PWA service worker)
- [ ] Order history
- [ ] Profile management

---

## Phase 8 — Check-in / QR Scanning (`checkin`)
**Goal:** Venue staff scan tickets at the door.

- [ ] `CheckInView` — staff-only role (`is_staff` or custom `is_checkin_staff`)
- [ ] Browser camera via `jsQR` — scans `Ticket.token` from QR
- [ ] AJAX POST to validation endpoint
- [ ] Endpoint: validates token → checks `is_used` → marks used → returns JSON (valid/invalid/already_used)
- [ ] Visual + audio feedback on scan result
- [ ] Works offline-tolerant (PWA caching of check-in UI, sync when back online — stretch goal)
- [ ] Check-in stats live counter on scanner page

---

## Phase 9 — Notifications (`notifications`)
- [ ] Africa's Talking SMS service class
- [ ] Notification triggers: signup confirmation, organizer approval/rejection, order confirmation, ticket delivery link, event reminder (24h before), event cancellation
- [ ] All SMS sent as Celery/django-q2 tasks
- [ ] `NotificationLog` model — tracks delivery status, timestamp, recipient

---

## Phase 10 — PWA
- [ ] `manifest.json` — name, icons, theme_color, display: standalone
- [ ] Service Worker — caches: ticket pages, event details, static assets
- [ ] Offline fallback page
- [ ] Install prompt (custom banner, not browser default)
- [ ] Lighthouse targets: Performance ≥ 90, Accessibility ≥ 95, SEO ≥ 95, Best Practices ≥ 95

---

## Phase 11 — Production Hardening & Deployment
- [ ] `django-csp` — Content Security Policy headers
- [ ] `django-axes` — brute-force login protection
- [ ] `django-ratelimit` — on purchase, auth endpoints
- [ ] Whitenoise for static + `/media/` served via Nginx
- [ ] Gunicorn + Nginx config
- [ ] Celery + Redis supervisor setup
- [ ] SSL via Let's Encrypt
- [ ] `DEBUG = False`, `ALLOWED_HOSTS`, `SECURE_*` settings
- [ ] Sentry error tracking
- [ ] Log rotation + structured logging
- [ ] DB backups (daily cron → off-site)

---

## Phase Sequence Summary

```
Phase 1  →  Bootstrap, structure, design system, SEO app
Phase 2  →  Auth + organizer onboarding
Phase 3  →  Events (CRUD, discovery, SEO)
Phase 4  →  Ticketing (models, purchase flow, QR)
Phase 5  →  Payments (AzamPay, webhooks, commission)
Phase 6  →  Admin portal (full platform management)
Phase 7  →  Dashboards (organizer + buyer)
Phase 8  →  Check-in / QR scanning
Phase 9  →  Notifications (SMS)
Phase 10 →  PWA
Phase 11 →  Production hardening + deployment
```

Each phase is independently shippable. Phases 1–3 can go live as a browsable event listing. Phases 4–5 unlock purchasing. Phases 6–8 complete the operational loop.

---

## Palette Note

`tamasha_palette.css` is solid. One flag worth discussing:

**`--color-text-primary: #F0EBE0` (dark mode) vs. pure white.**
The warm ivory is intentional and premium — keep it. However, `--color-text-muted: #888888` in dark mode against `#0D0D0D` surfaces gives a contrast ratio of ~4.7:1, which barely passes WCAG AA for normal text but **fails** for small text (< 18px normal / < 14px bold). Recommend bumping to `#999999` or `#9A9A9A` (~5.1:1) for muted text in dark mode. Minor change, significant accessibility win.
