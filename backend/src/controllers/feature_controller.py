"""Feature definition handlers (wired by app/routes/features.py)."""
from src.middlewares.audit_logger import record
from src.schemas.common import page
from src.services import catalogue_service, feature_service
from src.utils.serialize import feature_out, feature_version_out


def list_features(db, user) -> dict:
    items = [feature_out(feature) for feature in feature_service.list_features(db)]
    return page(items, len(items))


def get_feature(db, user, feature_id: int) -> dict:
    feature = feature_service.get_feature(db, feature_id)
    return {
        "feature": feature_out(feature),
        "versions": [feature_version_out(item) for item in feature_service.versions(db, feature_id)],
        "audits": catalogue_service.list_audits(db, limit=10, feature_id=feature_id),
    }


def create_feature(db, user, payload, request=None) -> dict:
    feature = feature_service.create_feature(db, payload, user)
    record(
        request,
        "feature_create",
        "feature_def",
        feature.id,
        after={"code": feature.code, "boundary_policy": feature.boundary_policy},
    )
    return feature_out(feature)


def patch_feature(db, user, feature_id: int, payload, request=None) -> dict:
    before = feature_out(feature_service.get_feature(db, feature_id))
    feature = feature_service.update_feature(db, feature_id, payload, user)
    after = feature_out(feature)
    record(request, "feature_update", "feature_def", feature.id, before=before, after=after)
    return after


def publish_feature(db, user, feature_id: int, request=None) -> dict:
    feature = feature_service.publish_feature(db, feature_id, user)
    record(
        request,
        "feature_publish",
        "feature_def",
        feature.id,
        after={"code": feature.code, "version": feature.version, "status": feature.status},
    )
    return feature_out(feature)


def get_versions(db, user, feature_id: int) -> dict:
    feature = feature_service.get_feature(db, feature_id)
    return {
        "feature": feature_out(feature),
        "versions": [feature_version_out(item) for item in feature_service.versions(db, feature_id)],
        "audits": catalogue_service.list_audits(db, limit=30, feature_id=feature_id),
    }
