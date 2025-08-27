from bot import build_main_keyboard

kb = build_main_keyboard(is_admin=True)
print(type(kb))
print(kb)
print('inline_keyboard attr:', getattr(kb, 'inline_keyboard', None))
