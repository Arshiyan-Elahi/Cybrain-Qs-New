from typing import Annotated, Generic, TypeVar

from fastapi import Depends, Query
from pydantic import Field

from app.core.config import get_settings
from app.shared.schemas import CamelModel

T = TypeVar("T")


class PageParams:
    """
    Limit/offset paging.

    Unbounded list endpoints are a latent outage: one large tenant is enough to
    time out a request and exhaust memory. `limit` is clamped to a configured
    maximum so a client cannot ask for everything.
    """

    def __init__(
        self,
        limit: Annotated[int | None, Query(ge=1, description="Items per page.")] = None,
        offset: Annotated[int, Query(ge=0, description="Items to skip.")] = 0,
    ) -> None:
        settings = get_settings()
        self.limit = min(limit or settings.default_page_size, settings.max_page_size)
        self.offset = offset


Paging = Annotated[PageParams, Depends()]


class Page(CamelModel, Generic[T]):
    """Envelope carrying the data plus enough state for a client to page."""

    items: list[T]
    total: int = Field(description="Total matching rows, ignoring limit/offset.")
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total
