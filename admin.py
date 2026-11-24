"""Управление магазином из консоли — чтобы добавлять товары без кнопок.

Примеры:
    python admin.py add "Ключ на 30 дней" 500 --desc "Доступ в закрытый чат" --items "KEY-1,KEY-2"
    python admin.py stock 1 "KEY-3,KEY-4"
    python admin.py price 1 700
    python admin.py list
    python admin.py orders
    python admin.py stats
    python admin.py confirm 5
    python admin.py reject 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import config, keyboards as kb  # noqa: E402
from core.storage import STATUS_AWAITING, STATUS_NO_STOCK, STATUS_PAID, Storage  # noqa: E402


def split_items(raw: str) -> list[str]:
    if not raw:
        return []
    if "\n" in raw:
        parts = raw.splitlines()
    else:
        parts = raw.split(",")
    return [p.strip() for p in parts if p.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Управление Frolik Shop")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="добавить товар")
    add.add_argument("title")
    add.add_argument("price", type=int)
    add.add_argument("--desc", default="")
    add.add_argument("--items", default="", help="позиции склада через запятую или с новой строки")
    add.add_argument("--cat", default="Разное", help="раздел: Оформление, Обложки, Звуки, Гайды, Наборы")

    cat = sub.add_parser("cat", help="сменить раздел товара")
    cat.add_argument("product_id", type=int)
    cat.add_argument("category")

    photo = sub.add_parser("photo", help="задать фото товара файлом")
    photo.add_argument("product_id", type=int)
    photo.add_argument("path", help="путь к картинке, например assets/preview_pack.jpg")

    stock = sub.add_parser("stock", help="пополнить склад")
    stock.add_argument("product_id", type=int)
    stock.add_argument("items")

    price = sub.add_parser("price", help="изменить цену")
    price.add_argument("product_id", type=int)
    price.add_argument("value", type=int)

    sub.add_parser("list", help="список товаров")
    sub.add_parser("orders", help="последние заказы")
    sub.add_parser("stats", help="статистика")

    hide = sub.add_parser("hide", help="скрыть товар из каталога")
    hide.add_argument("product_id", type=int)
    show = sub.add_parser("show", help="вернуть товар в каталог")
    show.add_argument("product_id", type=int)

    promo = sub.add_parser("promo", help="создать промокод")
    promo.add_argument("code")
    promo.add_argument("percent", type=int)
    promo.add_argument("--max", dest="max_uses", type=int, default=0,
                       help="сколько раз можно активировать (0 — без ограничения)")
    sub.add_parser("promos", help="список промокодов")
    sub.add_parser("refs", help="топ приглашающих")
    sub.add_parser("sources", help="источники трафика")

    confirm = sub.add_parser("confirm", help="подтвердить оплату и выдать")
    confirm.add_argument("order_id", type=int)
    reject = sub.add_parser("reject", help="отклонить заказ")
    reject.add_argument("order_id", type=int)

    args = parser.parse_args()
    db = Storage(config.DB_PATH)

    if args.cmd == "add":
        if args.price <= 0:
            print("Цена должна быть больше нуля")
            return 1
        pid = db.add_product(args.title, args.desc, args.price, category=args.cat)
        items = split_items(args.items)
        if items:
            db.add_stock(pid, items)
        print(f"Товар #{pid} «{args.title}» добавлен за {kb.money(args.price)} "
              f"в раздел «{args.cat}», на складе {db.stock_left(pid)} шт.")

    elif args.cmd == "stock":
        items = split_items(args.items)
        if not items:
            print("Нет позиций")
            return 1
        db.add_stock(args.product_id, items)
        print(f"Добавлено {len(items)} шт. Всего на складе: {db.stock_left(args.product_id)}")

    elif args.cmd == "price":
        db.set_price(args.product_id, args.value)
        print(f"Цена товара #{args.product_id} — {kb.money(args.value)}")

    elif args.cmd == "cat":
        with db.lock:
            db.db.execute("UPDATE products SET category = ? WHERE id = ?",
                          (args.category, args.product_id))
            db.db.commit()
        print(f"Товар #{args.product_id} → раздел «{args.category}»")

    elif args.cmd == "photo":
        path = Path(args.path)
        if not path.exists():
            print("файл не найден:", path)
            return 1
        db.set_photo(args.product_id, f"file:{path.as_posix()}")
        print(f"Фото товара #{args.product_id}: {path.name}")

    elif args.cmd == "list":
        products = db.products(active_only=False)
        if not products:
            print("Товаров нет")
        for p in products:
            print(f"#{p['id']:<3} {p['title'][:34]:36} {kb.money(p['price']):>9}  "
                  f"{p['category'][:14]:15} осталось {p['left']}")

    elif args.cmd == "orders":
        labels = {"pending": "ждёт оплаты", "awaiting": "ждут проверки", "paid": "выдан",
                  "paid_no_stock": "нет на складе", "canceled": "отменён"}
        for r in db.recent_orders(20):
            print(f"#{r['id']:<4} {r['title'] or '—':30} {kb.money(r['price']):>10}  "
                  f"{labels.get(r['status'], r['status']):15} user {r['user_id']}")

    elif args.cmd == "stats":
        s = db.stats()
        print(f"Товаров: {s['products']} · на складе {s['stock']} шт.")
        print(f"Продаж: {s['orders']} на {kb.money(s['revenue'])}")
        print(f"За сутки: {s['today_orders']} на {kb.money(s['today_revenue'])}")
        print(f"Ждут подтверждения: {s['awaiting']} · покупателей: {s['buyers']}")

    elif args.cmd == "hide":
        db.set_active(args.product_id, False)
        print(f"Товар #{args.product_id} скрыт из каталога")

    elif args.cmd == "show":
        db.set_active(args.product_id, True)
        print(f"Товар #{args.product_id} снова в каталоге")

    elif args.cmd == "promo":
        if not (0 < args.percent <= 90):
            print("Скидка должна быть от 1 до 90%")
            return 1
        db.add_promo(args.code, args.percent, args.max_uses)
        limit = f"до {args.max_uses} активаций" if args.max_uses else "без ограничения"
        print(f"Промокод {args.code.upper()} — скидка {args.percent}%, {limit}")

    elif args.cmd == "promos":
        rows = db.promos()
        if not rows:
            print("Промокодов нет")
        for p in rows:
            used = f"{p['used']}/{p['max_uses']}" if p["max_uses"] else f"{p['used']}/∞"
            print(f"{p['code']:14} −{p['percent']:>2}%  использован {used}  "
                  f"{'активен' if p['active'] else 'выключен'}")

    elif args.cmd == "refs":
        rows = db.top_referrers()
        if not rows:
            print("Пока никто никого не приглашал")
        for r in rows:
            print(f"user {r['id']:>10}  пригласил {r['invited']:>2}  "
                  f"бонусов {kb.money(r['balance'])}")

    elif args.cmd == "sources":
        rows = db.stats_by_source()
        if not rows:
            print("Данных пока нет")
        for r in rows:
            print(f"{r['src']:16} пользователей {r['users']:>3}  "
                  f"заказов {r['orders']:>2}  выручка {kb.money(r['revenue'])}")

    elif args.cmd == "confirm":
        order = db.order(args.order_id)
        if not order:
            print("Заказ не найден")
            return 1
        if order["status"] != STATUS_AWAITING:
            print(f"Заказ в статусе {order['status']} — подтверждать нечего")
            return 1
        result = db.deliver(args.order_id, charge_id=f"cli:{args.order_id}")
        if not result:
            print("Не удалось выдать")
            return 1
        item, title, status = result
        if status == STATUS_NO_STOCK:
            print("Нет товара на складе — пополните и повторите")
            return 1
        print(f"Выдано по заказу #{args.order_id}: {item}")

    elif args.cmd == "reject":
        db.set_status(args.order_id, "canceled")
        print(f"Заказ #{args.order_id} отклонён")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
