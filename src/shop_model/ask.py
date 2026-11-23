"""Answer the staff questions two ways, and score each against the answers the shop expects (Session 7).

    shop-ask questions                 both routes, one line per question and route
    shop-ask questions --route keyword the keyword route only
    shop-ask questions --show          also list the products each route found, missed or got wrong
    shop-ask profile                   listings against products: what the data holds
    shop-ask sales --by department     listings, sales and sell-through rate by department, material or range

The keyword route is what a simple assistant does with the listings alone: keep the listings whose
description contains a word from the question. The knowledge route looks the word up in the shop's
vocabulary, follows it to a concept (a department, category, range or material), and from there, down every
level of the hierarchy, to the products.
"""
import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from shop_model.config import load_config
import pandas as pd

from shop_model.knowledge import link_listings, load_knowledge, load_listings, load_questions, products_for
from shop_model.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def apply_filters(listings, question):
    """The conditions in the question that the listings can check: a price ceiling, and whether it sold."""
    keep = listings
    if "max_price" in question:
        keep = keep[keep["price"] < question["max_price"]]
    if question.get("sold"):
        keep = keep[keep["sold"] == 1]
    return keep


def keyword_route(question, listings):
    """Listings whose description contains any of the question's words, as distinct products."""
    pattern = "|".join(question["terms"])
    matched = listings[listings["description"].str.contains(pattern, case=False, regex=True)]
    if question.get("listed") is False:
        return set()  # the listings hold only what has been listed: a product never listed cannot be found in them
    return set(apply_filters(matched, question)["product_id"])


def knowledge_route(question, listings, kg):
    """The question's words, through the vocabulary, to concepts, to products, to their listings."""
    concept_ids = {kg.synonyms[t] for t in question["terms"] if t in kg.synonyms}
    covered = set()
    for concept_id in concept_ids:
        covered |= products_for(concept_id, kg)
    if question.get("listed") is False:
        return covered - set(listings["product_id"])  # in the catalogue, never listed
    return set(apply_filters(listings[listings["product_id"].isin(covered)], question)["product_id"])


def score(found, expected):
    """Precision: the share of what was found that is right. Recall: the share of what is right that was found."""
    right = len(found & expected)
    precision = right / len(found) if found else None
    recall = right / len(expected) if expected else None
    return precision, recall


def fmt(value):
    return "  n/a" if value is None else f"{value:5.2f}"


def questions(args, config):
    kg = load_knowledge()
    listings = link_listings(load_listings(config), kg.products)
    routes = ["keyword", "knowledge"] if args.route == "both" else [args.route]

    print(f"{'question':<12} {'route':<10} {'found':>5} {'right':>5} {'expected':>8} {'precision':>9} {'recall':>6}")
    for q in load_questions():
        expected = set(q["expected"])
        for route in routes:
            if route == "keyword":
                found = keyword_route(q, listings)
            else:
                found = knowledge_route(q, listings, kg)
            precision, recall = score(found, expected)
            print(f"{q['id']:<12} {route:<10} {len(found):>5} {len(found & expected):>5} {len(expected):>8} "
                  f"{fmt(precision):>9} {fmt(recall):>6}")
            if args.show:
                for label, items in (("wrong", found - expected), ("missed", expected - found)):
                    if items:
                        print(f"{'':<21}{label}: {', '.join(sorted(items))}")
    return 0


def profile(config):
    listings = load_listings(config)
    kg = load_knowledge()
    products = kg.products
    linked = link_listings(listings, products)
    per_product = linked.groupby("product_id").size()
    same_day = int(listings.duplicated(["listed_at", "description"]).sum())
    print(f"listings                        {len(listings)}")
    print(f"distinct descriptions           {listings['description'].nunique()}")
    print(f"products in kg/products.csv     {len(products)}")
    print(f"products listed                 {linked['product_id'].nunique()}")
    print(f"products never listed           {len(set(products['product_id']) - set(linked['product_id']))}")
    print(f"gift sets                       {int((products['class'] == 'GiftSet').sum())}")
    print(f"listings per product            {per_product.min()} to {per_product.max()}")
    print(f"same product, same day, again   {same_day}")
    print(f"premium-range products          {int((products['range'] == 'premium').sum())}")
    per_category = kg.product_categories.groupby("product_id").size()
    print(f"products in several categories  {int((per_category > 1).sum())}")
    return 0


def top(hierarchy, item_id):
    """The broadest concept above item_id: its department, or its broadest material."""
    while hierarchy[item_id].get("is_a"):
        item_id = hierarchy[item_id]["is_a"]
    return item_id


def sales(by, config):
    """Listings, sales and sell-through rate (the share of listings that sold), by department, material or range.
    None of the three is in the listings: each comes from the knowledge layer."""
    kg = load_knowledge()
    listings = link_listings(load_listings(config), kg.products)
    products = kg.products.set_index("product_id")
    if by == "range":
        groups = pd.DataFrame({"product_id": products.index, "group": products["range"].values})
    elif by == "material":
        groups = pd.DataFrame({"product_id": products.index,
                               "group": [top(kg.materials, m) if m else "(not recorded)" for m in products["material"]]})
    else:  # a product in two departments counts in both
        pc = kg.product_categories
        groups = pd.DataFrame({"product_id": pc["product_id"],
                               "group": [top(kg.concepts, c) for c in pc["category"]]}).drop_duplicates()
    table = listings.merge(groups, on="product_id").groupby("group")["sold"].agg(listings="size", sold="sum")
    table["sell_through"] = table["sold"] / table["listings"]
    names = {**{k: v["name"] for k, v in kg.concepts.items()}, **{k: v["name"] for k, v in kg.materials.items()},
             **{k: v["name"] for k, v in kg.ranges.items()}}
    table.index = [names.get(g, g) for g in table.index]
    print(f"{by:<28} {'listings':>8} {'sold':>5} {'sell-through':>12}")
    for group, row in table.sort_values("sell_through", ascending=False).iterrows():
        print(f"{group:<28} {int(row['listings']):>8} {int(row['sold']):>5} {row['sell_through']:>12.2f}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Answer the staff questions and score the answers.")
    sub = parser.add_subparsers(dest="command", required=True)
    q = sub.add_parser("questions")
    q.add_argument("--route", choices=["keyword", "knowledge", "both"], default="both")
    q.add_argument("--show", action="store_true")
    sub.add_parser("profile")
    s = sub.add_parser("sales")
    s.add_argument("--by", choices=["department", "material", "range"], default="department")
    args = parser.parse_args(argv)

    load_dotenv()
    setup_logging(os.environ.get("LOG_LEVEL", "WARNING"))
    config = load_config()
    try:
        if args.command == "questions":
            sys.exit(questions(args, config))
        if args.command == "sales":
            sys.exit(sales(args.by, config))
        sys.exit(profile(config))
    except ValueError as err:
        logger.error("%s", err)
        sys.exit(1)


if __name__ == "__main__":
    main()
