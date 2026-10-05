from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from main_app.models import Category, Expense, PlannedExpense
from main_app.recurrence import add_months, materialize_recurring_expenses, shift_recurring_date


class RecurringDateTests(TestCase):
    def test_monthly_keeps_day_or_clamps_end_of_month(self):
        self.assertEqual(add_months(date(2026, 1, 15), 1), date(2026, 2, 15))
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(add_months(date(2026, 1, 31), 2), date(2026, 3, 31))

    def test_yearly_february_29(self):
        self.assertEqual(
            shift_recurring_date(date(2024, 2, 29), Expense.Frequency.YEARLY, 1),
            date(2025, 2, 28),
        )


class RecurringExpenseMaterializeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('mathieu_test', password='pass')
        self.category = Category.objects.create(name='Abonnements', color='#c45c3e')

    def _template(self, when, frequency):
        return Expense.objects.create(
            user=self.user,
            category=self.category,
            name='Netflix',
            amount=Decimal('13.00'),
            date=when,
            frequency=frequency,
        )

    def test_weekly_copies_same_weekday_until_today(self):
        self._template(date(2026, 9, 1), Expense.Frequency.WEEKLY)
        created = materialize_recurring_expenses(self.user, today=date(2026, 9, 16))
        dates = list(
            Expense.objects.filter(user=self.user).order_by('date').values_list('date', flat=True)
        )
        self.assertEqual(created, 2)
        self.assertEqual(dates, [date(2026, 9, 1), date(2026, 9, 8), date(2026, 9, 15)])

    def test_monthly_same_day(self):
        self._template(date(2026, 6, 10), Expense.Frequency.MONTHLY)
        materialize_recurring_expenses(self.user, today=date(2026, 9, 10))
        dates = list(
            Expense.objects.filter(user=self.user).order_by('date').values_list('date', flat=True)
        )
        self.assertEqual(
            dates,
            [date(2026, 6, 10), date(2026, 7, 10), date(2026, 8, 10), date(2026, 9, 10)],
        )

    def test_yearly_same_month_day(self):
        self._template(date(2024, 9, 30), Expense.Frequency.YEARLY)
        materialize_recurring_expenses(self.user, today=date(2026, 9, 30))
        dates = list(
            Expense.objects.filter(user=self.user).order_by('date').values_list('date', flat=True)
        )
        self.assertEqual(dates, [date(2024, 9, 30), date(2025, 9, 30), date(2026, 9, 30)])

    def test_one_shot_is_ignored(self):
        self._template(date(2026, 1, 1), Expense.Frequency.ONCE)
        created = materialize_recurring_expenses(self.user, today=date(2026, 9, 30))
        self.assertEqual(created, 0)
        self.assertEqual(Expense.objects.filter(user=self.user).count(), 1)

    def test_does_not_create_future_dates(self):
        self._template(date(2026, 9, 30), Expense.Frequency.MONTHLY)
        created = materialize_recurring_expenses(self.user, today=date(2026, 9, 15))
        self.assertEqual(created, 0)
        self.assertEqual(Expense.objects.filter(user=self.user).count(), 1)

    def test_idempotent(self):
        self._template(date(2026, 9, 1), Expense.Frequency.WEEKLY)
        first = materialize_recurring_expenses(self.user, today=date(2026, 9, 16))
        second = materialize_recurring_expenses(self.user, today=date(2026, 9, 16))
        self.assertEqual(first, 2)
        self.assertEqual(second, 0)
        self.assertEqual(Expense.objects.filter(user=self.user).count(), 3)


class PlannedSetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('prev_user', password='pass')
        self.category = Category.objects.create(name='Courses', color='#c45c3e')
        self.template = PlannedExpense.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal('200.00'),
        )

    def test_template_applies_to_every_month(self):
        from main_app.views import effective_planned_expenses

        october = effective_planned_expenses(self.user, 2026, 10)
        november = effective_planned_expenses(self.user, 2026, 11)
        self.assertEqual(october[0]['amount'], Decimal('200.00'))
        self.assertFalse(october[0]['customized'])
        self.assertEqual(november[0]['amount'], Decimal('200.00'))

    def test_month_override_does_not_change_other_months(self):
        from main_app.views import effective_planned_expenses

        PlannedExpense.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal('80.00'),
            year=2026,
            month=10,
        )
        october = effective_planned_expenses(self.user, 2026, 10)[0]
        november = effective_planned_expenses(self.user, 2026, 11)[0]
        self.assertEqual(october['amount'], Decimal('80.00'))
        self.assertTrue(october['customized'])
        self.assertEqual(november['amount'], Decimal('200.00'))
        self.assertFalse(november['customized'])

    def test_adjust_view_keeps_template(self):
        self.client.force_login(self.user)
        response = self.client.post(
            f'/previsions/{self.template.pk}/ce-mois/?year=2026&month=10',
            {'amount': '50.00'},
        )
        self.assertEqual(response.status_code, 302)
        self.template.refresh_from_db()
        self.assertEqual(self.template.amount, Decimal('200.00'))
        self.assertTrue(
            PlannedExpense.objects.filter(
                user=self.user,
                category=self.category,
                year=2026,
                month=10,
                amount=Decimal('50.00'),
                apply_forward=False,
            ).exists()
        )

    def test_checkbox_updates_following_months_only(self):
        from main_app.views import effective_planned_expenses

        self.client.force_login(self.user)
        response = self.client.post(
            f'/previsions/{self.template.pk}/ce-mois/?year=2026&month=10',
            {'amount': '50.00', 'apply_forward': 'on'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(effective_planned_expenses(self.user, 2026, 9)[0]['amount'], Decimal('200.00'))
        self.assertEqual(effective_planned_expenses(self.user, 2026, 10)[0]['amount'], Decimal('50.00'))
        self.assertEqual(effective_planned_expenses(self.user, 2026, 11)[0]['amount'], Decimal('50.00'))
