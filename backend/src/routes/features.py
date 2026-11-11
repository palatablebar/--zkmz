"""Feature definition router — write endpoints require the owner role."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import feature_controller
from src.middlewares.rbac import require_owner, require_reader
from src.schemas.feature import FeatureCreate, FeatureUpdate

router = APIRouter(prefix="/features", tags=["features"])


@router.get("")
def list_features(db: Session = Depends(get_db), user=Depends(require_reader)):
    return feature_controller.list_features(db, user)


@router.get("/{feature_id}")
def get_feature(feature_id: int, db: Session = Depends(get_db), user=Depends(require_reader)):
    return feature_controller.get_feature(db, user, feature_id)


@router.post("", status_code=201)
def create_feature(
    payload: FeatureCreate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_owner),
):
    return feature_controller.create_feature(db, user, payload, request)


@router.patch("/{feature_id}")
def patch_feature(
    feature_id: int,
    payload: FeatureUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_owner),
):
    return feature_controller.patch_feature(db, user, feature_id, payload, request)


@router.post("/{feature_id}/publish")
def publish_feature(
    feature_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_owner),
):
    return feature_controller.publish_feature(db, user, feature_id, request)


@router.get("/{feature_id}/versions")
def get_versions(feature_id: int, db: Session = Depends(get_db), user=Depends(require_reader)):
    return feature_controller.get_versions(db, user, feature_id)
