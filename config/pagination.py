from django.core.paginator import Paginator


def paginate_queryset(request, queryset, *, page_size, page_parameter="page"):
    """Return a forgiving Django Page for HTML list views."""
    paginator = Paginator(queryset, page_size)
    return paginator.get_page(request.GET.get(page_parameter))


def pagination_query(request, *, page_parameter="page"):
    """Preserve current filters while replacing only the requested page value."""
    parameters = request.GET.copy()
    parameters.pop(page_parameter, None)
    encoded = parameters.urlencode()
    return f"{encoded}&" if encoded else ""
