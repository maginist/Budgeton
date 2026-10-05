"""Génération des dépenses récurrentes (hebdo, mensuel, annuel) à date égale."""

from calendar import monthrange
from datetime import date, timedelta

from django.utils import timezone

from main_app.models import Expense

RECURRING_FREQUENCIES = (
    Expense.Frequency.WEEKLY,
    Expense.Frequency.MONTHLY,
    Expense.Frequency.YEARLY,
)
MAX_CATCH_UP_DAYS = 731
MAX_OCCURRENCES_PER_TEMPLATE = 200


def add_months(anchor, months):
    """Ajoute des mois en conservant le jour, ou le dernier jour du mois cible."""
    month_index = anchor.month - 1 + months
    year = anchor.year + month_index // 12
    month = month_index % 12 + 1
    day = min(anchor.day, monthrange(year, month)[1])
    return date(year, month, day)


def add_years(anchor, years):
    """Ajoute des années en conservant le mois et le jour (29 février → 28)."""
    year = anchor.year + years
    day = min(anchor.day, monthrange(year, anchor.month)[1])
    return date(year, anchor.month, day)


def shift_recurring_date(anchor, frequency, steps):
    """Retourne la n-ième occurrence à partir de la date d'origine."""
    if steps <= 0:
        return anchor
    if frequency == Expense.Frequency.WEEKLY:
        return anchor + timedelta(weeks=steps)
    if frequency == Expense.Frequency.MONTHLY:
        return add_months(anchor, steps)
    if frequency == Expense.Frequency.YEARLY:
        return add_years(anchor, years=steps)
    return None


def iter_due_dates(anchor, frequency, today, after, min_date):
    """Dates d'occurrence dues, strictement après `after` et jusqu'à `today`."""
    for steps in range(1, MAX_OCCURRENCES_PER_TEMPLATE + 1):
        current = shift_recurring_date(anchor, frequency, steps)
        if current is None or current > today:
            break
        if current <= after or current < min_date:
            continue
        yield current


def materialize_recurring_expenses(user, today=None):
    """Crée les copies manquantes des dépenses récurrentes de l'utilisateur, jusqu'à aujourd'hui."""
    if today is None:
        today = timezone.localdate()
    min_date = today - timedelta(days=MAX_CATCH_UP_DAYS)

    templates = (
        Expense.objects.filter(
            user=user,
            frequency__in=RECURRING_FREQUENCIES,
            recurring_from__isnull=True,
        )
        .select_related('category')
    )

    created = 0
    for template in templates:
        last_date = (
            Expense.objects.filter(recurring_from=template)
            .order_by('-date')
            .values_list('date', flat=True)
            .first()
        )
        after = last_date if last_date else template.date
        for due in iter_due_dates(template.date, template.frequency, today, after, min_date):
            _, was_created = Expense.objects.get_or_create(
                user=user,
                recurring_from=template,
                date=due,
                defaults={
                    'name': template.name,
                    'amount': template.amount,
                    'frequency': template.frequency,
                    'category': template.category,
                },
            )
            if was_created:
                created += 1
    return created
