from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from app.models.resource import ResourceCategory, Resource
from app.schemas.resource_schema import (
    ResourceCategoryCreate,
    ResourceCategoryUpdate,
    ResourceCreate,
    ResourceUpdate,
)


def criar_categoria(db: Session, categoria: ResourceCategoryCreate) -> ResourceCategory:
    nova_categoria = ResourceCategory(
        tenant_id=categoria.tenant_id,
        name=categoria.name,
        description=categoria.description,
        type=categoria.type,
        icon=categoria.icon,
        color=categoria.color,
        is_active=categoria.is_active,
        category_metadata=categoria.category_metadata,
    )
    db.add(nova_categoria)
    db.commit()
    db.refresh(nova_categoria)
    return nova_categoria


def listar_categorias(db: Session, tenant_id: Optional[UUID] = None):
    query = db.query(ResourceCategory)
    if tenant_id:
        query = query.filter(ResourceCategory.tenant_id == tenant_id)
    return query.order_by(ResourceCategory.name.asc()).all()


def buscar_categoria(db: Session, categoria_id: UUID) -> Optional[ResourceCategory]:
    return (
        db.query(ResourceCategory)
        .options(joinedload(ResourceCategory.resources))
        .filter(ResourceCategory.id == categoria_id)
        .first()
    )


def atualizar_categoria(
    db: Session, categoria_id: UUID, categoria_update: ResourceCategoryUpdate
) -> Optional[ResourceCategory]:
    categoria = buscar_categoria(db, categoria_id)
    if not categoria:
        return None

    for campo, valor in categoria_update.model_dump(exclude_unset=True).items():
        setattr(categoria, campo, valor)

    db.commit()
    db.refresh(categoria)
    return categoria


def deletar_categoria(db: Session, categoria_id: UUID) -> Optional[ResourceCategory]:
    categoria = buscar_categoria(db, categoria_id)
    if not categoria:
        return None

    db.delete(categoria)
    db.commit()
    return categoria


def criar_recurso(db: Session, recurso: ResourceCreate) -> Resource:
    novo_recurso = Resource(
        tenant_id=recurso.tenant_id,
        category_id=recurso.category_id,
        name=recurso.name,
        description=recurso.description,
        status=recurso.status,
        capacity=recurso.capacity,
        location=recurso.location,
        attributes=recurso.attributes,
        availability_schedule=recurso.availability_schedule,
        image_url=str(recurso.image_url) if recurso.image_url else None,
    )
    db.add(novo_recurso)
    db.commit()
    db.refresh(novo_recurso)
    return novo_recurso


def listar_recursos(
    db: Session,
    tenant_id: Optional[UUID] = None,
    category_id: Optional[UUID] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
):
    query = db.query(Resource).options(joinedload(Resource.category))

    if tenant_id:
        query = query.filter(Resource.tenant_id == tenant_id)
    if category_id:
        query = query.filter(Resource.category_id == category_id)
    if status:
        query = query.filter(Resource.status == status)
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(Resource.name.ilike(like_pattern))

    return query.order_by(Resource.name.asc()).all()


def buscar_recurso(db: Session, recurso_id: UUID) -> Optional[Resource]:
    return (
        db.query(Resource)
        .options(joinedload(Resource.category))
        .filter(Resource.id == recurso_id)
        .first()
    )


def atualizar_recurso(
    db: Session, recurso_id: UUID, recurso_update: ResourceUpdate
) -> Optional[Resource]:
    recurso = buscar_recurso(db, recurso_id)
    if not recurso:
        return None

    update_data = recurso_update.model_dump(exclude_unset=True)
    if "image_url" in update_data and update_data["image_url"] is not None:
        update_data["image_url"] = str(update_data["image_url"])

    for campo, valor in update_data.items():
        setattr(recurso, campo, valor)

    db.commit()
    db.refresh(recurso)
    return recurso


def deletar_recurso(db: Session, recurso_id: UUID, publisher=None) -> Optional[Resource]:
    recurso = buscar_recurso(db, recurso_id)
    if not recurso:
        return None

    # Publicar evento ANTES de deletar para outros serviços reagirem
    if publisher:
        payload = {
            "resource_id": str(recurso_id),
            "tenant_id": str(recurso.tenant_id),
        }
        publisher.publish("resource.deleted", payload)

    db.delete(recurso)
    db.commit()
    return recurso
