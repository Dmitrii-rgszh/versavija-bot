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
    for cat in slice_items:
        text = cat.get('text', 'Категория')
        slug = cat.get('slug') or text
        btn = InlineKeyboardButton(text=text, callback_data=f"pf:{slug}")
        row.append(btn)
        if len(row) == 2:
            rows.append(row)
            row = []
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


def build_category_photo_nav_keyboard(slug: str, idx: int) -> InlineKeyboardMarkup:
    """Keyboard for navigating photos inside a category (random shuffle on each click). idx is current photo index."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️", callback_data=f"pf_pic:{slug}:{idx}"),
            InlineKeyboardButton(text="▶️", callback_data=f"pf_pic:{slug}:{idx}"),
        ],
        [InlineKeyboardButton(text="⬅️ Категории", callback_data="portfolio")]
    ])


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
        rows.append([InlineKeyboardButton(text="Администрирование", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_keyboard(admin_mode_on: Optional[bool] = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Изменить текст приветствия", callback_data="admin_change_text")],
        [InlineKeyboardButton(text="Изменить картинку приветствия", callback_data="admin_change_image")],
        [InlineKeyboardButton(text="Управление меню", callback_data="admin_manage_menu")],
        [InlineKeyboardButton(text="Просмотреть структуру меню", callback_data="view_menu")],
    ]
    if admin_mode_on is not None:
        toggle_text = "👁 Режим администратора: ВЫКЛ (включить)" if not admin_mode_on else "👁 Режим администратора: ВКЛ (выключить)"
        rows.append([InlineKeyboardButton(text=toggle_text, callback_data="toggle_admin_mode")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_menu_edit_kb(menu: list) -> InlineKeyboardMarkup:
    """Build keyboard for editing menu: each button has callback edit_menu:idx and delete_menu:idx"""
    rows = []
    for idx, item in enumerate(menu):
        # use stable per-item identifier (callback field) so actions survive reorders
        ident = item.get('callback') or f'btn{idx}'
        # show text + edit callback button + delete + move up/down
        rows.append([
            InlineKeyboardButton(text=f"✏️ {item.get('text','btn')}", callback_data=f"edit_menu::{ident}"),
            InlineKeyboardButton(text="🔧 callback", callback_data=f"edit_callback::{ident}"),
        ])
        rows.append([
            InlineKeyboardButton(text="️ Удалить", callback_data=f"prompt_delete::{ident}"),
            InlineKeyboardButton(text="⬆️", callback_data=f"move_up::{ident}"),
            InlineKeyboardButton(text="⬇️", callback_data=f"move_down::{ident}"),
        ])
    # controls: add new, back
    rows.append([
        InlineKeyboardButton(text="➕ Добавить кнопку", callback_data="add_menu"),
        InlineKeyboardButton(text="➕ Ручной режим", callback_data="add_menu_manual"),
    ])
    rows.append([
        InlineKeyboardButton(text="Сортировать (дефолты сначала)", callback_data="sort_defaults_first"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_confirm_delete_kb(idx: int) -> InlineKeyboardMarkup:
    # idx may be numeric index or an identifier; caller should pass the same identifier used in prompt
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete::{idx}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")],
    ])


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
        [InlineKeyboardButton(text="💒 Свадебная", callback_data="wedding_packages")],
        [InlineKeyboardButton(text="💋 Lingerie (будуарная)", callback_data="lingerie_service")],
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
