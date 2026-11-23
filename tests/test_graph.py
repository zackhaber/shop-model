"""The shop's knowledge layer as an RDF graph (Session 7, Stage 17). These tests need no server: the graph is built
in memory from the same files and listings that make kg-load uses."""
import pytest
from rdflib import Graph

from shop_model.config import load_config
from shop_model.graph import (add_knowledge, answer, contains, cross_sell, listing_id, load_relationship_questions,
                              save_store)
from shop_model.knowledge import link_listings, load_knowledge, load_listings, load_questions


@pytest.fixture(scope="module")
def inputs():
    kg = load_knowledge()
    listings = link_listings(load_listings(load_config()), kg.products)
    return kg, listings


@pytest.fixture(scope="module")
def graph(inputs):
    return add_knowledge(Graph(), *inputs)


def test_every_listing_gets_a_unique_key(inputs):
    _, listings = inputs
    assert listings.apply(listing_id, axis=1).is_unique


def test_loading_twice_changes_nothing(inputs):
    g = add_knowledge(Graph(), *inputs)
    once = len(g)
    add_knowledge(g, *inputs)
    assert len(g) == once


def test_the_same_graph_always_gives_the_same_store(inputs, tmp_path):
    first = save_store(add_knowledge(Graph(), *inputs), tmp_path / "a.nt")
    second = save_store(add_knowledge(Graph(), *inputs), tmp_path / "b.nt")
    assert first == second


def test_sparql_gives_the_expected_answers(graph):
    for q in load_questions():
        assert answer(graph, q) == set(q["expected"]), q["id"]


def test_sparql_gives_the_expected_relationship_answers(graph):
    for q in load_relationship_questions():
        found = cross_sell(graph, q) if q["kind"] == "cross_sell" else contains(graph, q)
        assert found == set(q["expected"]), q["id"]


def test_the_graph_states_the_release_it_was_built_from(graph):
    from rdflib.namespace import OWL

    from shop_model.graph import RELEASE
    from shop_model.knowledge import load_schema

    assert [str(v) for v in graph.objects(RELEASE, OWL.versionInfo)] == [load_schema()["version"]]
