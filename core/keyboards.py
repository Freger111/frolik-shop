"""Кнопки и тексты."""
from __future__ import annotations

from . import config


def money(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " ₽"


WELCOME = (
    "🛍 <b>{shop}</b>\n\n"
    "Цифровые товары с мгновенной выдачей.\n"
    "Оплата по СБП или картой — товар приходит сразу после подтверждения.\n\n"
    "👇 Выберите раздел"
)

HELP = (
    "❓ <b>Как это работает</b>\n\n"
    "<b>1.</b> Откройте каталог и выберите товар.\n"
    "<b>2.</b> Нажмите «Купить» — бот покажет реквизиты и номер заказа.\n"
    "<b>3.</b> Переведите сумму и нажмите «Я оплатил».\n"
    "<b>4.</b> После подтверждения товар придёт в этот чат.\n\n"
    "🎁 <b>Промокод</b> — скидка на следующую покупку (кнопка в меню).\n"
    "👥 <b>Пригласить друга</b> — вы получаете 15% от его покупок на бонусный счёт,\n"
    "бонусами можно оплачивать свои заказы.\n\n"
    "Все покупки хранятся в разделе «Мои покупки»."
)


def main_menu(is_admin: bool = False) -> dict:
    rows = [
        [{"text": "🛍 Каталог", "callback_data": "catalog"}],
        [
            {"text": "📦 Мои покупки", "callback_data": "my"},
            {"text": "🎁 Промокод", "callback_data": "promo"},
        ],
        [
            {"text": "👥 Пригласить друга", "callback_data": "invite"},
            {"text": "❓ Помощь", "callback_data": "help"},
        ],
        [{"text": "🎁 Бесплатный мини-пак", "callback_data": "free"}],
    ]
    if is_admin:
        rows.append([{"text": "⚙️ Админ-панель", "callback_data": "adm"}])
    return {"inline_keyboard": rows}


CATEGORY_ICONS = {
    "Оформление": "🎨",
    "Обложки": "🖼",
    "Звуки": "🔊",
    "Гайды": "📚",
    "Инструменты": "🛠",
    "Наборы": "📦",
    "Разное": "✨",
}


def categories(items: list[dict]) -> dict:
    rows = []
    for item in items:
        name = item["category"]
        icon = CATEGORY_ICONS.get(name, "📁")
        rows.append([{"text": f"{icon} {name} · {item['count']}",
                      "callback_data": f"cat:{name}"}])
    rows.append([{"text": "🔥 Показать всё", "callback_data": "cat_all"}])
    rows.append([{"text": "← Меню", "callback_data": "menu"}])
    return {"inline_keyboard": rows}


def catalog(products: list[dict]) -> dict:
    rows = []
    for p in products:
        left = p.get("left", 0)
        mark = "" if left > 0 else " · нет в наличии"
        rows.append([{"text": f"{p['title']} — {money(p['price'])}{mark}",
                      "callback_data": f"p:{p['id']}"}])
    rows.append([{"text": "🖼 Галерея с фото", "callback_data": "gal"}])
    rows.append([
        {"text": "← Разделы", "callback_data": "catalog"},
        {"text": "◀ Меню", "callback_data": "menu"},
    ])
    return {"inline_keyboard": rows}


def product_card(product: dict) -> dict:
    left = product.get("left", 0)
    rows = []
    if left > 0 and product.get("active"):
        rows.append([{"text": f"💳 Купить за {money(product['price'])}",
                      "callback_data": f"buy:{product['id']}"}])
    else:
        rows.append([{"text": "😔 Нет в наличии", "callback_data": "catalog"}])
    rows.append([{"text": "← Каталог", "callback_data": "catalog"}])
    return {"inline_keyboard": rows}


def pay_manual(order_id: int) -> dict:
    return {"inline_keyboard": [
        [{"text": "✅ Я оплатил(а)", "callback_data": f"paid:{order_id}"}],
        [{"text": "← Отменить", "callback_data": f"cancel:{order_id}"}],
    ]}


def pay_link(url: str, order_id: int) -> dict:
    return {"inline_keyboard": [
        [{"text": "💳 Перейти к оплате", "url": url}],
        [{"text": "← Отменить", "callback_data": f"cancel:{order_id}"}],
    ]}


def admin_confirm(order_id: int) -> dict:
    return {"inline_keyboard": [
        [
            {"text": "✅ Подтвердить", "callback_data": f"admok:{order_id}"},
            {"text": "❌ Отклонить", "callback_data": f"admno:{order_id}"},
        ],
    ]}


def admin_panel() -> dict:
    return {"inline_keyboard": [
        [{"text": "➕ Добавить товар", "callback_data": "adm:add"}],
        [{"text": "📥 Пополнить склад", "callback_data": "adm:topup"}],
        [
            {"text": "🖼 Фото товаров", "callback_data": "adm:photos"},
            {"text": "🧾 Заказы", "callback_data": "adm:orders"},
        ],
        [{"text": "📊 Статистика", "callback_data": "adm:stats"}],
        [{"text": "← Меню", "callback_data": "menu"}],
    ]}


def products_picker(products: list[dict], prefix: str) -> dict:
    rows = [[{"text": f"{p['title']} · {p.get('left', 0)} шт.",
              "callback_data": f"{prefix}:{p['id']}"}] for p in products]
    rows.append([{"text": "← Назад", "callback_data": "adm"}])
    return {"inline_keyboard": rows}


def back(callback: str = "menu", label: str = "← Меню") -> dict:
    return {"inline_keyboard": [[{"text": label, "callback_data": callback}]]}
