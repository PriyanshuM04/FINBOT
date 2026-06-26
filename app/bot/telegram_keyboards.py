from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def yes_no_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, save it", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ No, correct it", callback_data="confirm_no"),
        ]
    ])


def category_keyboard() -> InlineKeyboardMarkup:
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


def confirm_clear_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗑️ Yes, clear everything", callback_data="clear_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="clear_cancel"),
        ]
    ])