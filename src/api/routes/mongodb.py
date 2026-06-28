"""Routes backed by MongoDB document collections."""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from src.db.mongodb_client import mongo_client

router = APIRouter(tags=["mongodb"])


@router.get("/products/{product_id}/reviews")
def product_reviews(product_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Reviews for a product, newest helpful first."""
    collection = mongo_client.get_collection("reviews")
    return list(
        collection.find({"product_id": product_id}, {"_id": 0})
        .sort("helpful_votes", -1)
        .limit(limit)
    )


@router.get("/products/{product_id}/specs")
def product_specs(product_id: str) -> Dict[str, Any]:
    """Specifications for a product."""
    doc = mongo_client.get_collection("product_specs").find_one(
        {"product_id": product_id}, {"_id": 0}
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Specs not found")
    return doc


@router.get("/sellers/{seller_id}/profile")
def seller_profile(seller_id: str) -> Dict[str, Any]:
    """Rich profile for a seller."""
    doc = mongo_client.get_collection("seller_profiles").find_one(
        {"seller_id": seller_id}, {"_id": 0}
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return doc


@router.get("/users/{user_id}/preferences")
def user_preferences(user_id: str) -> Dict[str, Any]:
    """Stored preferences for a user."""
    doc = mongo_client.get_collection("user_preferences").find_one(
        {"user_id": user_id}, {"_id": 0}
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Preferences not found")
    return doc
