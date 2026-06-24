"""
Inline keyboard layouts for Telegram bot.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def yes_no_keyboard() -> InlineKeyboardMarkup:
    """Yes/No confirmation keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, save it", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ No, correct it", callback_data="confirm_no"),
        ]
    ])


def category_keyboard() -> InlineKeyboardMarkup:
    """Category selection keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🍔 Food", callback_data="cat_food"),
            InlineKeyboardButton("🚗 Travel", callback_data="cat_travel"),
        ],
        [
            InlineKeyboardButton("🛍️ Shopping", callback_data="cat_shopping"),
            InlineKeyboardButton("💊 Health", callback_data="cat_health"),
        ],
        [
            InlineKeyboardButton("💡 Bills", callback_data="cat_bills"),
            InlineKeyboardButton("🎬 Entertainment", callback_data="cat_entertainment"),
        ],
        [
            InlineKeyboardButton("📦 Other", callback_data="cat_other"),
        ],
    ])