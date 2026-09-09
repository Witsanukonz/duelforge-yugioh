from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from cards.models import Card
from cards.views import serialize_card
from config.api import api_error, paginate, parse_bool, parse_json
from config.pagination import paginate_queryset, pagination_query

from .forms import CollectionForm
from .models import Collection


def serialize_collection(item):
    return {
        "id": item.pk,
        "card": serialize_card(item.card),
        "quantity": item.quantity,
        "condition": item.condition,
        "is_favorite": item.is_favorite,
        "note": item.note,
        "added_at": item.added_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def collection_form_payload(payload, instance=None):
    fields = ("quantity", "condition", "is_favorite", "note")
    if instance is None:
        return {field: payload[field] for field in fields if field in payload}
    data = {field: getattr(instance, field) for field in fields}
    data.update({field: payload[field] for field in fields if field in payload})
    return data


def form_error(form):
    return api_error(
        "Validation failed.", errors=form.errors.get_json_data()
    )


def filtered_collection_items(request):
    items = Collection.objects.filter(user=request.user).select_related("card")
    query = request.GET.get("q", "").strip()
    if query:
        items = items.filter(
            Q(card__name__icontains=query)
            | Q(card__archetype__icontains=query)
            | Q(note__icontains=query)
        )
    condition = request.GET.get("condition", "").upper()
    if condition:
        items = items.filter(condition=condition)
    favorite = parse_bool(request.GET.get("favorite"))
    if favorite is not None:
        items = items.filter(is_favorite=favorite)
    return items, query


def collection_list(request):
    if not request.user.is_authenticated:
        return api_error("Authentication required.", status=401)

    if request.method == "GET":
        items, _ = filtered_collection_items(request)

        allowed_ordering = {
            "card__name", "-card__name", "quantity", "-quantity",
            "updated_at", "-updated_at",
        }
        ordering = request.GET.get("ordering", "-updated_at")
        if ordering not in allowed_ordering:
            return api_error("Unsupported ordering value.")
        page, error = paginate(
            request, items.order_by(ordering, "pk"), default_size=24, max_size=100
        )
        if error:
            return error
        return JsonResponse({
            "results": [serialize_collection(item) for item in page["items"]],
            "pagination": page["pagination"],
        })

    if request.method == "POST":
        payload, error = parse_json(request)
        if error:
            return error
        card_id = payload.get("card_id")
        if card_id is None:
            return api_error("card_id is required.")
        card = get_object_or_404(Card, card_id=card_id)
        if Collection.objects.filter(user=request.user, card=card).exists():
            return api_error("This card is already in your collection.", status=409)
        form = CollectionForm(collection_form_payload(payload))
        if not form.is_valid():
            return form_error(form)
        item = form.save(commit=False)
        item.user = request.user
        item.card = card
        try:
            item.save()
        except IntegrityError:
            return api_error("This card is already in your collection.", status=409)
        return JsonResponse({"collection_item": serialize_collection(item)}, status=201)

    return api_error("Method not allowed.", status=405)


def collection_detail(request, item_id):
    if not request.user.is_authenticated:
        return api_error("Authentication required.", status=401)
    item = get_object_or_404(
        Collection.objects.select_related("card"),
        pk=item_id,
        user=request.user,
    )
    if request.method == "GET":
        return JsonResponse({"collection_item": serialize_collection(item)})
    if request.method == "PATCH":
        payload, error = parse_json(request)
        if error:
            return error
        form = CollectionForm(
            collection_form_payload(payload, item), instance=item
        )
        if not form.is_valid():
            return form_error(form)
        item = form.save()
        return JsonResponse({"collection_item": serialize_collection(item)})
    if request.method == "DELETE":
        item.delete()
        return JsonResponse({}, status=204)
    return api_error("Method not allowed.", status=405)


@login_required
def collection_page(request):
    items, query = filtered_collection_items(request)
    page_obj = paginate_queryset(
        request,
        items.order_by("-is_favorite", "card__name", "pk"),
        page_size=24,
    )
    stats = Collection.objects.filter(user=request.user).aggregate(
        unique_cards=Count("pk"),
        total_copies=Sum("quantity"),
    )
    return render(request, "collects/collection_list.html", {
        "items": page_obj,
        "page_obj": page_obj,
        "pagination_query": pagination_query(request),
        "query": query,
        "unique_cards": stats["unique_cards"],
        "total_copies": stats["total_copies"] or 0,
    })
