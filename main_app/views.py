"""Vues du tableau de bord, des flux, de l'épargne, des catégories et des prévisions."""

from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Max, Min, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView

from main_app.forms import (
    CategoryForm,
    ExpenseForm,
    IncomeForm,
    PlannedExpenseForm,
    PlannedMonthAmountForm,
    SavingsAccountForm,
    SavingsForm,
)
from main_app.models import Category, Expense, Income, PlannedExpense, Savings, SavingsAccount


def current_month_bounds(today=None):
    """Retourne le premier jour du mois courant et le premier jour du mois suivant."""
    if today is None:
        today = timezone.now().date()
    start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1)
    else:
        end = start.replace(month=start.month + 1, day=1)
    return start, end


def month_bounds_from_year_month(year: int, month: int):
    """Retourne l'intervalle [début, fin[ du mois calendaire indiqué."""
    today = timezone.now().date()
    start = today.replace(year=year, month=month, day=1)
    if month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1)
    else:
        end = start.replace(month=start.month + 1, day=1)
    return start, end


def _safe_int(value, default: int) -> int:
    """Convertit `value` en entier, ou renvoie `default` si la conversion échoue."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def requested_year_month(request):
    """Lit `year` et `month` dans la query string, avec repli sur le mois actuel."""
    today = timezone.now().date()
    year = _safe_int(request.GET.get('year'), today.year)
    month = _safe_int(request.GET.get('month'), today.month)
    if month < 1 or month > 12:
        month = today.month
    # clamp simple pour éviter des valeurs absurdes
    year = max(1900, min(2100, year))
    return year, month


def year_choices_for_user(user, max_span: int = 25):
    """Liste les années couvertes par les mouvements de l'utilisateur (plage bornée)."""
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
    """Renvoie (année, mois) précédent et suivant pour la navigation mensuelle."""
    if month == 1:
        return year - 1, 12, year, 2
    if month == 12:
        return year, 11, year + 1, 1
    return year, month - 1, year, month + 1


def decimal_to_chart(value):
    """Convertit un Decimal (ou None) en float pour Chart.js."""
    if value is None:
        return 0.0
    return float(value)


def category_chart_rows(queryset):
    """Agrège un queryset Money par catégorie pour alimenter un graphique."""
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
    """Tableau de bord mensuel : totaux, camemberts et dernières transactions."""
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
        context['recent_incomes'] = (
            Income.objects.filter(user=user, date__gte=start, date__lt=end)
            .select_related('category')
            .order_by('-date', '-id')[:5]
        )

        context['home_chart_overview'] = {
            'salary': decimal_to_chart(total_income),
            'expense': decimal_to_chart(total_expense),
            'transfers': decimal_to_chart(total_savings),
        }
        context['home_chart_planned'] = [
            {
                'label': row['category'].name,
                'amount': decimal_to_chart(row['amount']),
                'color': row['category'].color or '#6c757d',
            }
            for row in effective_planned_expenses(user, selected_year, selected_month)
            if row['amount']
        ]
        return context


class BalanceOverviewView(LoginRequiredMixin, TemplateView):
    """Page solde du mois en cours, avec listes de revenus et de dépenses."""
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
    """Liste des dépenses du mois et historique récent (`expense_hub.html`)."""
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
    """Hub épargne : comptes/groupes et derniers mouvements."""
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
    """Profil utilisateur et déconnexion (`account.html`)."""
    template_name = 'main_app/account.html'


class ExpenseCreateView(LoginRequiredMixin, CreateView):
    """Formulaire d'ajout de dépense ; redirige vers l'accueil."""
    model = Expense
    template_name = 'main_app/expense_form.html'
    form_class = ExpenseForm
    success_url = reverse_lazy('main_app:home')

    def get_initial(self):
        initial = super().get_initial()
        initial['date'] = timezone.localdate()
        return initial

    def form_valid(self, form):
        form.instance.user = self.request.user
        if not form.instance.date:
            form.instance.date = timezone.localdate()
        return super().form_valid(form)


class IncomeCreateView(LoginRequiredMixin, CreateView):
    """Formulaire d'ajout de revenu ; redirige vers le solde."""
    model = Income
    template_name = 'main_app/income_form.html'
    form_class = IncomeForm
    success_url = reverse_lazy('main_app:balance')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class OwnedObjectMixin:
    """Restreint le queryset à l'utilisateur connecté et honore un paramètre `next` sûr."""
    def get_queryset(self):
        return self.model.objects.filter(user=self.request.user)

    def get_success_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url and next_url.startswith('/') and not next_url.startswith('//'):
            return next_url
        return str(self.success_url)


class ExpenseDeleteView(LoginRequiredMixin, OwnedObjectMixin, DeleteView):
    """Suppression d'une dépense appartenant à l'utilisateur."""
    model = Expense
    template_name = 'main_app/confirm_delete.html'
    success_url = reverse_lazy('main_app:home')
    extra_context = {'object_kind': 'cette dépense'}


class IncomeDeleteView(LoginRequiredMixin, OwnedObjectMixin, DeleteView):
    """Suppression d'une entrée d'argent appartenant à l'utilisateur."""
    model = Income
    template_name = 'main_app/confirm_delete.html'
    success_url = reverse_lazy('main_app:home')
    extra_context = {'object_kind': 'cette entrée'}


class ExpenseUpdateView(LoginRequiredMixin, OwnedObjectMixin, UpdateView):
    """Modification d'une dépense ; redirige vers l'accueil."""
    model = Expense
    form_class = ExpenseForm
    template_name = 'main_app/expense_form.html'
    success_url = reverse_lazy('main_app:home')


class IncomeUpdateView(LoginRequiredMixin, OwnedObjectMixin, UpdateView):
    """Modification d'un revenu ; redirige vers l'accueil."""
    model = Income
    form_class = IncomeForm
    template_name = 'main_app/income_form.html'
    success_url = reverse_lazy('main_app:home')


class SavingsAccountUpdateView(LoginRequiredMixin, OwnedObjectMixin, UpdateView):
    """Modification d'un compte ou groupe d'épargne."""
    model = SavingsAccount
    form_class = SavingsAccountForm
    template_name = 'main_app/savings_account_form.html'
    success_url = reverse_lazy('main_app:savings_hub')


class SavingsCreateView(LoginRequiredMixin, CreateView):
    """Ajout d'un mouvement d'épargne ; redirige vers le hub épargne."""
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
    """Création d'un compte ou groupe d'épargne."""
    model = SavingsAccount
    form_class = SavingsAccountForm
    template_name = 'main_app/savings_account_form.html'
    success_url = reverse_lazy('main_app:savings_hub')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class CategoryCreateView(LoginRequiredMixin, CreateView):
    """Création d'une catégorie ; redirige vers le hub catégories."""
    model = Category
    form_class = CategoryForm
    template_name = 'main_app/category_form.html'
    success_url = reverse_lazy('main_app:categories_hub')


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    """Modification d'une catégorie ; redirige vers le hub catégories."""
    model = Category
    form_class = CategoryForm
    template_name = 'main_app/category_form.html'
    success_url = reverse_lazy('main_app:categories_hub')


class CategoriesHubView(LoginRequiredMixin, TemplateView):
    """Récap mensuel par catégorie (totaux, extraits, graphiques)."""
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
                'all_categories': Category.objects.order_by('name'),
                'expense_chart_data': category_chart_rows(expenses_qs),
                'income_chart_data': category_chart_rows(income_qs),
                'savings_chart_data': category_chart_rows(savings_qs),
            }
        )
        return context


def planned_expenses_url(year, month):
    """URL du hub prévisions pour l'année et le mois indiqués."""
    return f"{reverse('main_app:planned_expenses')}?year={year}&month={month}"


def month_index(year, month):
    """Clé comparable pour ordonner les mois calendaires."""
    return year * 12 + month


def next_calendar_month(year, month):
    """Renvoie le mois calendaire qui suit."""
    if month == 12:
        return year + 1, 1
    return year, month + 1


def effective_planned_expenses(user, year, month):
    """Montant du mois : report en cours, sauf ajustement limité à ce mois."""
    templates = {
        plan.category_id: plan
        for plan in PlannedExpense.objects.filter(
            user=user,
            year__isnull=True,
            month__isnull=True,
        ).select_related('category')
    }
    dated_by_category = {}
    for plan in PlannedExpense.objects.filter(
        user=user,
        year__isnull=False,
    ).select_related('category'):
        dated_by_category.setdefault(plan.category_id, []).append(plan)

    target = month_index(year, month)
    rows = []
    for category_id in set(templates) | set(dated_by_category):
        template = templates.get(category_id)
        entries = dated_by_category.get(category_id, [])
        exact = next(
            (
                entry for entry in entries
                if entry.year == year and entry.month == month and not entry.apply_forward
            ),
            None,
        )
        forwards = [
            entry for entry in entries
            if entry.apply_forward and month_index(entry.year, entry.month) <= target
        ]
        forward = max(forwards, key=lambda entry: month_index(entry.year, entry.month), default=None)
        if exact:
            source = exact
            amount = exact.amount
            customized = True
        else:
            source = forward or template
            if source is None:
                continue
            amount = source.amount
            customized = False
        usual_amount = None
        if customized:
            usual_amount = forward.amount if forward else (template.amount if template else None)
        rows.append({
            'category': source.category,
            'amount': amount,
            'template': template,
            'override': exact,
            'customized': customized,
            'usual_amount': usual_amount,
        })
    rows.sort(key=lambda row: row['category'].name.lower())
    return rows


class PlannedExpensesView(LoginRequiredMixin, TemplateView):
    """Compare enveloppes prévisionnelles et dépenses réelles du mois."""
    template_name = 'main_app/planned_expenses.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        selected_year, selected_month = requested_year_month(self.request)
        start, end = month_bounds_from_year_month(selected_year, selected_month)
        prev_year, prev_month, next_year, next_month = month_switch(selected_year, selected_month)

        spent_by_category = {
            row['category_id']: row['total'] or Decimal('0')
            for row in (
                Expense.objects.filter(user=user, date__gte=start, date__lt=end)
                .values('category_id')
                .annotate(total=Sum('amount'))
            )
        }

        plans = effective_planned_expenses(user, selected_year, selected_month)

        rows = []
        total_planned = Decimal('0')
        total_spent_planned = Decimal('0')
        for plan in plans:
            spent = spent_by_category.get(plan['category'].pk) or Decimal('0')
            amount = plan['amount']
            remaining = amount - spent
            percent = float((spent / amount) * 100) if amount else 0.0
            bar_width = int(min(max(percent, 0.0), 100.0))
            rows.append({
                **plan,
                'spent': spent,
                'remaining': remaining,
                'over_amount': spent - amount if spent > amount else Decimal('0'),
                'percent': percent,
                'bar_width': bar_width,
                'over': spent > amount,
            })
            total_planned += amount
            total_spent_planned += spent

        overall_percent = float((total_spent_planned / total_planned) * 100) if total_planned else 0.0

        context.update({
            'title': 'Prévisions',
            'dashboard_month': start,
            'selected_year': selected_year,
            'selected_month': selected_month,
            'prev_year': prev_year,
            'prev_month': prev_month,
            'next_year': next_year,
            'next_month': next_month,
            'year_choices': year_choices_for_user(user),
            'rows': rows,
            'total_planned': total_planned,
            'total_spent': total_spent_planned,
            'overall_percent': overall_percent,
            'overall_bar_width': int(min(max(overall_percent, 0.0), 100.0)),
            'overall_over': total_spent_planned > total_planned if total_planned else False,
        })
        return context


class PlannedExpenseCreateView(LoginRequiredMixin, CreateView):
    """Ajoute une prévision au jeu habituel, reprise chaque mois."""
    model = PlannedExpense
    form_class = PlannedExpenseForm
    template_name = 'main_app/planned_expense_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.year = None
        form.instance.month = None
        return super().form_valid(form)

    def get_success_url(self):
        year, month = requested_year_month(self.request)
        return planned_expenses_url(year, month)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year, month = requested_year_month(self.request)
        context['selected_year'] = year
        context['selected_month'] = month
        context['is_template'] = True
        return context


class PlannedExpenseUpdateView(LoginRequiredMixin, OwnedObjectMixin, UpdateView):
    """Modifie le montant habituel, ou un ajustement déjà enregistré pour un mois."""
    model = PlannedExpense
    form_class = PlannedExpenseForm
    template_name = 'main_app/planned_expense_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['lock_category'] = not self.get_object().is_template
        return kwargs

    def get_success_url(self):
        if self.object.year and self.object.month:
            return planned_expenses_url(self.object.year, self.object.month)
        year, month = requested_year_month(self.request)
        return planned_expenses_url(year, month)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_template'] = self.object.is_template
        context['selected_year'] = self.object.year
        context['selected_month'] = self.object.month
        return context


class PlannedExpenseMonthAdjustView(LoginRequiredMixin, FormView):
    """Modifie la prévision du mois, et les suivantes si la case est cochée."""
    form_class = PlannedMonthAmountForm
    template_name = 'main_app/planned_expense_month_form.html'

    def get_template_plan(self):
        return get_object_or_404(
            PlannedExpense,
            pk=self.kwargs['pk'],
            user=self.request.user,
            year__isnull=True,
            month__isnull=True,
        )

    def get_month_row(self):
        plan = self.get_template_plan()
        year, month = requested_year_month(self.request)
        return PlannedExpense.objects.filter(
            user=self.request.user,
            category=plan.category,
            year=year,
            month=month,
        ).first()

    def get_initial(self):
        plan = self.get_template_plan()
        year, month = requested_year_month(self.request)
        current = next(
            (
                row for row in effective_planned_expenses(self.request.user, year, month)
                if row['category'].pk == plan.category_id
            ),
            None,
        )
        month_row = self.get_month_row()
        return {
            'amount': current['amount'] if current else plan.amount,
            'apply_forward': bool(month_row and month_row.apply_forward),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year, month = requested_year_month(self.request)
        plan = self.get_template_plan()
        context.update({
            'plan': plan,
            'selected_year': year,
            'selected_month': month,
        })
        return context

    def form_valid(self, form):
        plan = self.get_template_plan()
        year, month = requested_year_month(self.request)
        amount = form.cleaned_data['amount']
        if form.cleaned_data['apply_forward']:
            self._apply_forward(plan, year, month, amount)
        else:
            self._apply_this_month(plan, year, month, amount)
        return redirect(planned_expenses_url(year, month))

    def _amount_before(self, plan, year, month):
        """Montant déjà en vigueur juste avant le mois choisi."""
        target = month_index(year, month)
        earlier = [
            entry for entry in PlannedExpense.objects.filter(
                user=plan.user,
                category=plan.category,
                apply_forward=True,
                year__isnull=False,
            )
            if month_index(entry.year, entry.month) < target
        ]
        if not earlier:
            return plan.amount
        return max(earlier, key=lambda entry: month_index(entry.year, entry.month)).amount

    def _apply_this_month(self, plan, year, month, amount):
        """Ne change que le mois affiché. Les mois suivants gardent leur montant."""
        month_row = PlannedExpense.objects.filter(
            user=plan.user,
            category=plan.category,
            year=year,
            month=month,
        ).first()
        if month_row and month_row.apply_forward:
            later_year, later_month = next_calendar_month(year, month)
            already = PlannedExpense.objects.filter(
                user=plan.user,
                category=plan.category,
                year=later_year,
                month=later_month,
            ).exists()
            if already:
                month_row.delete()
            else:
                month_row.year = later_year
                month_row.month = later_month
                month_row.save(update_fields=['year', 'month'])
        previous = self._amount_before(plan, year, month)
        if amount == previous:
            PlannedExpense.objects.filter(
                user=plan.user,
                category=plan.category,
                year=year,
                month=month,
                apply_forward=False,
            ).delete()
            return
        PlannedExpense.objects.update_or_create(
            user=plan.user,
            category=plan.category,
            year=year,
            month=month,
            defaults={'amount': amount, 'apply_forward': False},
        )

    def _apply_forward(self, plan, year, month, amount):
        """Reprend ce montant pour le mois choisi et tous les mois suivants."""
        target = month_index(year, month)
        for entry in PlannedExpense.objects.filter(
            user=plan.user,
            category=plan.category,
            year__isnull=False,
        ):
            if month_index(entry.year, entry.month) >= target:
                entry.delete()
        if amount != self._amount_before(plan, year, month):
            PlannedExpense.objects.create(
                user=plan.user,
                category=plan.category,
                year=year,
                month=month,
                amount=amount,
                apply_forward=True,
            )


class PlannedExpenseMonthResetView(LoginRequiredMixin, DeleteView):
    """Oublie l'ajustement du mois et retrouve le montant habituel."""
    model = PlannedExpense
    template_name = 'main_app/confirm_delete.html'
    extra_context = {'object_kind': 'l’ajustement de ce mois'}

    def get_queryset(self):
        return PlannedExpense.objects.filter(user=self.request.user, year__isnull=False)

    def get_success_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url and next_url.startswith('/') and not next_url.startswith('//'):
            return next_url
        return planned_expenses_url(self.object.year, self.object.month)


class PlannedExpenseDeleteView(LoginRequiredMixin, OwnedObjectMixin, DeleteView):
    """Retire une prévision du jeu habituel, y compris ses ajustements mensuels."""
    model = PlannedExpense
    template_name = 'main_app/confirm_delete.html'
    extra_context = {'object_kind': 'cette prévision'}

    def form_valid(self, form):
        if self.object.is_template:
            PlannedExpense.objects.filter(
                user=self.object.user,
                category_id=self.object.category_id,
                year__isnull=False,
            ).delete()
        return super().form_valid(form)

    def get_success_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url and next_url.startswith('/') and not next_url.startswith('//'):
            return next_url
        if self.object.year and self.object.month:
            return planned_expenses_url(self.object.year, self.object.month)
        year, month = requested_year_month(self.request)
        return planned_expenses_url(year, month)
