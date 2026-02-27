import aiosqlite
from fastapi import APIRouter

from database import DB_PATH
from models.schemas import AlertCreate, AlertResponse

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.post("")
async def create_alert(alert: AlertCreate):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO alerts (watchlist_id, alert_type, threshold) VALUES (?, ?, ?)",
            (alert.watchlist_id, alert.alert_type, alert.threshold),
        )
        await db.commit()
        return {"id": cursor.lastrowid}


@router.get("")
async def list_alerts():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT a.*, w.name as ratio_name
            FROM alerts a
            JOIN watchlist w ON a.watchlist_id = w.id
            ORDER BY a.created_at DESC
        """)
        rows = await cursor.fetchall()

    return [
        AlertResponse(
            id=row["id"],
            watchlist_id=row["watchlist_id"],
            ratio_name=row["ratio_name"],
            alert_type=row["alert_type"],
            threshold=row["threshold"],
            triggered=bool(row["triggered"]),
            created_at=str(row["created_at"]),
        )
        for row in rows
    ]


@router.delete("/{alert_id}")
async def delete_alert(alert_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        await db.commit()
    return {"deleted": alert_id}
