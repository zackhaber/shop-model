"""The shop's knowledge files must conform to their schema, agree with each other and with the listings, and
answer the competency questions (Session 7, Stage 16)."""
import hashlib

import pytest

from shop_model.ask import knowledge_route
from shop_model.config import load_config
from shop_model.knowledge import (check_against_schema, complement_pairs, gift_sets_containing, link_listings,
                                  load_knowledge, load_listings, load_questions)

# The listings the earlier sessions were built on must not change: the model, the gate and the monitoring depend
# on them. The knowledge layer is added beside them.
LISTINGS_SHA256 = {
    "data/prices_v2.csv": "3204454704805475aed65f5c535fec764ca3f5c7aeb2a331f2e2d6dcbc839e77",
    "data/holdout.csv": "6f9f166ef89f71275397fdd2a8d5c5f3ce9544a79775944278824963aa072ec1",
}


@pytest.fixture(scope="module")
def kg():
    return load_knowledge()


@pytest.fixture(scope="module")
def listings(kg):
    return link_listings(load_listings(load_config()), kg.products)  # raises if a description has no product


@pytest.mark.parametrize("path", sorted(LISTINGS_SHA256))
def test_the_listings_are_unchanged_since_stage_15(path):
    with open(path, "rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == LISTINGS_SHA256[path]


def test_the_knowledge_files_conform_to_the_schema(kg):
    assert check_against_schema(kg) == []


def test_product_ids_are_unique(kg):
    assert kg.products["product_id"].is_unique


def test_every_recorded_material_and_range_is_known(kg):
    assert set(kg.products["range"]) <= set(kg.ranges)
    recorded = set(kg.products["material"]) - {""}  # an empty material is not known, not "none"
    assert recorded <= set(kg.materials)


@pytest.mark.parametrize("name", ["concepts", "materials"])
def test_the_hierarchy_has_no_cycles(kg, name):
    hierarchy = getattr(kg, name)
    for start in hierarchy:
        seen, current = set(), start
        while current is not None:
            assert current not in seen, f"cycle through {current}"
            seen.add(current)
            current = hierarchy[current].get("is_a")


def test_a_gift_set_contains_products_but_no_gift_set(kg):
    sets = set(kg.products.loc[kg.products["class"] == "GiftSet", "product_id"])
    assert not set(kg.gift_sets["product_id"]) & sets


def test_the_knowledge_route_gives_the_expected_answers(kg, listings):
    for q in load_questions():
        assert knowledge_route(q, listings, kg) == set(q["expected"]), q["id"]


def test_the_expected_relationship_answers_follow_from_the_files(kg, listings):
    """The Stage 17 questions, answered here in Python from the files, as a check on the expected answers."""
    import yaml
    with open("kg/questions.yaml") as f:
        questions = yaml.safe_load(f).get("relationship_questions", [])
    in_range = kg.products.set_index("product_id")["range"]
    sold = set(listings.loc[listings["sold"] == 1, "product_id"])
    for q in questions:
        if q["kind"] == "cross_sell":
            found = {b for pair in complement_pairs(kg) for a in pair for b in pair
                     if a != b and in_range[a] == q["from_range"] and (not q.get("sold") or a in sold)
                     and in_range[b] == q["to_range"]}
        else:
            found = set().union(*(gift_sets_containing(kg.synonyms[t], kg) for t in q["terms"]))
        assert found == set(q["expected"]), q["id"]
