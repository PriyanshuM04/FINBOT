from app.bot.commands import handle_text_command


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
    Returns a reply string to send back.
    """

    # Media message (image or PDF)
    if num_media > 0 and media_url:
        if media_type and "pdf" in media_type:
            return "📄 PDF received! Bank statement import coming in Phase 6. Stay tuned."
        elif media_type and ("image" in media_type):
            return "🖼️ Image received! UPI screenshot parsing coming in Phase 2. Stay tuned."
        else:
            return "📎 File received but this type isn't supported yet."

    # Text message
    if body:
        return await handle_text_command(sender=sender, body=body)

    return "🤖 I didn't understand that. Try sending a message like *40 chai* or *report*."