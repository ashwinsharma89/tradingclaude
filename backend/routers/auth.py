from fastapi import APIRouter, Query

from config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/upstox/callback")
async def upstox_callback(code: str = Query(...)):
    # Upstox OAuth callback — exchange code for token
    import httpx
    settings = get_settings()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.upstox.com/v2/login/authorization/token",
            data={
                "code": code,
                "client_id": settings.UPSTOX_CLIENT_ID,
                "client_secret": settings.UPSTOX_CLIENT_SECRET,
                "redirect_uri": settings.UPSTOX_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code == 200:
            token_data = resp.json()
            return {"status": "success", "access_token": token_data.get("access_token", "")}
        return {"status": "error", "message": resp.text}


@router.get("/dhan/status")
async def dhan_status():
    """Check if Dhan access token is configured."""
    settings = get_settings()
    has_token = bool(settings.DHAN_ACCESS_TOKEN and settings.DHAN_ACCESS_TOKEN != "your_dhan_access_token")
    return {"authenticated": has_token, "source": "dhan"}
