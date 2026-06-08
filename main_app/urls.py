from django.urls import path

from . import views

app_name = 'main_app'

urlpatterns = [
    path('', views.HomePageView.as_view(), name='home'),
    path('categories/', views.CategoriesHubView.as_view(), name='categories_hub'),
    path('categories/nouvelle/', views.CategoryCreateView.as_view(), name='category_create'),
    path('solde/', views.BalanceOverviewView.as_view(), name='balance'),
    path('depenses/', views.ExpenseHubView.as_view(), name='expense_hub'),
    path('epargne/', views.SavingsHubView.as_view(), name='savings_hub'),
    path('compte/', views.AccountPageView.as_view(), name='account'),
    path('depense/nouvelle/', views.ExpenseCreateView.as_view(), name='expense_create'),
    path('revenu/nouveau/', views.IncomeCreateView.as_view(), name='income_create'),
    path('epargne/mouvement/nouveau/', views.SavingsCreateView.as_view(), name='savings_create'),
    path('epargne/compte/nouveau/', views.SavingsAccountCreateView.as_view(), name='savings_account_create'),
]
