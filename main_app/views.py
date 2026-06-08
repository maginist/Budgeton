from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Max, Min, Sum
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, TemplateView

from main_app.forms import (
    CategoryForm,
    ExpenseForm,
    IncomeForm,
    SavingsAccountForm,
    SavingsForm,
)
from main_app.models import Category, Expense, Income, Savings, SavingsAccount


def current_month_bounds(today=None):
    if today is None:
        today = timezone.now().date()
    start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1)
    else:
        end = start.replace(month=start.month + 1, day=1)
    return start, end


def month_bounds_from_year_month(year: int, month: int):
    today = timezone.now().date()
    start = today.replace(year=year, month=month, day=1)
    if month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1)
    else:
        end = start.replace(month=start.month + 1, day=1)
    return start, end


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def requested_year_month(request):
    today = timezone.now().date()
    year = _safe_int(request.GET.get('year'), today.year)
    month = _safe_int(request.GET.get('month'), today.month)
    if month < 1 or month > 12:
        month = today.month
    # clamp simple pour éviter des valeurs absurdes
    year = max(1900, min(2100, year))
    return year, month


def year_choices_for_user(user, max_span: int = 25):
    today = timezone.now().date()
    min_dates = []
    max_dates = []
    for model in (Expense, Income, Savings):
        agg_min = model.objects.filter(user=user).aggregate(d=Min('date'))['d']
        agg_max = model.objects.filter(user=user).aggregate(d=Max('date'))['d']
        if agg_min:
            min_dates.append(agg_min)
        if agg_max:
            max_dates.append(agg_max)

    min_year = min([d.year for d in min_dates], default=today.year)
    max_year = max([d.year for d in max_dates], default=today.year)

    if max_year - min_year > max_span:
        min_year = max_year - max_span
    return list(range(min_year, max_year + 1))


def month_switch(year: int, month: int):
    if month == 1:
        return year - 1, 12, year, 2
    if month == 12:
        return year, 11, year + 1, 1
    return year, month - 1, year, month + 1


def decimal_to_chart(value):
    if value is None:
        return 0.0
    return float(value)


def category_chart_rows(queryset):
    rows = (
        queryset.values('category__name', 'category__color')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    return [
        {
            'label': r['category__name'] or 'Sans nom',
            'amount': decimal_to_chart(r['total']),
            'color': r['category__color'] or '#6c757d',
        }
        for r in rows
    ]


class HomePageView(LoginRequiredMixin, TemplateView):
    template_name = 'main_app/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        selected_year, selected_month = requested_year_month(self.request)
        start, end = month_bounds_from_year_month(selected_year, selected_month)
        prev_year, prev_month, next_year, next_month = month_switch(selected_year, selected_month)
        year_choices = year_choices_for_user(user)

        expenses_qs = Expense.objects.filter(user=user, date__gte=start, date__lt=end)
        income_qs = Income.objects.filter(user=user, date__gte=start, date__lt=end)
        savings_qs = Savings.objects.filter(user=user, date__gte=start, date__lt=end)

        total_expense = expenses_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        total_income = income_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        total_savings = savings_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        estimated_remaining = total_income - total_expense - total_savings

        context['title'] = 'Tableau de bord'
        context['dashboard_month'] = start
        context['selected_year'] = selected_year
        context['selected_month'] = selected_month
        context['prev_year'] = prev_year
        context['prev_month'] = prev_month
        context['next_year'] = next_year
        context['next_month'] = next_month
        context['year_choices'] = year_choices
        context['total_expense'] = total_expense
        context['total_income'] = total_income
        context['total_savings'] = total_savings
        context['estimated_remaining'] = estimated_remaining
        context['recent_expenses'] = (
            Expense.objects.filter(user=user, date__gte=start, date__lt=end)
            .select_related('category')
            .order_by('-date', '-id')[:5]
        )

        # Graphique unique "entrées + dépenses" par catégorie (mois sélectionné)
        expenses_totals = (
            expenses_qs.values('category_id', 'category__name', 'category__color')
            .annotate(total=Sum('amount'))
        )
        incomes_totals = (
            income_qs.values('category_id', 'category__name', 'category__color')
            .annotate(total=Sum('amount'))
        )

        categories_map = {}
        for r in expenses_totals:
            cid = r['category_id']
            categories_map[cid] = {
                'label': r['category__name'] or 'Sans nom',
                'color': r['category__color'] or '#6c757d',
                'income': 0.0,
                'expense': decimal_to_chart(r['total']),
            }

        for r in incomes_totals:
            cid = r['category_id']
            if cid not in categories_map:
                categories_map[cid] = {
                    'label': r['category__name'] or 'Sans nom',
                    'color': r['category__color'] or '#6c757d',
                    'income': 0.0,
                    'expense': 0.0,
                }
            categories_map[cid]['income'] = decimal_to_chart(r['total'])

        home_chart_categories = list(categories_map.values())
        home_chart_categories.sort(
            key=lambda d: (d.get('income', 0.0) + d.get('expense', 0.0)),
            reverse=True,
        )

        context['home_chart_categories'] = home_chart_categories
        return context


class BalanceOverviewView(LoginRequiredMixin, TemplateView):
    template_name = 'main_app/balance.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        start, end = current_month_bounds()

        expenses_qs = Expense.objects.filter(user=user, date__gte=start, date__lt=end)
        income_qs = Income.objects.filter(user=user, date__gte=start, date__lt=end)
        savings_qs = Savings.objects.filter(user=user, date__gte=start, date__lt=end)

        total_expense = expenses_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        total_income = income_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        total_savings = savings_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')

        context['estimated_remaining'] = total_income - total_expense - total_savings
        context['total_income'] = total_income
        context['total_expense'] = total_expense
        context['total_savings'] = total_savings
        context['month_start'] = start
        context['recent_incomes'] = (
            Income.objects.filter(user=user).select_related('category').order_by('-date', '-id')[:15]
        )
        context['recent_expenses'] = (
            Expense.objects.filter(user=user).select_related('category').order_by('-date', '-id')[:15]
        )
        return context


class ExpenseHubView(LoginRequiredMixin, ListView):
    template_name = 'main_app/expense_hub.html'
    context_object_name = 'expenses'

    def get_queryset(self):
        start, end = current_month_bounds()
        return (
            Expense.objects.filter(user=self.request.user, date__gte=start, date__lt=end)
            .select_related('category')
            .order_by('-date', '-id')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start, end = current_month_bounds()
        qs = Expense.objects.filter(user=self.request.user, date__gte=start, date__lt=end)
        context['month_total'] = qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        context['recent_all'] = (
            Expense.objects.filter(user=self.request.user)
            .select_related('category')
            .order_by('-date', '-id')[:20]
        )
        return context


class SavingsHubView(LoginRequiredMixin, TemplateView):
    template_name = 'main_app/savings_hub.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        start, end = current_month_bounds()
        savings_qs = Savings.objects.filter(user=user, date__gte=start, date__lt=end)
        context['month_total'] = savings_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        context['accounts'] = SavingsAccount.objects.filter(user=user)
        context['recent_savings'] = (
            Savings.objects.filter(user=user)
            .select_related('category', 'account')
            .order_by('-date', '-id')[:20]
        )
        return context


class AccountPageView(LoginRequiredMixin, TemplateView):
    template_name = 'main_app/account.html'


class ExpenseCreateView(LoginRequiredMixin, CreateView):
    model = Expense
    template_name = 'main_app/expense_form.html'
    form_class = ExpenseForm
    success_url = reverse_lazy('main_app:home')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class IncomeCreateView(LoginRequiredMixin, CreateView):
    model = Income
    template_name = 'main_app/income_form.html'
    form_class = IncomeForm
    success_url = reverse_lazy('main_app:balance')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class SavingsCreateView(LoginRequiredMixin, CreateView):
    model = Savings
    template_name = 'main_app/savings_form.html'
    form_class = SavingsForm
    success_url = reverse_lazy('main_app:savings_hub')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        account = form.cleaned_data.get('account')
        if account and account.user_id != self.request.user.id:
            form.add_error('account', 'Compte invalide.')
            return self.form_invalid(form)
        return super().form_valid(form)


class SavingsAccountCreateView(LoginRequiredMixin, CreateView):
    model = SavingsAccount
    form_class = SavingsAccountForm
    template_name = 'main_app/savings_account_form.html'
    success_url = reverse_lazy('main_app:savings_hub')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'main_app/category_form.html'
    success_url = reverse_lazy('main_app:categories_hub')


class CategoriesHubView(LoginRequiredMixin, TemplateView):
    template_name = 'main_app/categories_hub.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        selected_year, selected_month = requested_year_month(self.request)
        start, end = month_bounds_from_year_month(selected_year, selected_month)
        prev_year, prev_month, next_year, next_month = month_switch(selected_year, selected_month)
        year_choices = year_choices_for_user(user)

        expenses_qs = Expense.objects.filter(user=user, date__gte=start, date__lt=end)
        income_qs = Income.objects.filter(user=user, date__gte=start, date__lt=end)
        savings_qs = Savings.objects.filter(user=user, date__gte=start, date__lt=end)

        expenses_totals = (
            expenses_qs.values('category_id', 'category__name', 'category__color')
            .annotate(total=Sum('amount'))
        )
        incomes_totals = (
            income_qs.values('category_id', 'category__name', 'category__color')
            .annotate(total=Sum('amount'))
        )
        savings_totals = (
            savings_qs.values('category_id', 'category__name', 'category__color')
            .annotate(total=Sum('amount'))
        )

        rows = {}
        for r in expenses_totals:
            rows[r['category_id']] = {
                'category_id': r['category_id'],
                'name': r['category__name'] or 'Sans nom',
                'color': r['category__color'] or '#6c757d',
                'expenses_total': r['total'] or Decimal('0'),
                'incomes_total': Decimal('0'),
                'savings_total': Decimal('0'),
                'expense_samples': [],
                'income_samples': [],
                'savings_samples': [],
            }

        for r in incomes_totals:
            cid = r['category_id']
            if cid not in rows:
                rows[cid] = {
                    'category_id': cid,
                    'name': r['category__name'] or 'Sans nom',
                    'color': r['category__color'] or '#6c757d',
                    'expenses_total': Decimal('0'),
                    'incomes_total': r['total'] or Decimal('0'),
                    'savings_total': Decimal('0'),
                    'expense_samples': [],
                    'income_samples': [],
                    'savings_samples': [],
                }
            else:
                rows[cid]['incomes_total'] = r['total'] or Decimal('0')

        for r in savings_totals:
            cid = r['category_id']
            if cid not in rows:
                rows[cid] = {
                    'category_id': cid,
                    'name': r['category__name'] or 'Sans nom',
                    'color': r['category__color'] or '#6c757d',
                    'expenses_total': Decimal('0'),
                    'incomes_total': Decimal('0'),
                    'savings_total': r['total'] or Decimal('0'),
                    'expense_samples': [],
                    'income_samples': [],
                    'savings_samples': [],
                }
            else:
                rows[cid]['savings_total'] = r['total'] or Decimal('0')

        for e in expenses_qs.select_related('category').order_by('-date', '-id'):
            row = rows.get(e.category_id)
            if not row:
                continue
            if len(row['expense_samples']) < 3:
                row['expense_samples'].append({
                    'date': e.date,
                    'name': e.name,
                    'amount': e.amount,
                })

        for i in income_qs.select_related('category').order_by('-date', '-id'):
            row = rows.get(i.category_id)
            if not row:
                continue
            if len(row['income_samples']) < 3:
                row['income_samples'].append({
                    'date': i.date,
                    'name': i.name,
                    'amount': i.amount,
                })

        for s in savings_qs.select_related('category').order_by('-date', '-id'):
            row = rows.get(s.category_id)
            if not row:
                continue
            if len(row['savings_samples']) < 3:
                row['savings_samples'].append({
                    'date': s.date,
                    'name': s.name,
                    'amount': s.amount,
                })

        categories_rows = sorted(
            rows.values(),
            key=lambda r: (r.get('expenses_total') or Decimal('0')),
            reverse=True,
        )

        context.update(
            {
                'title': 'Catégories',
                'dashboard_month': start,
                'selected_year': selected_year,
                'selected_month': selected_month,
                'prev_year': prev_year,
                'prev_month': prev_month,
                'next_year': next_year,
                'next_month': next_month,
                'year_choices': year_choices,
                'categories_rows': categories_rows,
                'expense_chart_data': category_chart_rows(expenses_qs),
                'income_chart_data': category_chart_rows(income_qs),
            }
        )
        return context
