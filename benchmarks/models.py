"""Shared types for benchmark data."""

from typing import TypedDict


class Item(TypedDict):
    id: int
    title: str
    url: str
    summary: str
    category: str
    featured: bool
    author: str
    tags: list[str]
    comments: int
    thumbnail: str
    external: bool
    draft: bool
    rating: int
