"""Middleware : complète les dépenses récurrentes à chaque requête authentifiée."""

from main_app.recurrence import materialize_recurring_expenses


class RecurringExpensesMiddleware:
    """Ajoute les occurrences hebdo, mensuelles et annuelles dès que leur date est due."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        path = request.path
        if (
            user is not None
            and user.is_authenticated
            and not path.startswith('/admin/')
            and not path.startswith('/static/')
        ):
            materialize_recurring_expenses(user)
        return self.get_response(request)
