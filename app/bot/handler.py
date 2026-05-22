from app.bot.commands import handle_text_command, handle_image_command


async def handle_message(
    sender: str,
    body: str,
    num_media: int,
    media_url: str | None,
    media_type: str | None,
) -> str:
    """
    Entry point for every incoming WhatsApp message.
    Routes to the right handler based on message type.
    """

    # Image message
    if num_media > 0 and media_url:
        if media_type and "pdf" in media_type:
            return "📄 PDF received! Bank statement import coming in Phase 6."

        if media_type and "image" in media_type:
            return await handle_image_command(
                sender=sender,
                media_url=media_url,
            )

        return "📎 File type not supported yet. Send a UPI screenshot or PDF."

    # Text message
    if body:
        return await handle_text_command(sender=sender, body=body)

    return "🤖 Didn't understand that. Try *40 chai* or forward a UPI screenshot."