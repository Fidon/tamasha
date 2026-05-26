from django.urls import path

from . import views

app_name = 'events'

urlpatterns = [
    # ── Public — fixed paths MUST come before <slug:slug>/ ──────────────────
    path('', views.EventListView.as_view(), name='list'),

    # ── Organizer: Wizard — declared before <slug:slug>/ to avoid collision ─
    path('create/',                  views.EventWizardView.as_view(),        name='create'),
    path('edit/<slug:slug>/',        views.EventWizardView.as_view(),        name='edit'),
    path('wizard/step/<int:step>/',  views.EventWizardStepView.as_view(),    name='wizard_step'),
    path('wizard/discard/',          views.EventDiscardDraftView.as_view(),  name='discard_draft'),

    # ── AJAX: Venue & Collaborators — before <slug:slug>/ ───────────────────
    path('venues/search/',           views.VenueSearchView.as_view(),        name='venue_search'),
    path('venues/save/',             views.VenueSaveView.as_view(),          name='venue_save'),
    path('collaborators/search/',    views.CollaboratorSearchView.as_view(), name='collaborator_search'),

    # ── Public: Event Detail — slug pattern LAST ────────────────────────────
    path('<slug:slug>/',             views.EventDetailView.as_view(),        name='detail'),
    path('<slug:slug>/cancel/',      views.EventCancelView.as_view(),        name='cancel'),
    path('<slug:slug>/republish/',   views.EventRepublishView.as_view(),     name='republish'),
    path('<slug:slug>/retract/',     views.EventRetractView.as_view(),       name='retract'),
]