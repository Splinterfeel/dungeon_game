import names
from pydantic import Field
from src.entities.base import Actor


class Enemy(Actor):
    name: str = Field(default_factory=lambda: f"[e]{names.get_full_name()}")
