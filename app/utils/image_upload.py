import httpx
from app.config import settings


async def download_twilio_image(media_url: str) -> bytes:
    """
    Downloads an image from Twilio's media URL.
    Twilio requires Basic Auth with Account SID + Auth Token.
    Returns raw image bytes.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            media_url,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            follow_redirects=True,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.content