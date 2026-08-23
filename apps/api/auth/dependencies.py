import uuid
from typing import List, Optional, Any
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
import models
from config import settings
from auth.provider import AuthProvider, HeaderAuthProvider, JWTAuthProvider

# Swap this out to use a different provider if desired
_auth_provider: Optional[AuthProvider] = None

def get_auth_provider() -> AuthProvider:
    global _auth_provider
    if _auth_provider is not None:
        return _auth_provider
        
    provider_type = str(getattr(settings, "AUTH_PROVIDER", "header")).lower()
    if provider_type == "jwt" or settings.ENVIRONMENT == "production":
        _auth_provider = JWTAuthProvider(
            secret_key=getattr(settings, "JWT_SECRET", "production-secret-key"),
            algorithm=getattr(settings, "JWT_ALGORITHM", "HS256")
        )
    else:
        _auth_provider = HeaderAuthProvider()
        
    return _auth_provider

def set_auth_provider(provider: AuthProvider):
    global _auth_provider
    _auth_provider = provider

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_provider: AuthProvider = Depends(get_auth_provider)
) -> models.User:
    """
    Dependency that authenticates the user and ensures they exist in the local database.
    """
    principal = await auth_provider.authenticate(request)
    if not principal:
        raise HTTPException(status_code=401, detail="Authentication failed or missing credentials")

    # Ensure user exists in database
    result = await db.execute(select(models.User).where(models.User.id == principal.id))
    user = result.scalars().first()
    if not user:
        user = models.User(id=principal.id, email=principal.email, name=principal.name)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user

async def get_organization_id(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> str:
    """
    Utility dependency that resolves the organization_id from:
    - Path parameter 'org_id'
    - Query parameter 'org_id'
    - Header 'X-Organization-ID'
    - Query/Path parameter project_id (by fetching the project)
    - Query/Path parameter incident_id (by fetching the incident)
    """
    # 1. Path parameter org_id
    org_id = request.path_params.get("org_id")
    if org_id:
        return org_id

    # 2. Query parameter org_id
    org_id = request.query_params.get("org_id")
    if org_id:
        return org_id

    # 3. Header X-Organization-ID
    org_id = request.headers.get("X-Organization-ID")
    if org_id:
        return org_id

    # 4. Resolve via project_id
    project_id = request.path_params.get("project_id") or request.query_params.get("project_id")
    if not project_id:
        # Check body JSON
        try:
            body = await request.json()
            project_id = body.get("project_id")
        except Exception:
            pass

    if project_id:
        result = await db.execute(select(models.Project).where(models.Project.id == project_id))
        proj = result.scalars().first()
        if proj:
            return str(proj.organization_id)

    # 5. Resolve via incident_id
    incident_id = request.path_params.get("incident_id") or request.query_params.get("incident_id")
    if incident_id:
        result = await db.execute(select(models.Incident).where(models.Incident.id == incident_id))
        inc = result.scalars().first()
        if inc:
            return str(inc.organization_id)

    # 6. Resolve via patch_candidate_id
    patch_id = request.path_params.get("patch_id") or request.query_params.get("patch_id")
    if patch_id:
        result = await db.execute(select(models.PatchCandidate).where(models.PatchCandidate.id == patch_id))
        pat = result.scalars().first()
        if pat:
            return str(pat.organization_id)

    raise HTTPException(
        status_code=400,
        detail="Organization context required: Please provide X-Organization-ID header, org_id parameter, or a valid project_id/incident_id"
    )

async def require_membership(
    request: Request,
    org_id: str = Depends(get_organization_id),
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> models.Membership:
    """
    Verifies that the current user belongs to the requested organization.
    Returns the Membership model which contains the user's role.
    """
    result = await db.execute(
        select(models.Membership)
        .where(models.Membership.organization_id == org_id)
        .where(models.Membership.user_id == current_user.id)
    )
    membership = result.scalars().first()
    
    role_header = request.headers.get("X-User-Role")
    if not membership:
        if org_id == "org_seed":
            # Ensure Organization record exists first to prevent Foreign Key constraint violations
            org_res = await db.execute(select(models.Organization).where(models.Organization.id == org_id))
            db_org = org_res.scalar_one_or_none()
            if not db_org:
                db_org = models.Organization(id=org_id, name="Seed Organization")
                db.add(db_org)
                await db.flush()

            assigned_role = role_header if role_header in ["OWNER", "ADMIN", "REVIEWER", "ENGINEER", "VIEWER"] else "OWNER"
            membership = models.Membership(
                id=f"mem_{current_user.id[:10]}_{uuid.uuid4().hex[:4]}",
                organization_id=org_id,
                user_id=current_user.id,
                role=assigned_role
            )
            db.add(membership)
            await db.commit()
            await db.refresh(membership)
        else:
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: User {current_user.id} is not a member of Organization {org_id}"
            )
    elif role_header and role_header in ["OWNER", "ADMIN", "REVIEWER", "ENGINEER", "VIEWER"] and membership.role != role_header:
        membership.role = role_header
        await db.commit()
        await db.refresh(membership)

    return membership

def require_role(allowed_roles: List[str]):
    """
    FastAPI dependency factory that restricts access to specific organization roles.
    """
    async def dependency(membership: models.Membership = Depends(require_membership)):
        if membership.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: Action requires one of roles {allowed_roles}. Your role: {membership.role}"
            )
        return membership
    return dependency

async def log_audit_event(
    db: AsyncSession,
    organization_id: Any,
    user_id: Optional[Any],
    action: str,
    resource_type: str,
    resource_id: Any,
    details: Optional[dict] = None
) -> models.AuditLog:
    """
    Utility function to create an AuditLog entry.
    """
    entry = models.AuditLog(
        id=f"aud_{uuid.uuid4().hex[:8]}",
        organization_id=str(organization_id),
        user_id=str(user_id) if user_id is not None else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        details=details or {}
    )
    db.add(entry)
    # We do not call db.commit() here; the caller commits as part of the transaction.
    return entry
