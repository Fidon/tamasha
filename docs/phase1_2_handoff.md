# Tamasha Events — Phase 1 & 2 Handoff Document

> **Status:** Phases 1 & 2 Complete  
> **Next Phase:** Phase 3 — Events (CRUD, Discovery, SEO)  
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
tamasha/                                ← project root (manage.py lives here)
├── apps/
│   ├── __init__.py
│   ├── accounts/
│   │   ├── migrations/
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── forms.py
│   │   ├── handlers.py
│   │   ├── managers.py
│   │   ├── mixins.py
│   │   ├── models.py
│   │   ├── services.py
│   │   ├── tasks.py
│   │   ├── urls.py
│   │   └── views.py
│   ├── checkin/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── context_processors.py
│   │   ├── urls.py
│   │   └── views.py
│   ├── dashboard/
│   ├── events/
│   ├── notifications/
│   ├── payments/
│   ├── seo/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── canonical.py
│   │   ├── mixins.py
│   │   ├── sitemaps.py
│   │   ├── slugs.py
│   │   └── structured_data.py
│   └── tickets/
├── config/
│   ├── __init__.py                     ← imports celery app
│   ├── asgi.py
│   ├── celery.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
├── static/
│   ├── css/
│   │   ├── theme.css                   ← design tokens only
│   │   ├── base.css                    ← resets + typography + Bootstrap overrides
│   │   └── accounts/
│   │       ├── auth.css
│   │       ├── profile.css
│   │       └── become_organizer.css
│   ├── js/
│   │   ├── theme.js
│   │   ├── toasts.js
│   │   └── accounts/
│   │       ├── auth.js
│   │       ├── profile.js
│   │       └── become_organizer.js
│   ├── images/
│   │   ├── icons/
│   │   │   ├── icon-192.png
│   │   │   └── icon-512.png
│   │   ├── favicon.ico
│   │   ├── apple-touch-icon.png
│   │   └── og-default.jpg
│   └── vendor/
│       ├── bootstrap.min.css
│       ├── bootstrap.bundle.min.js
│       ├── bootstrap-icons.min.css
│       └── fonts/
│           ├── bootstrap-icons.woff
│           └── bootstrap-icons.woff2
├── templates/
│   ├── base.html
│   ├── components/
│   │   ├── _navbar.html
│   │   ├── _footer.html
│   │   ├── _toasts.html
│   │   └── _skeleton.html
│   ├── core/
│   │   └── home.html
│   ├── accounts/
│   │   ├── emails/
│   │   │   ├── base_email.html
│   │   │   ├── verify_email.html
│   │   │   ├── organizer_approved.html
│   │   │   ├── organizer_rejected.html
│   │   │   └── password_reset.html
│   │   ├── signup.html
│   │   ├── login.html
│   │   ├── email_verification_sent.html
│   │   ├── lockout.html
│   │   ├── profile.html
│   │   ├── become_organizer.html
│   │   ├── password_reset.html
│   │   ├── password_reset_done.html
│   │   ├── password_reset_confirm.html
│   │   └── password_reset_complete.html
│   └── seo/
│       ├── _meta.html
│       ├── _json_ld.html
│       └── robots.txt
├── .env
├── .env.example
├── manage.py
└── requirements.txt
```

---

## 3. Installed Packages

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

> Bootstrap 5.3.3, Bootstrap Icons 1.11.3, and jQuery 3.7.1 are served locally
> from `static/vendor/` — NOT from CDN. django-csp blocks CDN requests.

---

## 4. Key Configuration Decisions

### 4.1 Settings
- `DJANGO_SETTINGS_MODULE=config.settings.development`
- Split: `base.py` / `development.py` / `production.py`
- All secrets via `django-environ` from `.env` at project root

### 4.2 Custom User Model
- `AUTH_USER_MODEL = 'accounts.CustomUser'`
- `AbstractBaseUser` + `PermissionsMixin`
- `USERNAME_FIELD = 'email'`

### 4.3 Task Queue
- Celery + Redis in both dev and prod (no django-q2)
- `CELERY_RESULT_BACKEND = 'django-db'`
- Beat: `django_celery_beat.schedulers:DatabaseScheduler`

### 4.4 CSP (django-csp 4.0)
- New format: `CONTENT_SECURITY_POLICY = {'DIRECTIVES': {...}}`
- Old flat `CSP_*` keys do NOT work with v4.0

### 4.5 Bootstrap
- Served from `static/vendor/` (local)
- Load order: `theme.css` → `bootstrap.min.css` → `bootstrap-icons.min.css` → `base.css`
- Bootstrap overrides in `base.css` using `!important` for specificity

### 4.6 Theme System
- Dark mode is default
- FART prevention: inline `<script>` in `<head>` reads localStorage before first paint
- `static/js/theme.js` — full toggle logic, localStorage persistence, server sync
- Authenticated users: `CustomUser.theme_preference` DB field
- Anonymous users: localStorage only
- Theme sync endpoint: `POST /accounts/theme-sync/`

### 4.7 Email
- SMTP (Gmail App Password) in both dev and prod
- `ADMIN_NOTIFICATION_EMAIL` setting for admin alerts
- All emails sent as Celery async tasks — never synchronously in views
- Django's built-in `PasswordResetView.form_valid()` is fully overridden —
  password reset email is sent via `send_password_reset_email` Celery task,
  NOT via Django's internal mechanism (which sends plain text)

### 4.8 Auth
- `LOGIN_URL = 'accounts:login'`
- `LOGIN_REDIRECT_URL = 'core:home'`
- `LOGOUT_REDIRECT_URL = 'core:home'`
- django-axes brute-force protection: 5 failures → 1-hour lockout
- Lockout handler: `apps.accounts.handlers.axes_lockout_handler`
- Login form errors: `__all__` (non-field errors from axes/wrong credentials)
  are extracted and returned as a flat `error` string — never as a nested object

---

## 5. Models

### `accounts.CustomUser` (AbstractBaseUser + PermissionsMixin)
```
email                       EmailField (USERNAME_FIELD, unique)
full_name                   CharField(255)
phone                       CharField(20, blank=True)
avatar                      ImageField(upload_to='avatars/', nullable)
is_organizer                BooleanField(default=False)
organizer_status            CharField choices: NONE|PENDING|APPROVED|REJECTED
theme_preference            CharField choices: dark|light (default: dark)
is_active                   BooleanField(default=True)
is_staff                    BooleanField(default=False)
date_joined                 DateTimeField(default=timezone.now)
email_verified              BooleanField(default=False)
email_verified_at           DateTimeField(nullable)
email_verification_token    UUIDField(default=uuid.uuid4, editable=False)
```

**Properties:** `is_pending_organizer`, `is_approved_organizer`, `is_rejected_organizer`  
**Methods:** `get_full_name()`, `get_short_name()`, `rotate_verification_token()`

### `accounts.OrganizerProfile` (OneToOne → CustomUser)
```
user                OneToOneField(CustomUser, related_name='organizer_profile')
organization_name   CharField(255)
bio                 TextField(blank=True)
website             URLField(blank=True)
approved_at         DateTimeField(nullable)
approved_by         ForeignKey(CustomUser, nullable, related_name='organizer_approvals')
```

### `accounts.OrganizerRequest` (FK → CustomUser)
```
user                ForeignKey(CustomUser, related_name='organizer_requests')
organization_name   CharField(255)
bio                 TextField(blank=True)
phone               CharField(20, blank=True)
website             URLField(blank=True)
pitch               TextField (min 50 chars enforced in form)
status              CharField choices: PENDING|APPROVED|REJECTED (default: PENDING)
rejection_reason    TextField(blank=True) — mandatory when rejecting
submitted_at        DateTimeField(default=timezone.now)
reviewed_at         DateTimeField(nullable)
reviewed_by         ForeignKey(CustomUser, nullable, related_name='reviewed_organizer_requests')
```

**Properties:** `is_pending`, `is_approved`, `is_rejected`  
**Key rule:** Never overwritten — each resubmission is a new row. Full audit trail preserved.

---

## 6. Services Layer (`apps/accounts/services.py`)

All business logic lives here. Views call these functions only.

| Function | Description |
|---|---|
| `register_user(email, full_name, password)` | Creates user. Does NOT send email. |
| `verify_email(token)` | Marks email verified, rotates token. Returns user or None. |
| `update_profile(user, full_name, phone, avatar)` | Updates profile fields. |
| `sync_theme(user, theme)` | Persists theme preference to DB. |
| `submit_organizer_request(user, ...)` | Creates OrganizerRequest, sets user status PENDING. |
| `approve_organizer_request(request, reviewed_by)` | Approves request, creates/updates OrganizerProfile. |
| `reject_organizer_request(request, reviewed_by, rejection_reason)` | Rejects request, raises ValueError if reason empty. |

---

## 7. Celery Tasks (`apps/accounts/tasks.py`)

| Task | Trigger |
|---|---|
| `send_verification_email(user_id)` | After signup |
| `send_password_reset_email(user_id, reset_url)` | After password reset form submit |
| `send_organizer_approved_notifications(user_id)` | After admin approval — email + SMS |
| `send_organizer_rejected_notifications(user_id, rejection_reason)` | After admin rejection — email + SMS |

All tasks: `bind=True`, `max_retries=3`, `default_retry_delay=60`.  
SMS via Africa's Talking — failure is silent (logged, never re-raised).  
`send_password_reset_email` builds its own `reset_url` — template uses
`{{ reset_url }}` directly, not Django's `{% url %}` token tags.

---

## 8. Permission Mixins (`apps/accounts/mixins.py`)

| Mixin | Behaviour |
|---|---|
| `AnonymousRedirectMixin` | Extends `LoginRequiredMixin`. Redirects to `accounts:login?next=`. |
| `VerifiedUserMixin` | Requires authenticated + email verified. Redirects to `accounts:verification_sent`. |
| `OrganizerRequiredMixin` | Requires approved organizer. Raises 403 for non-organizers. |

---

## 9. SEO Mixins (`apps/seo/mixins.py`)

| Mixin | Behaviour |
|---|---|
| `SEOMixin` | Injects seo_* context vars. Override `get_seo_title()` etc. for dynamic values. |
| `NoIndexMixin` | Extends SEOMixin. Sets `seo_robots = 'noindex, nofollow'`. Use on ALL auth/profile/dashboard pages. |

---

## 10. URL Namespaces & Named URLs

| Namespace | Prefix | Status |
|---|---|---|
| `core` | `/` | Active |
| `accounts` | `/accounts/` | Active (Phase 2) |
| `events` | `/events/` | Stub (Phase 3) |
| `tickets` | `/tickets/` | Stub (Phase 4) |
| `dashboard` | `/dashboard/` | Stub (Phase 6) |
| `checkin` | `/checkin/` | Stub (Phase 7) |

### `accounts` URLs (all active)
```
accounts:signup                  POST /accounts/signup/
accounts:login                   POST /accounts/login/
accounts:logout                  POST /accounts/logout/
accounts:verification_sent       GET  /accounts/verification-sent/
accounts:verify_email            GET  /accounts/verify-email/<uuid:token>/
accounts:profile                 GET/POST /accounts/profile/
accounts:theme_sync              POST /accounts/theme-sync/
accounts:become_organizer        GET/POST /accounts/become-organizer/
accounts:password_reset          GET/POST /accounts/password-reset/
accounts:password_reset_done     GET  /accounts/password-reset/done/
accounts:password_reset_confirm  GET/POST /accounts/password-reset/confirm/<uidb64>/<token>/
accounts:password_reset_complete GET  /accounts/password-reset/complete/
```

### `core` URLs (all active)
```
core:home, core:about, core:contact, core:help, core:terms, core:privacy, core:manifest
```

---

## 11. Template Architecture

### `templates/base.html` blocks
- `{% block seo %}` → includes `seo/_meta.html` (plain variables, NO `{% block %}` tags inside)
- `{% block structured_data %}` → includes `seo/_json_ld.html` (plain variables only)
- `{% block extra_css %}` — page CSS
- `{% block content %}` — page content
- `{% block extra_js %}` — page JS

> **Critical:** `{% include %}` partials cannot contain `{% block %}` tags.
> `_meta.html` and `_json_ld.html` use plain `{{ variable }}` only.
> `structured_data` context var is a list of `render_json_ld()` safe strings.

### Context vars available everywhere (context processors)
```
current_theme, SITE_NAME, SITE_DOMAIN, SITE_DESCRIPTION, user
```

### Skeleton loader
```django
{% include "components/_skeleton.html" with type="card" %}
{% include "components/_skeleton.html" with type="event-card" %}
{% include "components/_skeleton.html" with type="text" %}
{% include "components/_skeleton.html" with type="heading" %}
{% include "components/_skeleton.html" with type="avatar" %}
{% include "components/_skeleton.html" with type="table" %}
```

### Toast notifications
```javascript
window.showToast('Your message', 'success'); // success | danger | warning | info
// Server-side Django messages render automatically via _toasts.html
```

### Email base template
- `templates/accounts/emails/base_email.html` — branded dark HTML email shell
- All email templates extend this base
- Context vars in all emails: `user`, `site_name`, `site_domain`
- Password reset email uses `{{ reset_url }}` — NOT Django's `{% url %}` token tags

---

## 12. SEO App (`apps/seo/`)

| File | Exports |
|---|---|
| `mixins.py` | `SEOMixin`, `NoIndexMixin` |
| `structured_data.py` | `organization_schema()`, `website_schema()`, `breadcrumb_schema()`, `event_schema()`, `faq_schema()`, `render_json_ld()` |
| `sitemaps.py` | `StaticViewSitemap`, `EventSitemap`, `sitemaps` dict |
| `slugs.py` | `generate_unique_slug(model_class, title, instance, slug_field)` |
| `canonical.py` | `build_canonical(request, path, page)`, `clean_query_string(request)` |

### Using SEOMixin
```python
from apps.seo.mixins import SEOMixin

class EventDetailView(SEOMixin, DetailView):
    seo_og_type = 'event'

    def get_seo_title(self):
        return f"{self.object.title} — {settings.SITE_NAME}"

    def get_seo_description(self):
        return self.object.description[:160]
```

### Using structured data
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

## 13. Design System

### CSS load order (critical)
```html
theme.css → bootstrap.min.css → bootstrap-icons.min.css → base.css → page.css
```

### CSS files
| File | Purpose |
|---|---|
| `static/css/theme.css` | CSS custom properties (tokens) only. No component styles. |
| `static/css/base.css` | Resets, typography, utilities, Bootstrap overrides (`!important`), navbar avatar fix. |
| `static/css/accounts/*.css` | Page-specific styles. |

### Key CSS variables
```css
--tamasha-gold: #C9A84C
--color-bg-base          /* page background */
--color-bg-card          /* card background */
--color-text-primary     /* main text */
--color-text-secondary   /* secondary/body text — use this, not text-muted, for readable dark mode text */
--color-text-muted       /* truly de-emphasised hints only */
--color-text-gold        /* gold text */
--btn-primary-bg         /* gold button */
--input-border-focus     /* gold focus ring */
--shadow-gold            /* gold glow shadow */
```

> **Dark mode text rule:** Use `--color-text-secondary` for any text that must
> be readable. `--color-text-muted` is for genuinely de-emphasised hints only —
> it is too dark to use for body copy or labels in dark mode.

### JS files
| File | Purpose |
|---|---|
| `static/js/theme.js` | FART prevention + toggle + localStorage + server sync |
| `static/js/toasts.js` | Auto-init server toasts + `window.showToast()` |
| `static/js/accounts/auth.js` | Signup + login AJAX + password toggle |
| `static/js/accounts/profile.js` | Profile update AJAX (multipart) |
| `static/js/accounts/become_organizer.js` | Organizer application AJAX + pitch counter |

### Adding new page assets
```
static/css/<app_name>/<page>.css
static/js/<app_name>/<page>.js
```
```django
{% block extra_css %}<link rel="stylesheet" href="{% static 'css/app/page.css' %}">{% endblock %}
{% block extra_js %}<script src="{% static 'js/app/page.js' %}" defer></script>{% endblock %}
```

---

## 14. Working URLs

| URL | Status |
|---|---|
| `/` | ✅ Home |
| `/sitemap.xml` | ✅ XML sitemap |
| `/robots.txt` | ✅ robots.txt |
| `/manifest.json` | ✅ PWA manifest |
| `/admin/` | ✅ Django admin |
| `/accounts/signup/` | ✅ Signup (AJAX) |
| `/accounts/login/` | ✅ Login (AJAX) |
| `/accounts/logout/` | ✅ Logout (POST) |
| `/accounts/verification-sent/` | ✅ Verification sent page |
| `/accounts/verify-email/<token>/` | ✅ Email verification |
| `/accounts/profile/` | ✅ Profile (AJAX) |
| `/accounts/theme-sync/` | ✅ Theme sync (POST JSON) |
| `/accounts/become-organizer/` | ✅ Organizer application (AJAX) |
| `/accounts/password-reset/` | ✅ Password reset (branded HTML email via Celery) |
| `/events/` | 🔲 Stub (Phase 3) |
| `/dashboard/` | 🔲 Stub (Phase 6) |

---

## 15. Development Server Startup

Three terminals required:

```bash
# Terminal 1 — Redis (Docker)
docker start tamasha-redis
# First time setup:
# docker run -d --name tamasha-redis -p 6399:6379 redis:alpine

# Terminal 2 — Celery worker
celery -A config worker --loglevel=info --pool=solo
# --pool=solo is required on Windows (prefork fails with WinError 5)

# Terminal 3 — Django
py manage.py runserver
```

> **Redis port:** Windows blocks ports 6337–6836 via Hyper-V exclusions.
> Redis runs on port **6399** mapped to internal 6379.
> `.env` must have `REDIS_URL=redis://localhost:6399/0`

---

## 16. Changes vs. Original Implementation Plan

| Item | Plan | Actual | Reason |
|---|---|---|---|
| Task queue | Celery (prod) + django-q2 (dev) | Celery + Redis in both | Simpler, no dual-backend |
| Bootstrap delivery | CDN | Local `static/vendor/` | django-csp blocked CDN |
| Bootstrap overrides | In `theme.css` | Moved to `base.css` | Must load after Bootstrap for specificity |
| `--color-text-muted` dark | `#888888` | `#999999` | WCAG AA compliance |
| CSP format | Old flat `CSP_*` | New `CONTENT_SECURITY_POLICY` dict | django-csp 4.0 breaking change |
| `OrganizerProfileInline` | No `fk_name` | `fk_name = 'user'` | Two FKs to CustomUser → admin.E202 |
| Email verification token | Separate model | UUID field on `CustomUser` | Simpler, no extra dependency |
| Logout | Template view | POST-only, GET redirects home | GET logout is CSRF-unsafe |
| Password reset email | Django built-in mechanism | Full `form_valid()` override + Celery task | Built-in sends plain text, not HTML |
| SEO partials (`_meta.html`, `_json_ld.html`) | Had `{% block %}` tags | Plain `{{ variables }}` only | `{% block %}` tags invalid inside `{% include %}` partials |
| `BecomeOrganizerView` access | Blocked approved organizers only | Also blocks `is_staff` users | Admins should not submit organizer applications |

---

## 17. Environment Variables

```env
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_SETTINGS_MODULE=config.settings.development

DB_NAME=tamasha_db
DB_USER=tamasha_user
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432

REDIS_URL=redis://localhost:6399/0        ← port 6399, not 6379 (Windows port exclusion)

COMMISSION_RATE=0.03

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=                      ← Gmail App Password, not account password
DEFAULT_FROM_EMAIL=Tamasha Events <noreply@tamasha.co.tz>
SERVER_EMAIL=errors@tamasha.co.tz
ADMIN_NOTIFICATION_EMAIL=

AFRICASTALKING_USERNAME=sandbox
AFRICASTALKING_API_KEY=
AFRICASTALKING_SENDER_ID=

AZAMPAY_APP_NAME=
AZAMPAY_CLIENT_ID=
AZAMPAY_CLIENT_SECRET=
AZAMPAY_BASE_URL=https://sandbox.azampay.co.tz

SITE_DOMAIN=http://127.0.0.1:8000
```

---

## 18. Phase 3 Scope — Events

### Models needed (`apps/events/`)
- `Category` — name, slug, icon (Bootstrap Icon name), sort_order
- `Venue` — name, address, city, lat, lng, capacity
- `Tag` — name, slug
- `Event` — full model per implementation plan
- `EventCollaborator` — FK Event + FK OrganizerProfile, read-only access

### Views needed
- `EventListView` — browse, filter by category/date/city, search, pagination
- `EventDetailView` — full event page with JSON-LD `@type: Event`
- `EventCreateView` — organizer-only
- `EventUpdateView` — primary organizer only (EventOwnerMixin)
- `EventDeleteView` — soft delete (status = CANCELLED), primary organizer only
- `EventCollaboratorManageView` — primary organizer adds/removes collaborators

### Key rules for Phase 3
- All event URLs use slug only: `/events/<slug>/`
- `EventOwnerMixin` enforces primary organizer ownership — collaborators get hard 403 on write URLs
- Collaborators: read-only access to analytics, orders, attendees, check-in data
- Use `generate_unique_slug()` from `apps/seo/slugs.py` — never roll your own
- `SEOMixin` + JSON-LD `event_schema()` on `EventDetailView`
- `EventSitemap` in `apps/seo/sitemaps.py` lazy-loads Event model — needs `updated_at` field on Event and `events:detail` URL

### Templates needed
```
templates/events/
├── list.html
├── detail.html
├── create.html
├── edit.html
└── components/
    ├── _event_card.html
    └── _filters.html
```

### CSS/JS needed
```
static/css/events/list.css
static/css/events/detail.css
static/css/events/form.css
static/js/events/list.js
static/js/events/detail.js
static/js/events/form.js
```

---

## 19. Code Standards

- Business logic in `services.py` or model methods — never in views
- CBVs with mixins for permission layers
- All forms via Django Forms/ModelForms — never raw POST
- AJAX submissions with loading/submitting state management
- `NoIndexMixin` on all dashboard/profile/auth pages
- `SEOMixin` on all public-facing pages
- `select_related`/`prefetch_related` on all QuerySets
- Page CSS → `static/css/<app>/page.css`
- Page JS → `static/js/<app>/page.js`
- Never put HTML, CSS, JS in the same file
- CSRF on all state-changing endpoints
- No hardcoded secrets, URLs, or commission rates
- Dark mode text: always use `--color-text-secondary` for readable copy,
  never `--color-text-muted` for anything that needs to be clearly visible
