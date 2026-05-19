# Tamasha Events — Phase 1 Handoff Document

> **Status:** Phase 1 Complete  
> **Next Phase:** Phase 2 — Authentication & Organizer Onboarding  
> **Django Version:** 6.0.5 | **Python:** 3.14+ | **DB:** PostgreSQL

---

## 1. Project Overview

**Tamasha Events** is a premium event ticketing platform for Tanzania.  
Stack: Django 6.x · PostgreSQL · Bootstrap 5 · jQuery · Celery + Redis · AzamPay · Africa's Talking · PWA

**Domain:** www.tamasha.co.tz (prod) · http://127.0.0.1:8000 (dev)  
**Brand colors:** Gold `#C9A84C` on dark `#0D0D0D` (primary) / ivory `#F5F0E8` (light mode)

---

## 2. Folder Structure

```
tamasha/                          ← project root (manage.py lives here)
├── apps/                         ← all Django apps
│   ├── __init__.py
│   ├── accounts/
│   ├── checkin/
│   ├── core/
│   ├── dashboard/
│   ├── events/
│   ├── notifications/
│   ├── payments/
│   ├── seo/
│   └── tickets/
├── config/                       ← Django project package (startproject config .)
│   ├── __init__.py               ← imports celery app
│   ├── asgi.py
│   ├── celery.py
│   ├── settings/
│   │   ├── __init__.py           ← empty
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
├── static/
│   ├── css/
│   │   ├── theme.css             ← design tokens only (no Bootstrap overrides)
│   │   └── base.css              ← resets + typography + Bootstrap overrides
│   ├── js/
│   │   ├── theme.js              ← FART prevention + theme toggle
│   │   └── toasts.js             ← server toast init + showToast() global
│   ├── images/
│   │   ├── icons/
│   │   │   ├── icon-192.png      ← PWA icon (placeholder, replace in Phase 9)
│   │   │   └── icon-512.png      ← PWA icon (placeholder, replace in Phase 9)
│   │   ├── favicon.ico
│   │   ├── apple-touch-icon.png
│   │   └── og-default.jpg        ← default OG share image
│   └── vendor/
│       ├── bootstrap.min.css
│       ├── bootstrap.bundle.min.js
│       ├── bootstrap-icons.min.css
│       └── fonts/
│           ├── bootstrap-icons.woff
│           └── bootstrap-icons.woff2
├── templates/
│   ├── base.html                 ← semantic SEO shell, dual-theme aware
│   ├── components/
│   │   ├── _navbar.html
│   │   ├── _footer.html
│   │   ├── _toasts.html
│   │   └── _skeleton.html
│   ├── core/
│   │   └── home.html
│   └── seo/
│       └── robots.txt
├── .env                          ← secrets (never commit)
├── .env.example
├── manage.py
└── requirements.txt
```

---

## 3. Installed Packages (requirements.txt / pip freeze)

```
africastalking==2.0.2
celery==5.6.3
Django==6.0.5
django-axes==8.3.1
django-celery-beat==2.9.0
django-celery-results==2.6.0
django-csp==4.0
django-debug-toolbar==6.3.0
django-environ==0.13.0
django-markdownx==4.0.9
django-ratelimit==4.1.0
pillow==12.2.0
psycopg==3.3.4
psycopg-binary==3.3.4
qrcode==8.2
redis==7.4.0
requests==2.34.2
whitenoise==6.12.0
```

> **Note:** Bootstrap 5.3.3 and Bootstrap Icons 1.11.3 are served locally from `static/vendor/` — NOT from CDN. This was necessary because django-csp blocked their CDN requests in development.

---

## 4. Key Configuration Decisions

### 4.1 Settings Module
- `DJANGO_SETTINGS_MODULE=config.settings.development`
- Split into `base.py` / `development.py` / `production.py`
- All secrets via `django-environ` reading `.env` at project root

### 4.2 Custom User Model
- `AUTH_USER_MODEL = 'accounts.CustomUser'`
- Uses `AbstractBaseUser` + `PermissionsMixin`
- `USERNAME_FIELD = 'email'` (no username field)

### 4.3 Task Queue
- **Celery + Redis in BOTH dev and prod** (no django-q2)
- `CELERY_RESULT_BACKEND = 'django-db'` (django-celery-results)
- Beat scheduler: `django_celery_beat.schedulers:DatabaseScheduler`

### 4.4 CSP (django-csp 4.0)
- Uses new `CONTENT_SECURITY_POLICY = {'DIRECTIVES': {...}}` format
- Old flat `CSP_*` keys do NOT work with v4.0

### 4.5 Bootstrap Vendor Strategy
- Bootstrap served from `static/vendor/` (local)
- Load order in `base.html`: `theme.css` → `bootstrap.min.css` → `bootstrap-icons.min.css` → `base.css`
- Bootstrap overrides live in `base.css` (loads after Bootstrap) using `!important` for specificity

### 4.6 Theme System
- CSS tokens in `theme.css` (shared, dark, light)
- Dark mode is the default theme
- FART prevention: inline `<script>` in `<head>` reads localStorage before first paint
- Full toggle logic in `static/js/theme.js`
- Theme sync URL `accounts:theme_sync` exists as a stub — real implementation in Phase 2
- Authenticated users: theme preference stored in `CustomUser.theme_preference` DB field
- Anonymous users: localStorage only

### 4.7 Email
- SMTP (Gmail) used in both dev and prod
- App Password configured (not raw Gmail password)
- `ADMIN_NOTIFICATION_EMAIL` setting added for admin alerts

---

## 5. Apps & Their Current State

| App | Status | Notes |
|-----|--------|-------|
| `accounts` | Models + admin done, views/forms = Phase 2 | CustomUser, OrganizerProfile, managers, handlers |
| `core` | Working | HomeView, static pages, ManifestView, context processors |
| `seo` | Complete | SEOMixin, NoIndexMixin, structured data, slugs, canonical, sitemap, robots.txt |
| `events` | Stub only | urls.py has list/create stubs pointing to placeholder templates |
| `tickets` | Stub only | Empty urls.py |
| `dashboard` | Stub only | buyer/organizer stubs |
| `checkin` | Stub only | Empty urls.py |
| `payments` | Stub only | Empty urls.py |
| `notifications` | Stub only | Empty urls.py |

---

## 6. Models Built (Phase 1)

### `accounts.CustomUser` (AbstractBaseUser)
```
email               EmailField (USERNAME_FIELD, unique)
full_name           CharField(255)
phone               CharField(20, blank=True)
avatar              ImageField(upload_to='avatars/', nullable)
is_organizer        BooleanField(default=False)
organizer_status    CharField choices: NONE|PENDING|APPROVED|REJECTED
theme_preference    CharField choices: dark|light (default: dark)
is_active           BooleanField(default=True)
is_staff            BooleanField(default=False)
date_joined         DateTimeField(default=timezone.now)
email_verified      BooleanField(default=False)
email_verified_at   DateTimeField(nullable)
```

Properties: `is_pending_organizer`, `is_approved_organizer`, `is_rejected_organizer`

### `accounts.OrganizerProfile` (OneToOne → CustomUser)
```
user                OneToOneField(CustomUser, related_name='organizer_profile')
organization_name   CharField(255)
bio                 TextField(blank=True)
website             URLField(blank=True)
approved_at         DateTimeField(nullable)
approved_by         ForeignKey(CustomUser, nullable, related_name='organizer_approvals')
```

---

## 7. URL Namespaces

| Namespace | Prefix | Status |
|-----------|--------|--------|
| `core` | `/` | Active |
| `accounts` | `/accounts/` | Stub (Phase 2) |
| `events` | `/events/` | Stub (Phase 3) |
| `tickets` | `/tickets/` | Stub (Phase 4) |
| `dashboard` | `/dashboard/` | Stub (Phase 6) |
| `checkin` | `/checkin/` | Stub (Phase 7) |

### Named URLs currently in use across templates:
```
core:home, core:about, core:contact, core:help, core:terms, core:privacy, core:manifest
accounts:login, accounts:signup, accounts:logout, accounts:profile,
accounts:become_organizer, accounts:theme_sync
events:list, events:create
dashboard:buyer, dashboard:organizer
```

---

## 8. Template Architecture

### `templates/base.html`
- `{% block seo %}` — includes `seo/_meta.html` partial
- `{% block structured_data %}` — includes `seo/_json_ld.html` partial
- `{% block extra_css %}` — page-specific CSS
- `{% block content %}` — main page content
- `{% block extra_js %}` — page-specific JS
- Context vars available everywhere: `current_theme`, `SITE_NAME`, `SITE_DOMAIN`, `SITE_DESCRIPTION`, `user`

### `templates/components/_skeleton.html`
Usage: `{% include "components/_skeleton.html" with type="card" %}`  
Types: `card` | `event-card` | `text` | `heading` | `avatar` | `table`

### `templates/components/_toasts.html`
Renders Django messages as Bootstrap toasts automatically.  
JS programmatic usage: `window.showToast('message', 'success'|'danger'|'warning'|'info')`

---

## 9. SEO App (`apps/seo/`)

### Files
```
apps/seo/
├── __init__.py
├── apps.py
├── mixins.py          ← SEOMixin, NoIndexMixin
├── structured_data.py ← JSON-LD generators (organization, website, breadcrumb, event, faq)
├── sitemaps.py        ← StaticViewSitemap, EventSitemap (lazy-loads Event model)
├── slugs.py           ← generate_unique_slug()
└── canonical.py       ← build_canonical(), clean_query_string()
```

### Using SEOMixin in a view
```python
from apps.seo.mixins import SEOMixin

class EventDetailView(SEOMixin, DetailView):
    seo_title       = "Event Name — Tamasha Events"
    seo_description = "..."
    seo_og_type     = "event"

    def get_seo_title(self):
        return f"{self.object.title} — {settings.SITE_NAME}"
```

### Using structured data in a view
```python
from apps.seo.structured_data import breadcrumb_schema, render_json_ld

def get_context_data(self, **kwargs):
    ctx = super().get_context_data(**kwargs)
    ctx['structured_data'] = [
        render_json_ld(breadcrumb_schema([
            ('Home', '/'),
            ('Events', '/events/'),
            (self.object.title, self.request.path),
        ], self.request))
    ]
    return ctx
```

---

## 10. Changes vs. Original Implementation Plan

| Item | Plan | Actual | Reason |
|------|------|--------|--------|
| Task queue | Celery (prod) + django-q2 (dev) | Celery + Redis in both | Simpler, no dual-backend abstraction |
| Bootstrap delivery | CDN | Local `static/vendor/` | django-csp blocked CDN in dev |
| Bootstrap overrides | In `theme.css` | Moved to `base.css` | Specificity — overrides must load after Bootstrap |
| `--color-text-muted` dark mode | `#888888` (original palette) | `#999999` | WCAG AA compliance fix (contrast ratio ~5.1:1) |
| CSP format | Old flat `CSP_*` keys | New `CONTENT_SECURITY_POLICY` dict | django-csp 4.0 breaking change |
| `OrganizerProfileInline` | No `fk_name` | Added `fk_name = 'user'` | Two FKs to CustomUser caused admin.E202 |

---

## 11. Environment Variables (.env)

```env
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_SETTINGS_MODULE=config.settings.development
DB_NAME=tamasha_db
DB_USER=postgres
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432
REDIS_URL=redis://localhost:6379/0
COMMISSION_RATE=0.03
AFRICASTALKING_USERNAME=sandbox
AFRICASTALKING_API_KEY=
AFRICASTALKING_SENDER_ID=45
AZAMPAY_APP_NAME=
AZAMPAY_CLIENT_ID=
AZAMPAY_CLIENT_SECRET=
AZAMPAY_BASE_URL=https://sandbox.azampay.co.tz
SITE_DOMAIN=http://127.0.0.1:8000
SERVER_EMAIL=errors@tamasha.co.tz
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=          ← Gmail App Password
DEFAULT_FROM_EMAIL=Tamasha Events <noreply@tamasha.co.tz>
ADMIN_NOTIFICATION_EMAIL=
```

---

## 12. Working URLs (Phase 1)

| URL | View | Status |
|-----|------|--------|
| `/` | `core:home` | ✅ Working |
| `/sitemap.xml` | Django sitemaps | ✅ Working |
| `/robots.txt` | `seo/robots.txt` template | ✅ Working |
| `/manifest.json` | `core:manifest` | ✅ Working |
| `/about/` | `core:about` | ✅ Stub template needed |
| `/contact/` | `core:contact` | ✅ Stub template needed |
| `/help/` | `core:help` | ✅ Stub template needed |
| `/terms/` | `core:terms` | ✅ Stub template needed |
| `/privacy/` | `core:privacy` | ✅ Stub template needed |
| `/admin/` | Django admin | ✅ Working |

---

## 13. Phase 2 Scope — Authentication & Organizer Onboarding

### 2.1 Auth Flows
- Signup (email + password) — AJAX form with inline validation
- Login — email/password, remember-me, redirect-next
- Logout (POST only, CSRF protected)
- Password reset via email (Django built-in + custom templates)
- Email verification on signup (token-based, Celery async task)
- Profile page — edit `full_name`, `phone`, `avatar`, `theme_preference`
- **Theme sync endpoint** — replace `ThemeSyncStubView` in `apps/accounts/urls.py` with real view that saves `theme_preference` to `CustomUser`

### 2.2 Become an Organizer Flow
- `OrganizerRequest` model (stores every submission, audit trail)
- `OrganizerRequestForm` — organization_name, bio, phone, website, pitch
- Submission sets `organizer_status = PENDING`
- Admin action: approve/reject with mandatory `rejection_reason`
- SMS notification on approval/rejection (Africa's Talking)
- Status page on profile showing Pending/Approved/Rejected + rejection reason
- Re-apply flow for rejected users

### 2.3 Permission Mixins
- `OrganizerRequiredMixin`
- `VerifiedUserMixin`
- `AnonymousRedirectMixin`

### 2.4 Templates needed
```
templates/accounts/
├── login.html
├── signup.html
├── logout.html          ← or just POST redirect, no template needed
├── profile.html
├── become_organizer.html
├── organizer_status.html
├── email_verification_sent.html
├── email_verified.html
├── password_reset.html
├── password_reset_done.html
├── password_reset_confirm.html
├── password_reset_complete.html
└── lockout.html         ← already referenced in handlers.py
```

### 2.5 Real URL replacements in `apps/accounts/urls.py`
All current stubs (`TemplateView`) must be replaced with real CBVs.

---

## 14. Code Standards Reminder

- All business logic in `services.py` or model methods — never in views
- CBVs preferred, mixins for permission layers
- All forms via Django Forms/ModelForms — never raw POST
- AJAX form submissions with loading/submitting state management
- CSRF protection on all state-changing endpoints
- Never put HTML, CSS, JS in the same file
- Page-specific CSS → `static/css/accounts/page.css`
- Page-specific JS → `static/js/accounts/page.js`
- QuerySets: always use `select_related`/`prefetch_related` where applicable
- `NoIndexMixin` on all dashboard/profile/auth pages
