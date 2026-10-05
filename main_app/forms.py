"""Formulaires de saisie pour les catégories, flux d'argent, épargne et prévisions."""

from datetime import date

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from main_app.models import Category, Expense, Income, Savings, SavingsAccount, PlannedExpense


class ExpenseForm(forms.ModelForm):
    """Création et modification d'une dépense."""

    date = forms.DateField(
        initial=timezone.localdate,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            attrs={
                'class': 'form-control',
                'type': 'date',
            },
            format='%Y-%m-%d',
        ),
    )

    class Meta:
        model = Expense
        fields = ['name', 'amount', 'date', 'frequency', 'category']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex. Courses, Loyer, Netflix…',
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Montant en €',
            }),
            'frequency': forms.Select(attrs={
                'class': 'form-select',
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
            }),
        }
        help_texts = {
            'frequency': (
                'Hebdomadaire, mensuel ou annuel : la dépense sera recopiée '
                'automatiquement le même jour (même jour de la semaine, du mois ou de l’année).'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and not getattr(self.instance, 'pk', None):
            today = timezone.localdate()
            self.initial['date'] = today
            self.fields['date'].widget.attrs['value'] = today.isoformat()


class IncomeForm(forms.ModelForm):
    """Création et modification d'une entrée d'argent."""
    date = forms.DateField(
        initial=date.today,
        widget=forms.DateInput(
            attrs={
                'class': 'form-control',
                'type': 'date',
            },
            format='%Y-%m-%d',
        ),
    )

    class Meta:
        model = Income
        fields = ['name', 'amount', 'date', 'frequency', 'category']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex. Salaire, prime, remboursement…',
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Montant en €',
            }),
            'frequency': forms.Select(attrs={
                'class': 'form-select',
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
            }),
        }


class SavingsForm(forms.ModelForm):
    """Création d'un mouvement d'épargne, avec compte optionnel filtré par utilisateur."""
    date = forms.DateField(
        initial=date.today,
        widget=forms.DateInput(
            attrs={
                'class': 'form-control',
                'type': 'date',
            },
            format='%Y-%m-%d',
        ),
    )

    class Meta:
        model = Savings
        fields = ['name', 'amount', 'date', 'frequency', 'category', 'account']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex. Livret A, projet voyage…',
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Montant en €',
            }),
            'frequency': forms.Select(attrs={
                'class': 'form-select',
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
            }),
            'account': forms.Select(attrs={
                'class': 'form-select',
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['account'].queryset = SavingsAccount.objects.filter(user=user)
        self.fields['account'].required = False


class SavingsAccountForm(forms.ModelForm):
    """Création et modification d'un compte ou groupe d'épargne."""
    class Meta:
        model = SavingsAccount
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex. Livret A, Projet maison…',
            }),
        }


class CategoryForm(forms.ModelForm):
    """Création d'une catégorie (description facultative)."""
    class Meta:
        model = Category
        fields = ['name', 'description', 'color']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Ex. Courses, Logement, Loisirs…',
                },
            ),
            'description': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 3,
                    'placeholder': 'Optionnel : note / description interne',
                }
            ),
            'color': forms.TextInput(
                attrs={
                    'class': 'form-control form-control-color',
                    'type': 'color',
                }
            ),
        }


class PlannedExpenseForm(forms.ModelForm):
    """Montant habituel d'une catégorie, repris chaque mois."""
    class Meta:
        model = PlannedExpense
        fields = ['category', 'amount']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Montant prévu en €',
                'step': '0.01',
                'min': '0',
            }),
        }
        help_texts = {
            'amount': 'Ce montant est repris chaque mois, sauf si tu l’ajustes pour un mois précis.',
        }

    def __init__(self, *args, user=None, lock_category=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if lock_category:
            self.fields['category'].disabled = True

    def clean(self):
        """Refuse deux montants habituels pour la même catégorie."""
        cleaned = super().clean()
        user = self.user
        category = cleaned.get('category')
        if user and category and not self.instance.year:
            qs = PlannedExpense.objects.filter(
                user=user,
                category=category,
                year__isnull=True,
                month__isnull=True,
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    'Cette catégorie a déjà un montant habituel.'
                )
        return cleaned


class PlannedMonthAmountForm(forms.Form):
    """Montant d'une prévision, avec report éventuel sur les mois suivants."""
    amount = forms.DecimalField(
        label='Montant prévu',
        min_value=0,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Montant prévu en €',
            'step': '0.01',
            'min': '0',
        }),
    )
    apply_forward = forms.BooleanField(
        required=False,
        label='Appliquer cette modification aux prévisions suivantes',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
