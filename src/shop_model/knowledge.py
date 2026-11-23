"""The shop's product knowledge, read from the files in kg/ (Session 7, Stage 16).

The files of Shop knowledge v1.0 hold what the listings alone cannot say:
    kg/schema.yaml             the classes, properties and relationships, with cardinalities; the files conform to it
    kg/products.csv            one row per product, listed or not yet listed: identifier, class, name, material, range
    kg/product_categories.csv  which category each product is in; a product can be in more than one
    kg/gift_sets.csv           which products each gift set contains
    kg/taxonomy.yaml           departments, categories and subcategories, each a kind of its broader concept
    kg/materials.yaml          materials, each a kind of its broader material (oak is a wood)
    kg/complements.yaml        which categories go with which: rules from which pairs of products are derived
    kg/synonyms.yaml           the words staff use, each mapped to a concept, a range or a material
    kg/questions.yaml          the competency questions, with the answers the shop expects

Stage 17 loads the same files into Neo4j; this module answers from them directly.
"""
import logging
from dataclasses import dataclass

import pandas as pd
import yaml

from shop_model.config import data_path

logger = logging.getLogger(__name__)

SCHEMA_PATH = "kg/schema.yaml"
PRODUCTS_PATH = "kg/products.csv"
GIFT_SETS_PATH = "kg/gift_sets.csv"
COMPLEMENTS_PATH = "kg/complements.yaml"
PRODUCT_CATEGORIES_PATH = "kg/product_categories.csv"
TAXONOMY_PATH = "kg/taxonomy.yaml"
MATERIALS_PATH = "kg/materials.yaml"
SYNONYMS_PATH = "kg/synonyms.yaml"
QUESTIONS_PATH = "kg/questions.yaml"


@dataclass
class Knowledge:
    """Everything the shop knows about its products, read once from kg/."""
    products: pd.DataFrame
    product_categories: pd.DataFrame
    gift_sets: pd.DataFrame
    concepts: dict
    ranges: dict
    materials: dict
    complements: list
    synonyms: dict


def load_listings(config):
    """Every listing the shop has: the training data and the frozen holdout, one row per listing.

    The holdout stays frozen for the quality gate; reading it here, to answer questions about what sold,
    does not train anything on it.
    """
    parts = [pd.read_csv(data_path(config)), pd.read_csv(config["holdout_path"])]
    return pd.concat(parts, ignore_index=True)


def load_products(path=PRODUCTS_PATH):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def load_product_categories(path=PRODUCT_CATEGORIES_PATH):
    return pd.read_csv(path, dtype=str)


def load_taxonomy(path=TAXONOMY_PATH):
    """Concepts (departments, categories and subcategories) and ranges, each keyed by its identifier."""
    with open(path) as f:
        raw = yaml.safe_load(f)
    concepts = {c["id"]: c for c in raw["concepts"]}
    ranges = {r["id"]: r for r in raw["ranges"]}
    return concepts, ranges


def load_materials(path=MATERIALS_PATH):
    with open(path) as f:
        return {m["id"]: m for m in yaml.safe_load(f)["materials"]}


def load_gift_sets(path=GIFT_SETS_PATH):
    return pd.read_csv(path, dtype=str)


def load_complements(path=COMPLEMENTS_PATH):
    with open(path) as f:
        return yaml.safe_load(f)["rules"]


def load_schema(path=SCHEMA_PATH):
    with open(path) as f:
        return yaml.safe_load(f)


def load_synonyms(path=SYNONYMS_PATH):
    with open(path) as f:
        return yaml.safe_load(f)["terms"]


def load_questions(path=QUESTIONS_PATH):
    with open(path) as f:
        return yaml.safe_load(f)["questions"]


def load_knowledge():
    concepts, ranges = load_taxonomy()
    return Knowledge(products=load_products(), product_categories=load_product_categories(),
                     gift_sets=load_gift_sets(), concepts=concepts, ranges=ranges, materials=load_materials(),
                     complements=load_complements(), synonyms=load_synonyms())


def narrower(hierarchy, broad_id):
    """The concept and every concept that is a kind of it, at any depth. Works for either hierarchy."""
    found = {broad_id}
    changed = True
    while changed:
        changed = False
        for item_id, item in hierarchy.items():
            if item.get("is_a") in found and item_id not in found:
                found.add(item_id)
                changed = True
    return found


def link_listings(listings, products):
    """Attach a product_id to every listing, by its description. A listing with no product is an error."""
    linked = listings.merge(products[["product_id", "name"]], left_on="description", right_on="name",
                            how="left")
    unmatched = linked[linked["product_id"].isna()]["description"].unique()
    if len(unmatched):
        raise ValueError(f"Listings with no product in {PRODUCTS_PATH}: {sorted(unmatched)}")
    return linked.drop(columns="name")


def products_for(concept_id, kg):
    """The products a concept covers: every product in a range; every product made of a material or any
    narrower one; or every product in a category or any narrower one."""
    if concept_id in kg.ranges:
        return set(kg.products.loc[kg.products["range"] == concept_id, "product_id"])
    if concept_id in kg.materials:
        made_of = narrower(kg.materials, concept_id)
        return set(kg.products.loc[kg.products["material"].isin(made_of), "product_id"])
    categories = narrower(kg.concepts, concept_id)
    pc = kg.product_categories
    return set(pc.loc[pc["category"].isin(categories), "product_id"])


def complement_pairs(kg):
    """Every pair of products that go with each other, derived from the rules between categories. A rule covers the
    products in each category and in every narrower one. Pairs are unordered: a frozenset of two product ids."""
    pc = kg.product_categories
    pairs = set()
    for rule in kg.complements:
        first, second = (set(pc.loc[pc["category"].isin(narrower(kg.concepts, c)), "product_id"])
                         for c in rule["categories"])
        pairs |= {frozenset((a, b)) for a in first for b in second if a != b}
    return pairs


def gift_sets_containing(concept_id, kg):
    """The gift sets that contain at least one product the concept covers."""
    covered = products_for(concept_id, kg)
    gs = kg.gift_sets
    return set(gs.loc[gs["product_id"].isin(covered), "gift_set_id"])


def instances(kg):
    """The instances of each class in the schema, by key."""
    products = kg.products
    return {
        "Department": {c for c, v in kg.concepts.items() if "is_a" not in v},
        "Category": {c for c, v in kg.concepts.items() if "is_a" in v},
        "Material": set(kg.materials),
        "Range": set(kg.ranges),
        "Product": set(products["product_id"]),
        "GiftSet": set(products.loc[products["class"] == "GiftSet", "product_id"]),
        "Term": set(kg.synonyms),
    }


def relationships(kg):
    """Every relationship the knowledge files state, as (name, from, to) triples of keys."""
    p = kg.products
    rels = [("IN_CATEGORY", r.product_id, r.category) for r in kg.product_categories.itertuples()]
    rels += [("IN_RANGE", r.product_id, r.range) for r in p.itertuples()]
    rels += [("MADE_OF", r.product_id, r.material) for r in p.itertuples() if r.material]
    rels += [("BROADER", c, v["is_a"]) for c, v in kg.concepts.items() if "is_a" in v]
    rels += [("BROADER", m, v["is_a"]) for m, v in kg.materials.items() if v.get("is_a")]
    rels += [("CONTAINS", r.gift_set_id, r.product_id) for r in kg.gift_sets.itertuples()]
    rels += [("GOES_WITH", *rule["categories"]) for rule in kg.complements]
    rels += [("MEANS", t, c) for t, c in kg.synonyms.items()]
    return rels


def check_against_schema(kg, schema=None):
    """Check every relationship in the knowledge files against the schema: the class at each end, and how many each
    instance has. Returns a list of violations, empty when the files conform."""
    schema = schema or load_schema()
    inst = instances(kg)
    rels = relationships(kg)
    violations = []
    for spec in schema["relationships"]:
        if spec["from"] == "Listing":
            continue  # listings are data, linked by link_listings, not knowledge files
        allowed = set().union(*(inst[c] for c in spec["to"]))
        found = [(a, b) for name, a, b in rels if name == spec["name"] and a in inst[spec["from"]]]
        for a, b in found:
            if b not in allowed:
                violations.append(f"{spec['name']} from {a} to {b}: {b} is not a {' or '.join(spec['to'])}")
        counts = pd.Series([a for a, b in found if b in allowed]).value_counts()
        for a in sorted(inst[spec["from"]]):
            n = int(counts.get(a, 0))
            if n < spec["min"] or (spec["max"] is not None and n > spec["max"]):
                bounds = f"{spec['min']}..{spec['max'] if spec['max'] is not None else '*'}"
                violations.append(f"{spec['from']} {a} has {n} {spec['name']}, expected {bounds}")
    return violations
