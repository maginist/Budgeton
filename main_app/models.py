from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now


class Category(models.Model):
    class Meta:
        verbose_name = "Catégorie"

    name = models.CharField(max_length=100)
    description = models.TextField()
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
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements',
    )


class Income(Money):
    pass


class Expense(Money):
    pass
