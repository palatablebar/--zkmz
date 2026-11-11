"""Catalogue / overview / meta handlers (wired by app/routes/catalogue.py)."""
from src.services import catalogue_service


def list_label_sets(db, user) -> dict:
    items = catalogue_service.list_label_sets(db)
    return {"items": items, "total": len(items)}


def list_events(db, user, limit: int = 60, offset: int = 0, event_type: str | None = None) -> dict:
    return catalogue_service.list_events(
        db, limit=min(max(limit, 1), 300), offset=max(offset, 0), event_type=event_type
    )


def list_audits(db, user, limit: int = 30, feature_id: int | None = None) -> dict:
    items = catalogue_service.list_audits(db, limit=min(max(limit, 1), 100), feature_id=feature_id)
    return {"items": items, "total": len(items)}


def overview(db, user) -> dict:
    return catalogue_service.overview(db)


def meta(db) -> dict:
    return catalogue_service.meta(db)
