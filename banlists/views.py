from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render

from cards.views import serialize_card
from config.api import api_error, paginate, parse_bool
from config.pagination import paginate_queryset, pagination_query

from .models import BanList, BanListEntry
from .services import get_active_banlist, get_banlist_status_counts


def serialize_banlist(banlist, *, include_entries=False, entries=None, pagination=None):
    payload = {
        "id": banlist.pk,
        "name": banlist.name,
        "format": banlist.format,
        "effective_date": (
            banlist.effective_date.isoformat() if banlist.effective_date else None
        ),
        "is_active": banlist.is_active,
        "source_url": banlist.source_url,
        "created_at": banlist.created_at.isoformat(),
        "updated_at": banlist.updated_at.isoformat(),
    }
    if include_entries:
        payload["entries"] = [
            {
                "id": entry.pk,
                "card": serialize_card(entry.card),
                "status": entry.status,
                "max_copies": entry.max_copies,
                "note": entry.note,
            }
            for entry in entries
        ]
        payload["pagination"] = pagination
    return payload


def banlist_list(request):
    if request.method != "GET":
        return api_error("Method not allowed.", status=405)
    banlists = BanList.objects.all()
    banlist_format = request.GET.get("format", "").upper()
    if banlist_format:
        banlists = banlists.filter(format=banlist_format)
    active = parse_bool(request.GET.get("active"))
    if active is not None:
        banlists = banlists.filter(is_active=active)
    page, error = paginate(
        request,
        banlists.order_by("-effective_date", "-updated_at", "-pk"),
        default_size=20,
        max_size=100,
    )
    if error:
        return error
    return JsonResponse({
        "results": [serialize_banlist(item) for item in page["items"]],
        "pagination": page["pagination"],
    })


def current_banlist(request):
    if request.method != "GET":
        return api_error("Method not allowed.", status=405)
    banlist_format = request.GET.get("format", "TCG").upper()
    if banlist_format not in {"TCG", "OCG"}:
        return api_error("format must be TCG or OCG.")
    banlist = get_active_banlist(banlist_format)
    if banlist is None:
        return api_error("No active ban list found for this format.", status=404)
    return JsonResponse({"banlist": serialize_banlist(banlist)})


def banlist_detail(request, banlist_id):
    if request.method != "GET":
        return api_error("Method not allowed.", status=405)
    banlist = get_object_or_404(BanList, pk=banlist_id)
    entries = BanListEntry.objects.filter(ban_list=banlist).select_related("card")
    query = request.GET.get("q", "").strip()
    if query:
        entries = entries.filter(
            Q(card__name__icontains=query)
            | Q(card__archetype__icontains=query)
        )
    status = request.GET.get("status", "").upper()
    if status:
        entries = entries.filter(status=status)
    page, error = paginate(
        request,
        entries.order_by("status", "card__name", "pk"),
        default_size=50,
        max_size=100,
    )
    if error:
        return error
    return JsonResponse({
        "banlist": serialize_banlist(
            banlist,
            include_entries=True,
            entries=page["items"],
            pagination=page["pagination"],
        )
    })


def banlist_page(request):
    banlist_format = request.GET.get("format", "TCG").upper()
    if banlist_format not in {"TCG", "OCG"}:
        banlist_format = "TCG"
    banlist = get_active_banlist(banlist_format)
    entries = BanListEntry.objects.none()
    status_counts = {
        "total": 0,
        "forbidden": 0,
        "limited": 0,
        "semi_limited": 0,
    }
    selected_status = request.GET.get("status", "").upper()
    valid_statuses = {choice[0] for choice in BanListEntry.STATUS_CHOICES}
    if selected_status not in valid_statuses:
        selected_status = ""
    if banlist:
        base_entries = banlist.entries.select_related("card")
        status_counts = get_banlist_status_counts(banlist)
        entries = base_entries
        query = request.GET.get("q", "").strip()
        if query:
            entries = entries.filter(
                Q(card__name__icontains=query)
                | Q(card__archetype__icontains=query)
                | Q(card__card_type__icontains=query)
            )
        if selected_status:
            entries = entries.filter(status=selected_status)
    else:
        query = request.GET.get("q", "").strip()
    page_obj = paginate_queryset(
        request,
        entries.order_by("status", "card__name", "pk"),
        page_size=30,
    )
    return render(request, "banlists/banlist_list.html", {
        "banlist": banlist,
        "banlist_return_url": request.get_full_path(),
        "entries": page_obj,
        "page_obj": page_obj,
        "pagination_query": pagination_query(request),
        "selected_format": banlist_format,
        "selected_status": selected_status,
        "status_counts": status_counts,
        "query": query,
    })
