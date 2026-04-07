"""
Unit routes.

A **Train** is a gas turbine generator train at a plant site (e.g. "1-1 Train" at Moss Landing).
It is the outage-planning grouping; one Train contains multiple Equipment items.
Trains are identified by id and outageId.

Routes:
  GET /api/units  — list all trains, with optional outage-type filter + text search
"""

from fastapi import APIRouter, Query

from data_service.services.train_service import get_trains

router = APIRouter(prefix="/dataservices/api/v1", tags=["units"])


@router.get("/units")
async def get_units(
    search: str = Query(default=""),
    filter_type: str = Query(default="all", alias="filter_type"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> dict[str, object]:
    """
    Return all train configurations (with nested equipment).

    Optional query params:
      filter_type  — one of "all" (default) | "Major" | "Minor"  (outage type)
      search       — case-insensitive substring match on trainName, site, outageId,
                     or any nested equipment serialNumber / equipmentCode
      page         — 1-based page number (default 1)
      page_size    — number of trains per page (default 25, max 100)
    """
    trains = await get_trains(
        page=page,
        page_size=page_size,
        search=search,
        filter_type=filter_type,
    )

    return {"units": trains, "page": page, "page_size": page_size}
