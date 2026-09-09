from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from .catalog import get_card_catalog_facets
from .models import Card
from .services import split_translation_chunks
from banlists.models import BanList, BanListEntry


class CardCatalogCacheTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_catalog_facets_are_cached_and_invalidated_when_cards_change(self):
        Card.objects.create(
            card_id=990001,
            name="Cached Dragon",
            card_type="Effect Monster",
            frame_type="effect",
            race="Dragon",
            attribute="DARK",
        )

        first = get_card_catalog_facets()
        with self.assertNumQueries(1):
            second = get_card_catalog_facets()

        self.assertEqual(first, second)
        self.assertEqual(first["total_cards"], 1)

        Card.objects.create(
            card_id=990002,
            name="Cache Invalidation Spell",
            card_type="Spell Card",
            race="Quick-Play",
        )
        refreshed = get_card_catalog_facets()

        self.assertEqual(refreshed["total_cards"], 2)
        self.assertIn("Quick-Play", refreshed["spell_types"])


class CardApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dark_magician = Card.objects.create(
            card_id=46986414,
            name="Dark Magician",
            card_type="Normal Monster",
            frame_type="normal",
            race="Spellcaster",
            attribute="DARK",
            archetype="Dark Magician",
            description="The ultimate wizard in terms of attack and defense.",
            atk=2500,
            defense=2100,
            level=7,
        )
        Card.objects.create(
            card_id=89631139,
            name="Blue-Eyes White Dragon",
            card_type="Normal Monster",
            frame_type="normal",
            race="Dragon",
            attribute="LIGHT",
            archetype="Blue-Eyes",
            atk=3000,
            defense=2500,
            level=8,
        )
        Card.objects.create(
            card_id=53129443,
            name="Dark Magical Circle",
            card_type="Spell Card",
            frame_type="spell",
            archetype="Dark Magician",
        )

    def test_list_search_filter_and_pagination(self):
        response = self.client.get(
            reverse("cards:list"),
            {"q": "dark", "type": "Normal Monster", "page_size": 1},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(payload["results"][0]["name"], "Dark Magician")

    def test_search_matches_card_names_without_punctuation(self):
        spaced = self.client.get(
            reverse("cards:list"),
            {"q": "blue eyes white dragon", "page_size": 30},
        )
        compact = self.client.get(
            reverse("cards:list"),
            {"q": "blueeye", "page_size": 30},
        )

        self.assertEqual(spaced.status_code, 200)
        self.assertEqual(spaced.json()["results"][0]["name"], "Blue-Eyes White Dragon")
        self.assertIn(
            "Blue-Eyes White Dragon",
            [card["name"] for card in compact.json()["results"]],
        )

    def test_related_card_search_can_continue_to_the_next_page(self):
        Card.objects.create(
            card_id=38517737,
            name="Blue-Eyes Alternative White Dragon",
            card_type="Effect Monster",
            archetype="Blue-Eyes",
        )

        first = self.client.get(
            reverse("cards:list"),
            {"q": "blue-eyes", "page_size": 1, "page": 1},
        ).json()
        second = self.client.get(
            reverse("cards:list"),
            {"q": "blue-eyes", "page_size": 1, "page": 2},
        ).json()

        self.assertEqual(first["pagination"]["total"], 2)
        self.assertTrue(first["pagination"]["has_next"])
        self.assertNotEqual(first["results"][0]["card_id"], second["results"][0]["card_id"])

    def test_builder_search_includes_selected_banlist_status(self):
        banlist = BanList.objects.create(name="TCG Test", format="TCG")
        BanListEntry.objects.create(
            ban_list=banlist,
            card=self.dark_magician,
            status="LIMITED",
            max_copies=1,
        )

        response = self.client.get(
            reverse("cards:list"),
            {"q": "Dark Magician", "ban_list": banlist.pk},
        )

        card = response.json()["results"][0]
        self.assertEqual(card["ban_status"], "LIMITED")
        self.assertEqual(card["max_copies"], 1)

    def test_card_payload_identifies_extra_deck_cards(self):
        fusion = Card.objects.create(
            card_id=89631140,
            name="Blue-Eyes Ultimate Dragon",
            card_type="Fusion Monster",
            frame_type="fusion",
        )

        response = self.client.get(reverse("cards:detail", args=[fusion.card_id]))

        self.assertTrue(response.json()["card"]["is_extra_deck_card"])
        self.assertFalse(
            self.client.get(
                reverse("cards:detail", args=[self.dark_magician.card_id])
            ).json()["card"]["is_extra_deck_card"]
        )

    def test_all_supported_extra_deck_frame_types_are_identified(self):
        for frame_type in (
            "fusion",
            "fusion_pendulum",
            "synchro",
            "synchro_pendulum",
            "xyz",
            "xyz_pendulum",
            "link",
        ):
            with self.subTest(frame_type=frame_type):
                self.assertTrue(Card(frame_type=frame_type).is_extra_deck_card)

    def test_detail_uses_public_card_id(self):
        response = self.client.get(
            reverse("cards:detail", args=[self.dark_magician.card_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["card"]["atk"], 2500)

    def test_rejects_unsupported_ordering(self):
        response = self.client.get(reverse("cards:list"), {"ordering": "card_id"})
        self.assertEqual(response.status_code, 400)

    def test_catalog_and_detail_pages_render(self):
        catalog = self.client.get(reverse("cards_page:list"), {"q": "Dark Magician"})
        detail = self.client.get(
            reverse("cards_page:detail", args=[self.dark_magician.card_id])
        )
        self.assertEqual(catalog.status_code, 200)
        self.assertContains(catalog, "Arcane")
        self.assertNotContains(catalog, "data-card-zoom")
        self.assertContains(catalog, "ดูรายละเอียดและเอฟเฟกต์ของ Dark Magician")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Dark Magician")
        self.assertContains(detail, 'data-card-zoom data-card-name="Dark Magician"')

    def test_detail_back_link_preserves_archive_search_and_filters(self):
        catalog = self.client.get(
            reverse("cards_page:list"),
            {"q": "Dark Magician", "attribute": "DARK", "type": "Normal Monster"},
        )
        return_url = catalog.context["archive_return_url"]
        detail = self.client.get(
            reverse("cards_page:detail", args=[self.dark_magician.card_id]),
            {"return": return_url},
        )

        self.assertContains(catalog, "return=/cards/%3Fq%3DDark%2BMagician")
        self.assertContains(
            detail,
            'href="/cards/?q=Dark+Magician&amp;type=Normal+Monster&amp;attribute=DARK"',
        )

    def test_detail_back_link_rejects_external_return_url(self):
        detail = self.client.get(
            reverse("cards_page:detail", args=[self.dark_magician.card_id]),
            {"return": "https://example.com/not-the-archive"},
        )

        self.assertContains(detail, 'class="back-link" href="/cards/"')
        self.assertContains(
            detail,
            'class="app-body card-detail-page min-h-screen',
        )

    def test_detail_back_link_accepts_deck_builder_return_url(self):
        return_url = reverse("decks_page:builder", args=[42])

        detail = self.client.get(
            reverse("cards_page:detail", args=[self.dark_magician.card_id]),
            {"return": return_url},
        )

        self.assertContains(detail, f'href="{return_url}"')
        self.assertContains(detail, "Back to deck")

    def test_detail_back_link_accepts_new_deck_return_url(self):
        return_url = reverse("decks_page:create")

        detail = self.client.get(
            reverse("cards_page:detail", args=[self.dark_magician.card_id]),
            {"return": return_url},
        )

        self.assertContains(detail, f'href="{return_url}"')
        self.assertContains(detail, "Back to deck builder")

    def test_monster_detail_renders_one_star_per_level(self):
        response = self.client.get(
            reverse("cards_page:detail", args=[self.dark_magician.card_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="monster-level__star"', count=7)
        self.assertContains(response, "พลังโจมตี")

    def test_unknown_monster_attack_and_defense_render_as_question_marks(self):
        unknown_stats = Card.objects.create(
            card_id=10000001,
            name="Unknown Stats Monster",
            card_type="Effect Monster",
            frame_type="effect",
            race="Creator God",
            attribute="DIVINE",
            atk=-1,
            defense=None,
            level=12,
        )

        response = self.client.get(
            reverse("cards_page:detail", args=[unknown_stats.card_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<strong>?</strong>", count=2, html=True)
        self.assertNotContains(response, "<strong>-1</strong>", html=True)

    def test_card_effect_renders_thai_and_english_tabs(self):
        response = self.client.get(
            reverse("cards_page:detail", args=[self.dark_magician.card_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="tablist"')
        self.assertContains(response, 'data-effect-tab="th"')
        self.assertContains(response, 'data-effect-tab="en"')
        self.assertContains(response, "ภาษาไทย(DEMO)")
        self.assertContains(response, 'id="effect-panel-th"')
        self.assertContains(response, 'id="effect-panel-en"')
        self.assertContains(
            response,
            'id="effect-tab-en" type="button" role="tab" aria-selected="true"',
        )
        self.assertContains(
            response,
            'id="effect-panel-th" role="tabpanel" aria-labelledby="effect-tab-th" data-effect-panel="th" lang="th" hidden',
        )
        self.assertContains(response, "The ultimate wizard in terms of attack and defense.")
        self.assertContains(response, "กดแท็บภาษาไทยเพื่อแปลข้อความการ์ดใบนี้")
        self.assertContains(
            response,
            'if (tab.dataset.effectTab === "th") loadThaiTranslation();',
        )

    @patch("cards.views.translate_description", return_value="จอมเวทที่แข็งแกร่งที่สุด")
    def test_translation_endpoint_translates_and_caches_card_text(self, translate):
        url = reverse("cards:translation", args=[self.dark_magician.card_id])

        first = self.client.post(url, data="{}", content_type="application/json")
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.json()["cached"])
        self.dark_magician.refresh_from_db()
        self.assertEqual(
            self.dark_magician.description_th,
            "จอมเวทที่แข็งแกร่งที่สุด",
        )

        second = self.client.post(url, data="{}", content_type="application/json")
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["cached"])
        translate.assert_called_once()

    def test_translation_endpoint_rejects_get(self):
        response = self.client.get(
            reverse("cards:translation", args=[self.dark_magician.card_id])
        )
        self.assertEqual(response.status_code, 405)

    def test_translation_chunks_preserve_card_text_paragraphs(self):
        chunks = split_translation_chunks("2 Level 4 monsters\nNegate the attack.")
        self.assertEqual(chunks, ["2 Level 4 monsters", "Negate the attack."])


class CardCatalogProgressiveFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cards = [
            Card(card_id=71001, name="Dragon Soldier", card_type="Normal Monster", frame_type="normal", race="Dragon", attribute="LIGHT"),
            Card(card_id=71002, name="Divine Avatar", card_type="Effect Monster", frame_type="effect", race="Divine-Beast", attribute="DIVINE"),
            Card(card_id=71003, name="Fusion Dragon", card_type="Fusion Monster", frame_type="fusion", race="Dragon", attribute="DARK"),
            Card(card_id=71004, name="Fusion Pendulum Mage", card_type="Pendulum Effect Fusion Monster", frame_type="fusion_pendulum", race="Spellcaster", attribute="DARK"),
            Card(card_id=71005, name="Quick Spell", card_type="Spell Card", frame_type="spell", race="Quick-Play"),
            Card(card_id=71006, name="Normal Spell", card_type="Spell Card", frame_type="spell", race="Normal"),
            Card(card_id=71007, name="Counter Trap", card_type="Trap Card", frame_type="trap", race="Counter"),
            Card(card_id=71008, name="Normal Trap", card_type="Trap Card", frame_type="trap", race="Normal"),
        ]
        Card.objects.bulk_create(cards)

    def card_names(self, response):
        return [card.name for card in response.context["page_obj"]]

    def get_catalog(self, **params):
        return self.client.get(reverse("cards_page:list"), params)

    def test_all_card_types_ignores_monster_specific_filters(self):
        response = self.get_catalog(attribute="DARK", race="Dragon", frame="fusion")

        self.assertEqual(response.context["page_obj"].paginator.count, 8)
        self.assertEqual(response.context["selected_attribute"], "")
        self.assertEqual(response.context["selected_race"], "")
        self.assertEqual(response.context["selected_frame"], "")

    def test_monster_dragon_filters_correctly(self):
        response = self.get_catalog(type="monster", race="Dragon")

        self.assertCountEqual(self.card_names(response), ["Dragon Soldier", "Fusion Dragon"])

    def test_monster_divine_beast_filters_correctly(self):
        response = self.get_catalog(type="monster", race="Divine-Beast")

        self.assertEqual(self.card_names(response), ["Divine Avatar"])

    def test_monster_fusion_group_includes_pendulum_fusion(self):
        response = self.get_catalog(type="monster", frame="fusion")

        self.assertCountEqual(self.card_names(response), ["Fusion Dragon", "Fusion Pendulum Mage"])

    def test_monster_dragon_and_fusion_work_together(self):
        response = self.get_catalog(type="monster", race="Dragon", frame="fusion")

        self.assertEqual(self.card_names(response), ["Fusion Dragon"])

    def test_spell_filter_works(self):
        response = self.get_catalog(type="spell")

        self.assertCountEqual(self.card_names(response), ["Quick Spell", "Normal Spell"])

    def test_quick_play_spell_type_works(self):
        response = self.get_catalog(type="spell", race="Quick-Play")

        self.assertEqual(self.card_names(response), ["Quick Spell"])

    def test_trap_filter_works(self):
        response = self.get_catalog(type="trap")

        self.assertCountEqual(self.card_names(response), ["Counter Trap", "Normal Trap"])

    def test_counter_trap_type_works(self):
        response = self.get_catalog(type="trap", race="Counter")

        self.assertEqual(self.card_names(response), ["Counter Trap"])

    def test_spell_ignores_stale_monster_filters(self):
        response = self.get_catalog(
            type="spell", attribute="DARK", race="Dragon", frame="fusion"
        )

        self.assertCountEqual(self.card_names(response), ["Quick Spell", "Normal Spell"])
        self.assertEqual(response.context["pagination_query"], "type=spell&")

    def test_monster_ignores_stale_spell_type(self):
        response = self.get_catalog(type="monster", race="Quick-Play")

        self.assertEqual(response.context["page_obj"].paginator.count, 4)
        self.assertEqual(response.context["selected_race"], "")

    def test_pagination_preserves_valid_filters(self):
        Card.objects.bulk_create([
            Card(
                card_id=72000 + index,
                name=f"Pagination Dragon {index:02d}",
                card_type="Effect Monster",
                frame_type="effect",
                race="Dragon",
                attribute="WIND",
            )
            for index in range(30)
        ])

        response = self.get_catalog(type="monster", race="Dragon")

        self.assertTrue(response.context["page_obj"].has_next())
        self.assertContains(response, "?type=monster&amp;race=Dragon&amp;page=2")

    def test_search_works_with_monster_filters(self):
        response = self.get_catalog(
            q="Fusion Dragon", type="monster", race="Dragon", frame="fusion"
        )

        self.assertEqual(self.card_names(response), ["Fusion Dragon"])

    def test_progressive_controls_hide_and_disable_irrelevant_fields(self):
        default_response = self.get_catalog()
        monster_response = self.get_catalog(type="monster")

        self.assertContains(default_response, 'data-filter-for="monster" hidden')
        self.assertContains(default_response, 'aria-label="Monster Type" disabled')
        self.assertContains(monster_response, 'aria-label="Monster Type"')
        self.assertNotContains(monster_response, 'data-filter-for="monster" hidden')
        self.assertContains(monster_response, 'data-filter-for="spell" hidden')
