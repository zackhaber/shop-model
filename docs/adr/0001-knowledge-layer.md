# ADR 0001: Add a knowledge layer for the shop's products

- Status: accepted
- Date: 2026-11-20
- Deciders: the shop's owner, the data team
- Session: ARI3217 Session 7, Stage 16

## Context

Staff want to ask an assistant questions about what the shop sells and what sold. The listings
(data/prices_v2.csv and data/holdout.csv) hold a date, a description, a price and whether the item
sold. They do not say what a product is: there is no category, no range and no identifier. 680
listings describe 52 products, and the same product is listed up to 27 times.

Asked through the listings alone, the staff questions go wrong (shop-ask questions --route keyword):

- "kitchen" finds one product, the cookbook, and misses all 14 kitchen and dining products sold under 25 euro;
- "premium" finds nothing, because no listing says which products form the premium range;
- "candle" finds a brass candle holder, which is not a candle, and misses the reed diffuser;
- "wood" finds the olive wood servers and the wooden board, and misses the oak and walnut products;
- "travel" finds nothing, although the shop sells a weekender bag and a water bottle for travel.

Every check from Sessions 5 and 6 passes on this data. The problem is meaning, not quality.

## Options considered

1. Do nothing, and improve the assistant's prompt. Rejected: a prompt cannot supply facts the
   listings do not hold, such as which products are premium.
2. Add category and range columns to the listings. Cheapest, and enough for the kitchen, premium and
   candles questions. Rejected: one column holds one category, so the water bottle could not be both an
   outdoor and a travel product; a material column says "oak" and nothing about wood; every listing
   repeats what belongs to the product; and a second source of listings would need the same columns.
3. A metrics layer (the business-intelligence sense of "semantic layer"): define measures such as
   sell-through rate once. Useful, but it defines numbers, not what a product is.
4. A product knowledge layer: products, their categories, materials and ranges, the two hierarchies
   (categories and materials) and the shop's vocabulary as data of their own, with listings linked to
   products. Chosen.

## Decision

Keep the shop's product knowledge in kg/ as a versioned release of reviewed files, written against an explicit
schema (kg/schema.yaml): products and gift sets, their categories, materials and ranges, the two hierarchies, the
rules for complements between categories, and the vocabulary. Release v1.0 is the Christmas 2026 catalogue. From
Stage 17 build it into an RDF graph, using the W3C standards (RDF, SKOS, SPARQL), that the
assistant and the model can both query.
Listings stay where they are; the knowledge layer links to them.

## Consequences

- Every new product needs a row in kg/products.csv before its listings can be linked; a test fails
  otherwise. Products can be catalogued before they are listed.
- Complements are stated once, between categories, so a new product receives them when it is placed in a
  category; a wrong rule is wrong for every product it covers.
- Someone must own the taxonomy, the materials and the vocabulary, and review changes to them. Some
  changes are decisions about meaning, not corrections: bamboo is recorded as a plant fibre, not a wood,
  so the bamboo coasters are not a wooden product.
- One more artefact to build, version and check: the graph is derived from the files and must be rebuilt
  whenever they change.
- The answers are only as good as the vocabulary: a staff word that is not in kg/synonyms.yaml finds
  nothing on the knowledge route.
- Revisit this decision if the knowledge files stay this small and no second source of listings
  appears: option 2 would then be enough. Revisit it in the other direction if the shop opens a second
  outlet, imports products from other suppliers, or opens an online shop: each makes the case stronger.
