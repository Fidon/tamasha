from django.urls import path

from apps.core import views

app_name = 'core'

urlpatterns = [
    path('',          views.HomeView.as_view(),     name='home'),
    path('about/',    views.AboutView.as_view(),    name='about'),
    path('contact/',  views.ContactView.as_view(),  name='contact'),
    path('help/',     views.HelpView.as_view(),     name='help'),
    path('terms/',    views.TermsView.as_view(),    name='terms'),
    path('privacy/',  views.PrivacyView.as_view(),  name='privacy'),
    path('manifest.json', views.ManifestView.as_view(), name='manifest'),
]