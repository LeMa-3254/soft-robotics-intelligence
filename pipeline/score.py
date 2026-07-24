from __future__ import annotations

import json
from typing import Any

from models import Item
from pipeline.model_clients import add_token_usage, build_anthropic_client, read_prompt
from sources.base import vocabulary_match


def score_item(
    item: Item,
    config: dict[str, Any],
    *,
    model_client: Any | None = None,
    token_usage: dict[str, Any] | None = None,
) -> Item:
    client = model_client if model_client is not None else build_anthropic_client()
    if client is not None:
        try:
            return score_item_with_model(item, config, client=client, token_usage=token_usage)
        except Exception as exc:
            bootstrap_score_item(item, config)
            item.score_reason = f"Model scoring failed; bootstrap fallback used: {exc}"
            return item
    return bootstrap_score_item(item, config)


def score_item_with_model(
    item: Item,
    config: dict[str, Any],
    *,
    client: Any,
    token_usage: dict[str, Any] | None = None,
) -> Item:
    scoring = config.get("scoring", {})
    prompt = read_prompt(scoring.get("rubric_prompt", "prompts/relevance.md"))
    result, usage = client.complete_json(
        model=scoring["model"],
        system_prompt=prompt,
        user_prompt=json.dumps(item_payload(item), indent=2, sort_keys=True),
        max_tokens=512,
    )
    add_token_usage(token_usage, "anthropic_scoring", usage)
    apply_score_result(item, config, result)
    return item


TIER_POINTS = {"A": 15, "B": 8, "C": 0, "D": -15}


def bootstrap_score_item(item: Item, config: dict[str, Any]) -> Item:
    """Keyword/tier heuristic on the 0–100 scale, used only when no model is available."""
    scoring = config.get("scoring", {})
    text = f"{item.title} {item.abstract or ''}".lower()
    boost_terms = [term.lower() for term in config.get("targeting", {}).get("materials_boost_terms", [])]
    base = 60 if vocabulary_match(item, config) else 25
    boost = 15 if any(term in text for term in boost_terms) else 0
    tier = TIER_POINTS.get(item.tier, 0)

    item.relevance_score = float(max(0, min(100, base + boost + tier)))
    item.quality_score = float(max(0, min(100, 55 + tier)))
    item.score_reason = "Keyword/tier bootstrap score (0–100); replace with configured model scoring."
    item.theme = infer_theme(item)
    item.status = "included" if item.relevance_score >= scoring.get("min_score", 70) else "dropped_lowscore"
    return item


def apply_score_result(item: Item, config: dict[str, Any], result: dict[str, Any]) -> None:
    # Trust the model's rubric judgment directly (0–100); no tier/polymer priors are added here,
    # so a "not really polymer" verdict cannot be inflated past the threshold.
    scoring = config.get("scoring", {})
    item.relevance_score = clamp_score(result.get("relevance"))
    item.quality_score = clamp_score(result.get("quality"))
    item.score_reason = str(result.get("reason") or "Model scored relevance and quality.")
    item.theme = str(result.get("theme") or infer_theme(item))
    item.status = "included" if item.relevance_score >= scoring.get("min_score", 70) else "dropped_lowscore"


def clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 0.0
    return max(0.0, min(100.0, score))


def item_payload(item: Item) -> dict[str, Any]:
    return {
        "title": item.title,
        "url": item.url,
        "source_type": item.source_type,
        "source_name": item.source_name,
        "tier": item.tier,
        "authors": item.authors,
        "published_date": item.published_date,
        "abstract": item.abstract,
        "doi": item.doi,
    }


def infer_theme(item: Item) -> str:
    """Map to the fixed theme taxonomy (mirrors targeting.themes / the relevance rubric)."""
    text = f"{item.title} {item.abstract or ''}".lower()
    if any(term in text for term in ("humanoid", "bipedal", "legged robot", "optimus", "atlas", "figure ai", "quadruped")):
        return "Humanoid Robotics"
    if any(term in text for term in ("tactile", "electronic skin", "e-skin", "robot skin", "piezoresistive", "stretchable sensor", "sensing")):
        return "Soft Skin & Tactile Sensing"
    if any(term in text for term in ("self-healing", "durability", "fatigue", "cyclic", "dynamic covalent", "vitrimer")):
        return "Durability & Self-Healing"
    if any(term in text for term in ("3d printing", "direct ink writing", "additive manufacturing", "molding", "fabrication", "manufactur")):
        return "Fabrication & Manufacturing"
    if any(term in text for term in ("safety", "compliant", "variable stiffness", "human-robot", "hri", "collaborative", "impact absorption")):
        return "HRI & Safety"
    if any(term in text for term in ("prosthetic", "prosthesis", "exoskeleton", "rehabilitation", "surgical", "medical", "agricultural", "industrial arm")):
        return "Applications"
    if any(term in text for term in ("actuator", "artificial muscle", "dielectric elastomer", "shape memory", "hydrogel", "liquid crystal elastomer", "pneumatic")):
        return "Actuator Materials"
    if any(term in text for term in ("soft robot", "soft robotic", "biomimetic", "bio-inspired", "compliant mechanism")):
        return "Soft Robotics Research"
    return "Other"
