from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, List, Optional
from app.services.cache import get_revenue_summary
from app.services.reservations import PropertyNotFoundError, MixedCurrencyError, list_tenant_properties
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    
    if (month is None) != (year is None):
        raise HTTPException(status_code=422, detail="month and year must be provided together")
    
    # Never fall back to a shared placeholder tenant
    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this user")

    try:
        revenue_data = await get_revenue_summary(property_id, tenant_id, month, year)
    except PropertyNotFoundError:
        raise HTTPException(status_code=404, detail="Property not found")
    except MixedCurrencyError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Reservations span multiple currencies {e.args[0]}; totals cannot be combined",
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Revenue data temporarily unavailable")

    # Return money as an exact decimal string; converting to float would
    # reintroduce binary rounding errors before the client ever sees it.
    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": revenue_data['total'],
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }


@router.get("/dashboard/properties")
async def get_dashboard_properties(
    current_user: dict = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Properties for the current tenant only (replaces the hardcoded frontend list)."""
    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this user")

    try:
        return await list_tenant_properties(tenant_id)
    except Exception:
        raise HTTPException(status_code=503, detail="Property list temporarily unavailable")
