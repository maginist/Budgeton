"""Modèles du budget personnel : catégories, flux d'argent, épargne et prévisions."""

from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now


class Category(models.Model):
    """Regroupe les mouvements (dépenses, revenus, épargne) sous un libellé et une couleur."""

    class Meta:
        verbose_name = "Catégorie"

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    color = models.CharField(max_length=7, default='#000000')

    def __str__(self):
        return self.name


class SavingsAccount(models.Model):
    """Compte ou groupe d'épargne pour regrouper les mouvements."""

    class Meta:
        verbose_name = "Compte d'épargne"
        ordering = ['name']

    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='savings_accounts')

    def __str__(self):
        return self.name


class Money(models.Model):
    """Modèle abstrait : montant, date, récurrence, catégorie et propriétaire."""

    class Meta:
        abstract = True

    class Frequency(models.TextChoices):
        YEARLY = 'annuel', 'Annuel'
        MONTHLY = 'mensuel', 'Mensuel'
        WEEKLY = 'hebdo', 'Hebdomadaire'
        DAILY = 'journalier', 'Journalière'
        ONCE = 'unique', 'Unique'
    name = models.CharField(max_length=100, verbose_name="Nom de la dépense")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant")
    date = models.DateField(default=now)
    frequency = models.CharField(
        max_length=10,
        choices=Frequency.choices,
        null=True,
        blank=True,
        default=Frequency.ONCE,
        verbose_name="Récurence",
    )
    category = models.ForeignKey('Category', on_delete=models.PROTECT)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class Savings(Money):
    """Mouvement d'épargne, éventuellement rattaché à un compte ou groupe."""

    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements',
    )


class Income(Money):
    """Entrée d'argent (salaire, prime, remboursement, etc.)."""

    pass


class Expense(Money):
    """Dépense enregistrée par l'utilisateur, éventuellement recopiée selon la récurrence."""

    class Meta:
        verbose_name = "Dépense"
        constraints = [
            models.UniqueConstraint(
                fields=['recurring_from', 'date'],
                condition=models.Q(recurring_from__isnull=False),
                name='unique_expense_recurring_date',
            ),
        ]

    recurring_from = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_occurrences',
        verbose_name="Dépense récurrente d'origine",
    )


class PlannedExpense(models.Model):
    """Enveloppe habituelle, ou ajustement d'une catégorie pour un mois précis."""

    class Meta:
        verbose_name = "Dépense prévisionnelle"
        ordering = ['category__name']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'category'],
                condition=models.Q(year__isnull=True),
                name='unique_planned_template_per_category',
            ),
            models.UniqueConstraint(
                fields=['user', 'category', 'year', 'month'],
                condition=models.Q(year__isnull=False),
                name='unique_planned_expense_per_category_month',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(year__isnull=True, month__isnull=True)
                    | models.Q(year__isnull=False, month__isnull=False)
                ),
                name='planned_expense_template_or_month',
            ),
        ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='planned_expenses')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='planned_expenses')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant prévu")
    year = models.PositiveIntegerField(null=True, blank=True)
    month = models.PositiveSmallIntegerField(null=True, blank=True)
    apply_forward = models.BooleanField(
        default=False,
        verbose_name="Appliquer aux mois suivants",
    )

    def __str__(self):
        if self.year and self.month:
            return f"{self.category.name} — {self.month:02d}/{self.year}"
        return f"{self.category.name} — habituel"

    @property
    def is_template(self):
        """Vrai si cette ligne est le montant repris chaque mois."""
        return self.year is None and self.month is None

    @property
    def name(self):
        """Libellé affiché (nom de la catégorie)."""
        return self.category.name
