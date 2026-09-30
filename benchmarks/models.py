"""Shared types for benchmark data."""

from typing import TypedDict


class Item(TypedDict):
    title: str
    url: str
    summary: str
    category: str
    featured: bool
    author: str
    tags: list[str]
    comments: int
