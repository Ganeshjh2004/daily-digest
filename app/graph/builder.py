"""Graph builder and invocation entry point for the Daily Digest pipeline."""

import asyncio
from functools import partial

from langgraph.graph import END, START, StateGraph

from app.graph.edges import after_select, after_validate
from app.graph.nodes import (
    NodeDependencies,
    classify_topics,
    dedupe,
    fetch_feeds,
    load_config,
    parse_entries,
    save_output,
    select_articles,
    summarize,
    validate,
)
from app.graph.state import PipelineState
from app.storage.json_store import read_cache


def build_graph(dependencies: NodeDependencies):
    """Build the required fetch-to-save LangGraph pipeline."""
    graph = StateGraph(PipelineState)
    graph.add_node("load_config", partial(load_config, dependencies=dependencies))
    graph.add_node("fetch_feeds", partial(fetch_feeds, dependencies=dependencies))
    graph.add_node("parse_entries", partial(parse_entries, dependencies=dependencies))
    graph.add_node("dedupe", partial(dedupe, dependencies=dependencies))
    graph.add_node("classify_topics", partial(classify_topics, dependencies=dependencies))
    graph.add_node("select_articles", partial(select_articles, dependencies=dependencies))
    graph.add_node("summarize", partial(summarize, dependencies=dependencies))
    graph.add_node("validate", partial(validate, dependencies=dependencies))
    graph.add_node("save_output", partial(save_output, dependencies=dependencies))
    graph.add_edge(START, "load_config")
    graph.add_edge("load_config", "fetch_feeds")
    graph.add_edge("fetch_feeds", "parse_entries")
    graph.add_edge("parse_entries", "dedupe")
    graph.add_edge("dedupe", "classify_topics")
    graph.add_edge("classify_topics", "select_articles")
    graph.add_conditional_edges(
        "select_articles",
        after_select,
        {"summarize": "summarize", "save_output": "save_output"},
    )
    graph.add_edge("summarize", "validate")
    graph.add_conditional_edges(
        "validate",
        after_validate,
        {"retry": "summarize", "save_output": "save_output"},
    )
    graph.add_edge("save_output", END)
    return graph.compile()


async def run_pipeline(dependencies: NodeDependencies) -> dict:
    """Run one graph invocation with an empty-or-validated persisted cache."""
    cache = await asyncio.to_thread(read_cache, dependencies.data_dir / "cache.json")
    initial: PipelineState = {
        "run_id": "",
        "started_at": "",
        "feeds": [],
        "topic_keywords": {},
        "default_topics": {},
        "raw_items": [],
        "articles": [],
        "selected": [],
        "summaries": [],
        "cache": cache,
        "retry_count": 0,
        "errors": [],
        "metrics": {},
    }
    result = await build_graph(dependencies).ainvoke(initial)
    return dict(result)
