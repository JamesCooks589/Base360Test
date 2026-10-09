from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Tuple
from zoneinfo import ZoneInfo

CENTS = Decimal("0.01")

def get_month_bounds_utc(year: int, month: int, timezone: str) -> Tuple[datetime, datetime]:
    """
    Returns the [start, end) of a calendar month as UTC datetimes, where the
    month boundaries are midnight in the property's local timezone.

    e.g. March 2024 in Europe/Paris starts at 2024-02-29 23:00 UTC, so a
    check-in at 2024-02-29 23:30 UTC (00:30 local) counts as March revenue.
    """
    tz = ZoneInfo(timezone)
    start_local = datetime(year, month, 1, tzinfo=tz)
    if month < 12:
        end_local = datetime(year, month + 1, 1, tzinfo=tz)
    else:
        end_local = datetime(year + 1, 1, 1, tzinfo=tz)

    # Convert each bound separately so DST offsets are applied correctly
    return start_local.astimezone(dt_timezone.utc), end_local.astimezone(dt_timezone.utc)


class PropertyNotFoundError(Exception):
    """Raised when a property does not exist for the requesting tenant."""


class MixedCurrencyError(Exception):
    """Raised when reservations in different currencies would be summed together."""


async def calculate_total_revenue(
    property_id: str,
    tenant_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Aggregates revenue from database. When month/year are given, only
    reservations checking in during that month (in the property's local
    timezone) are included; otherwise all reservations are included.
    """
    try:
        # Use the shared pool (creating one per request would leak connections)
        from app.core.database_pool import db_pool

        # Initialize pool if needed
        await db_pool.initialize()

        if db_pool.session_factory:
            async with db_pool.get_session() as session:
                # Use SQLAlchemy text for raw SQL
                from sqlalchemy import text

                # Only serve properties that belong to the requesting tenant
                owned = await session.execute(
                    text("SELECT timezone FROM properties WHERE id = :property_id AND tenant_id = :tenant_id"),
                    {"property_id": property_id, "tenant_id": tenant_id},
                )
                property_row = owned.first()
                if property_row is None:
                    raise PropertyNotFoundError(property_id)

                params = {"property_id": property_id, "tenant_id": tenant_id}
                date_filter = ""
                if month is not None and year is not None:
                    # Month boundaries are local to the property, not UTC
                    params["start_date"], params["end_date"] = get_month_bounds_utc(
                        year, month, property_row.timezone
                    )
                    date_filter = "AND check_in_date >= :start_date AND check_in_date < :end_date"

                query = text(f"""
                    SELECT
                        property_id,
                        currency,
                        SUM(total_amount) as total_revenue,
                        COUNT(*) as reservation_count
                    FROM reservations
                    WHERE property_id = :property_id AND tenant_id = :tenant_id
                    {date_filter}
                    GROUP BY property_id, currency
                """)

                result = await session.execute(query, params)
                rows = result.fetchall()

                # Amounts in different currencies cannot be added without FX rates
                if len(rows) > 1:
                    raise MixedCurrencyError(sorted(r.currency for r in rows))
                row = rows[0] if rows else None
                
                if row:
                    # Sum at full (sub-cent) precision in the DB, then round once
                    # to cents. Rounding each booking first would drift by cents
                    # (e.g. 333.333 + 333.333 + 333.334 -> 999.99 vs 1000.00).
                    total_revenue = Decimal(str(row.total_revenue)).quantize(CENTS, rounding=ROUND_HALF_UP)
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": str(total_revenue),
                        "currency": row.currency,
                        "count": row.reservation_count
                    }
                else:
                    # No reservations found for this property
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": "0.00",
                        "currency": "USD",
                        "count": 0
                    }
        else:
            raise Exception("Database pool not available")
            
    except (PropertyNotFoundError, MixedCurrencyError):
        raise
    except Exception as e:
        print(f"Database error for {property_id} (tenant: {tenant_id}): {e}")

        # Never fall back to fabricated figures: fail loudly instead of
        # showing a client numbers that are not theirs or not real.
        raise


async def list_tenant_properties(tenant_id: str) -> List[Dict[str, Any]]:
    """
    Returns the properties owned by a tenant, for the dashboard selector.
    """
    from app.core.database_pool import db_pool
    from sqlalchemy import text

    await db_pool.initialize()
    async with db_pool.get_session() as session:
        result = await session.execute(
            text("SELECT id, name, timezone FROM properties WHERE tenant_id = :tenant_id ORDER BY id"),
            {"tenant_id": tenant_id},
        )
        return [{"id": row.id, "name": row.name, "timezone": row.timezone} for row in result]
