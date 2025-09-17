from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional

ADMIN_USERNAMES = {"versavija", "dmitrii_poliakov"}


def build_portfolio_keyboard(categories: list, page: int = 0, page_size: int = 6, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Build paginated keyboard for portfolio categories.

    categories: list[{text, slug}]
    page: zero-based page index
    page_size: number of items per page
    """
    total = len(categories)
    if page_size <= 0:
        page_size = 6
    max_page = 0 if total == 0 else (total - 1) // page_size
    if page < 0:
        page = 0
    if page > max_page:
        page = max_page
    start = page * page_size
    end = start + page_size
    slice_items = categories[start:end]

    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    
    # Define long category texts that should be placed alone in row
    LONG_CATEGORIES = [
        "Репортажная (банкеты, мероприятия)",
        "Lingerie (будуарная)",
        "Детская (школы/садики)",
        "Мама с ребёнком",
    ]
    
    for cat in slice_items:
        text = cat.get('text', 'Категория')
        slug = cat.get('slug') or text
        btn = InlineKeyboardButton(text=text, callback_data=f"pf:{slug}")
        
        # Check if this is a long category that should be alone
        is_long_category = any(long_cat in text for long_cat in LONG_CATEGORIES)
        
        if is_long_category:
            # If current row has items, close it first
            if row:
                rows.append(row)
                row = []
            # Add long category alone in its row
            rows.append([btn])
        else:
            # Add to current row
            row.append(btn)
            if len(row) == 2:
                rows.append(row)
                row = []
    
    # Add remaining buttons in row if any
    if row:
        rows.append(row)

    # navigation row (only if more than one page)
    if max_page > 0:
        prev_page = page - 1 if page > 0 else max_page
        next_page = page + 1 if page < max_page else 0
        rows.append([
            InlineKeyboardButton(text="◀️", callback_data=f"pf_page:{prev_page}"),
            InlineKeyboardButton(text=f"Стр {page+1}/{max_page+1}", callback_data="pf_page:noop"),
            InlineKeyboardButton(text="▶️", callback_data=f"pf_page:{next_page}"),
        ])

    # admin: add new category button (placed at top or bottom – choose bottom before back)
    if is_admin:
        rows.append([InlineKeyboardButton(text="➕ Новая категория", callback_data="pf_cat_new")])
    # back button to main
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_category_admin_keyboard(slug: str, has_photos: bool) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text="➕ Добавить фото", callback_data=f"pf_add:{slug}")]]
    if has_photos:
        buttons.append([InlineKeyboardButton(text="🗑 Удалить фото", callback_data=f"pf_del:{slug}")])
        buttons.append([InlineKeyboardButton(text="🧹 Очистить все фото", callback_data=f"pf_del_all_confirm:{slug}")])
    # category-level actions
    buttons.append([InlineKeyboardButton(text="✏️ Переименовать категорию", callback_data=f"pf_cat_ren:{slug}")])
    buttons.append([InlineKeyboardButton(text="🗑 Удалить категорию", callback_data=f"pf_cat_del:{slug}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Категории", callback_data="portfolio")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_categories_admin_root_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Новая категория", callback_data="pf_cat_new")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main")],
    ])

def build_category_delete_keyboard(slug: str, photos: list) -> InlineKeyboardMarkup:
    rows = []
    for idx, fid in enumerate(photos):
        rows.append([InlineKeyboardButton(text=f"#{idx+1}", callback_data=f"pf_del_idx:{slug}:{idx}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"pf_back_cat:{slug}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_confirm_delete_all_photos_kb(slug: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить очистку", callback_data=f"pf_del_all_yes:{slug}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"pf_del_all_no:{slug}")]
    ])


def build_category_delete_viewer_keyboard(slug: str, idx: int) -> InlineKeyboardMarkup:
    """Keyboard for browsing photos one-by-one and deleting current.
    pf_delnav:<slug>:<idx>   – navigate (left/right reuse same idx placeholder)
    pf_delcurr:<slug>:<idx>  – delete current index
    pf_del_done:<slug>       – finish deletion mode (back to admin cat)
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️", callback_data=f"pf_delnav:{slug}:{idx}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"pf_delcurr:{slug}:{idx}"),
            InlineKeyboardButton(text="▶️", callback_data=f"pf_delnav:{slug}:{idx}"),
        ],
        [InlineKeyboardButton(text="⬅️ Готово", callback_data=f"pf_del_done:{slug}")]
    ])


def build_confirm_delete_category_kb(slug: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить удаление", callback_data=f"pf_cat_del_yes:{slug}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"pf_cat_del_no:{slug}")],
    ])


def build_undo_category_delete_kb(slug: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Отменить удаление категории", callback_data=f"pf_undo_cat:{slug}")]
    ])


def build_undo_photo_delete_kb(slug: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Восстановить фото", callback_data=f"pf_undo_photo:{slug}")]
    ])


def build_add_photos_in_progress_kb(slug: str, count: int) -> InlineKeyboardMarkup:  # deprecated, kept for backward compatibility
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"✅ Добавлено {count}", callback_data="noop")]])


def build_category_photo_nav_keyboard(slug: str, idx: int, user_id: int = None, likes_count: int = 0, user_has_liked: bool = False) -> InlineKeyboardMarkup:
    """Keyboard for navigating photos inside a category (random shuffle on each click). idx is current photo index."""
    buttons = []
    
    # Navigation row with like button in the middle
    if user_id is not None:
        # Always show red heart, regardless of like status
        like_text = f"❤️ {likes_count}"
        buttons.append([
            InlineKeyboardButton(text="◀️", callback_data=f"pf_pic:{slug}:{idx}"),
            InlineKeyboardButton(text=like_text, callback_data=f"like:{slug}:{idx}"),
            InlineKeyboardButton(text="▶️", callback_data=f"pf_pic:{slug}:{idx}"),
        ])
    else:
        # Navigation row without like button
        buttons.append([
            InlineKeyboardButton(text="◀️", callback_data=f"pf_pic:{slug}:{idx}"),
            InlineKeyboardButton(text="▶️", callback_data=f"pf_pic:{slug}:{idx}"),
        ])
    
    # Back button row
    buttons.append([InlineKeyboardButton(text="⬅️ Категории", callback_data="portfolio")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_main_keyboard_from_menu(menu: list, is_admin: bool) -> InlineKeyboardMarkup:
    """Build InlineKeyboardMarkup from a menu list. menu = [{'text': str, 'callback': str}, ...]"""
    rows = []
    # place buttons two per row
    row = []
    for item in menu:
        btn = InlineKeyboardButton(text=item.get('text', 'button'), callback_data=item.get('callback',''))
        row.append(btn)
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if is_admin:
        rows.append([InlineKeyboardButton(text="🔧 Администрирование", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_keyboard(admin_mode_on: Optional[bool] = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📢 Рассылка сообщений", callback_data="admin_broadcast")],
    ]
    if admin_mode_on is not None:
        toggle_text = "👁 Режим администратора: ВЫКЛ (включить)" if not admin_mode_on else "👁 Режим администратора: ВКЛ (выключить)"
        rows.append([InlineKeyboardButton(text=toggle_text, callback_data="toggle_admin_mode")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_social_admin_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для управления соцсетями"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать текст", callback_data="social_edit")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main")],
    ])


def build_reviews_nav_keyboard(photo_idx: int) -> InlineKeyboardMarkup:
    """Клавиатура навигации для отзывов"""
    buttons = []
    # Navigation arrows
    nav_row = []
    nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"reviews_pic:{photo_idx}"))
    nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"reviews_pic:{photo_idx}"))
    buttons.append(nav_row)
    
    # Back to main
    buttons.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_reviews_admin_keyboard() -> InlineKeyboardMarkup:
    """Админ клавиатура для управления отзывами"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить отзыв", callback_data="reviews_add")],
        [InlineKeyboardButton(text="🗑 Удалить отзыв", callback_data="reviews_del")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main")],
    ])


def build_reviews_delete_keyboard(reviews: list) -> InlineKeyboardMarkup:
    """Клавиатура для выбора отзыва для удаления"""
    rows = []
    for idx, fid in enumerate(reviews):
        rows.append([InlineKeyboardButton(text=f"#{idx+1}", callback_data=f"reviews_del_idx:{idx}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="reviews")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_services_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for services menu."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="� Свадебная", callback_data="wedding_packages")],
        [InlineKeyboardButton(text="💋 Lingerie (будуарная)", callback_data="lingerie_service")],
        [InlineKeyboardButton(text="📸 Репортажная", callback_data="reportage_service")],
        [InlineKeyboardButton(text="👤 Индивидуальная", callback_data="individual_service")],
        [InlineKeyboardButton(text="👩‍👶 Мама и ребенок", callback_data="mom_child_service")],
        [InlineKeyboardButton(text="💕 Love Story", callback_data="love_story_service")],
        [InlineKeyboardButton(text="👨‍👩‍👧‍👦 Семейная", callback_data="family_service")],
        [InlineKeyboardButton(text="🧒 Детская (садики/школы)", callback_data="children_service")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu")]
    ])


def build_wedding_packages_nav_keyboard(package_idx: int) -> InlineKeyboardMarkup:
    """Build navigation keyboard for wedding packages."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️", callback_data=f"wedding_pkg_prev:{package_idx}"),
            InlineKeyboardButton(text="▶️", callback_data=f"wedding_pkg_next:{package_idx}"),
        ],
        [InlineKeyboardButton(text="⬅️ Услуги", callback_data="services")]
    ])


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for broadcast confirmation."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, отправить", callback_data="broadcast_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")
        ]
    ])


def build_promotions_keyboard(promotion_idx: int = 0, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Build navigation keyboard for promotions."""
    buttons = []
    
    # Navigation buttons if more than one promotion
    if promotion_idx >= 0:  # We assume there's at least one promotion
        nav_row = [
            InlineKeyboardButton(text="◀️", callback_data=f"promo_prev:{promotion_idx}"),
            InlineKeyboardButton(text="▶️", callback_data=f"promo_next:{promotion_idx}"),
        ]
        buttons.append(nav_row)
    
    # Admin buttons
    if is_admin:
        buttons.append([InlineKeyboardButton(text="➕ Добавить акцию", callback_data="add_promotion")])
        buttons.append([InlineKeyboardButton(text="🗑 Удалить эту акцию", callback_data=f"delete_promotion:{promotion_idx}")])
    
    # Back button
    buttons.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_add_promotion_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for adding promotions (admin only)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить акцию", callback_data="add_promotion")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu")]
    ])


def build_promotion_image_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for promotion image selection."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Без фото", callback_data="promo_no_image")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="promotions")]
    ])


def build_broadcast_image_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for broadcast image selection."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Без фото", callback_data="broadcast_no_image")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")]
    ])


def build_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for broadcast confirmation."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")]
    ])


def build_promotion_date_keyboard(year: int, month: int, action_prefix: str) -> InlineKeyboardMarkup:
    """Build calendar keyboard for promotion date selection."""
    import calendar
    from datetime import datetime
    
    # Get calendar for the month
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]
    
    buttons = []
    
    # Header with month/year
    buttons.append([InlineKeyboardButton(text=f"{month_name} {year}", callback_data="ignore")])
    
    # Week days header
    buttons.append([
        InlineKeyboardButton(text="Пн", callback_data="ignore"),
        InlineKeyboardButton(text="Вт", callback_data="ignore"),
        InlineKeyboardButton(text="Ср", callback_data="ignore"),
        InlineKeyboardButton(text="Чт", callback_data="ignore"),
        InlineKeyboardButton(text="Пт", callback_data="ignore"),
        InlineKeyboardButton(text="Сб", callback_data="ignore"),
        InlineKeyboardButton(text="Вс", callback_data="ignore"),
    ])
    
    # Calendar days
    today = datetime.now()
    for week in cal:
        week_buttons = []
        for day in week:
            if day == 0:
                week_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                # Don't allow past dates
                date_obj = datetime(year, month, day)
                if date_obj < today.replace(hour=0, minute=0, second=0, microsecond=0):
                    week_buttons.append(InlineKeyboardButton(text=str(day), callback_data="ignore"))
                else:
                    week_buttons.append(InlineKeyboardButton(
                        text=str(day), 
                        callback_data=f"{action_prefix}:{year}-{month:02d}-{day:02d}"
                    ))
        buttons.append(week_buttons)
    
    # Navigation buttons
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    buttons.append([
        InlineKeyboardButton(text="◀️", callback_data=f"{action_prefix}_cal:{prev_year}-{prev_month:02d}"),
        InlineKeyboardButton(text="▶️", callback_data=f"{action_prefix}_cal:{next_year}-{next_month:02d}")
    ])
    
    # Cancel button
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="promotions")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
