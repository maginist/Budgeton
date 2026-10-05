from django.urls import path

from . import views

app_name = 'main_app'

urlpatterns = [
    path('', views.HomePageView.as_view(), name='home'),
    path('solde/', views.BalanceOverviewView.as_view(), name='balance'),
    
    path('categories/', views.CategoriesHubView.as_view(), name='categories_hub'),
    path('categories/nouvelle/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/modifier/', views.CategoryUpdateView.as_view(), name='category_update'),
    
    path('previsions/', views.PlannedExpensesView.as_view(), name='planned_expenses'),
    path('previsions/nouvelle/', views.PlannedExpenseCreateView.as_view(), name='planned_expense_create'),
    path('previsions/<int:pk>/modifier/', views.PlannedExpenseUpdateView.as_view(), name='planned_expense_update'),
    path('previsions/<int:pk>/ce-mois/', views.PlannedExpenseMonthAdjustView.as_view(), name='planned_expense_month'),
    path('previsions/<int:pk>/revenir/', views.PlannedExpenseMonthResetView.as_view(), name='planned_expense_month_reset'),
    path('previsions/<int:pk>/supprimer/', views.PlannedExpenseDeleteView.as_view(), name='planned_expense_delete'),
    
    path('epargne/', views.SavingsHubView.as_view(), name='savings_hub'),
    path('compte/', views.AccountPageView.as_view(), name='account'),
    
    path('depenses/', views.ExpenseHubView.as_view(), name='expense_hub'),
    path('depense/nouvelle/', views.ExpenseCreateView.as_view(), name='expense_create'),
    path('depense/<int:pk>/modifier/', views.ExpenseUpdateView.as_view(), name='expense_update'),
    path('depense/<int:pk>/supprimer/', views.ExpenseDeleteView.as_view(), name='expense_delete'),

    path('revenu/nouveau/', views.IncomeCreateView.as_view(), name='income_create'),
    path('revenu/<int:pk>/modifier/', views.IncomeUpdateView.as_view(), name='income_update'),
    path('revenu/<int:pk>/supprimer/', views.IncomeDeleteView.as_view(), name='income_delete'),
    
    path('epargne/mouvement/nouveau/', views.SavingsCreateView.as_view(), name='savings_create'),
    path('epargne/compte/nouveau/', views.SavingsAccountCreateView.as_view(), name='savings_account_create'),
    path('epargne/compte/<int:pk>/modifier/', views.SavingsAccountUpdateView.as_view(), name='savings_account_update'),
]
