import json
from functools import wraps

from django.core.paginator import EmptyPage, Paginator
from django.http import JsonResponse


def api_error(message, *, status=400, errors=None):
    payload = {"error": message}
    if errors is not None:
        payload["details"] = errors
    return JsonResponse(payload, status=status)


def parse_json(request):
    if not request.body:
        return {}, None

    try:
        payload = json.loads(request.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, api_error("Request body must be valid JSON.")

    if not isinstance(payload, dict):
        return None, api_error("Request body must be a JSON object.")

    return payload, None


def api_login_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return api_error("Authentication required.", status=401)
        return view(request, *args, **kwargs)

    return wrapped


def paginate(request, queryset, *, default_size=24, max_size=100):
    try:
        page_number = max(1, int(request.GET.get("page", 1)))
        page_size = int(request.GET.get("page_size", default_size))
        page_size = min(max(1, page_size), max_size)
    except (TypeError, ValueError):
        return None, api_error("page and page_size must be integers.")

    paginator = Paginator(queryset, page_size)
    try:
        page = paginator.page(page_number)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    return {
        "items": page.object_list,
        "pagination": {
            "page": page.number,
            "page_size": page_size,
            "pages": paginator.num_pages,
            "total": paginator.count,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
        },
    }, None


def parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return None


def api_root(request):
    if request.method != "GET":
        return api_error("Method not allowed.", status=405)
    return JsonResponse({
        "name": "Yu-Gi-Oh Deck Builder API",
        "endpoints": {
            "auth": "/api/auth/",
            "cards": "/api/cards/",
            "decks": "/api/decks/",
            "collection": "/api/collection/",
            "banlists": "/api/banlists/",
        },
    })
