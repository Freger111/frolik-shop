"""Товары, склад, заказы и настройки (SQLite, без зависимостей).

Цены — в рублях (целые). Выдача и списание со склада идут одной транзакцией.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price       INTEGER NOT NULL,
    currency    TEXT NOT NULL DEFAULT 'RUB',
    cover       TEXT NOT NULL DEFAULT '',
    category    TEXT NOT NULL DEFAULT 'Разное',
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS stock (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    payload    TEXT NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0,
    order_id   INTEGER,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    price      INTEGER NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',
    charge_id  TEXT,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    ref_id        INTEGER,
    balance       INTEGER NOT NULL DEFAULT 0,
    discount      INTEGER NOT NULL DEFAULT 0,
    discount_uses INTEGER NOT NULL DEFAULT 0,
    source        TEXT NOT NULL DEFAULT '',
    created_at    INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS promos (
    code       TEXT PRIMARY KEY,
    percent    INTEGER NOT NULL,
    max_uses   INTEGER NOT NULL DEFAULT 0,
    used       INTEGER NOT NULL DEFAULT 0,
    active     INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS promo_uses (
    user_id INTEGER NOT NULL,
    code    TEXT NOT NULL,
    used_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, code)
);
CREATE INDEX IF NOT EXISTS idx_stock_product ON stock(product_id, used);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
"""

STATUS_PENDING = "pending"          # ждёт оплаты
STATUS_AWAITING = "awaiting"        # клиент нажал «я оплатил»
STATUS_PAID = "paid"                # подтверждено, товар выдан
STATUS_NO_STOCK = "paid_no_stock"   # оплачено, но склада не хватило
STATUS_CANCELED = "canceled"


class Storage:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.lock:
            self.db.executescript(SCHEMA)
            self._migrate()
            self.db.commit()

    def _migrate(self) -> None:
        cols = {r["name"] for r in self.db.execute("PRAGMA table_info(products)")}
        if "currency" not in cols:
            self.db.execute("ALTER TABLE products ADD COLUMN currency TEXT NOT NULL DEFAULT 'RUB'")
        if "cover" not in cols:
            self.db.execute("ALTER TABLE products ADD COLUMN cover TEXT NOT NULL DEFAULT ''")
        if "category" not in cols:
            self.db.execute(
                "ALTER TABLE products ADD COLUMN category TEXT NOT NULL DEFAULT 'Разное'")

        # старая схема хранила цены заказа в stars — переводим на рубли
        order_cols = {r["name"] for r in self.db.execute("PRAGMA table_info(orders)")}
        if "price" not in order_cols:
            self.db.execute("ALTER TABLE orders ADD COLUMN price INTEGER NOT NULL DEFAULT 0")
        for column in ("base_price", "discount", "bonus_used"):
            if column not in order_cols:
                self.db.execute(
                    f"ALTER TABLE orders ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0")
        if "stars" in order_cols:
            self.db.execute("UPDATE orders SET price = stars WHERE price = 0 AND stars > 0")
            # перестраиваем таблицу: старый NOT NULL stars мешает новым заказам
            self.db.execute("DROP INDEX IF EXISTS idx_charge")
            self.db.execute("DROP INDEX IF EXISTS idx_orders_user")
            self.db.execute("ALTER TABLE orders RENAME TO orders_legacy")
            self.db.execute(
                "CREATE TABLE orders ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " user_id INTEGER NOT NULL,"
                " product_id INTEGER NOT NULL,"
                " price INTEGER NOT NULL,"
                " status TEXT NOT NULL DEFAULT 'pending',"
                " charge_id TEXT,"
                " created_at INTEGER NOT NULL)")
            self.db.execute(
                "INSERT INTO orders(id, user_id, product_id, price, status, charge_id, created_at)"
                " SELECT id, user_id, product_id, COALESCE(price, 0), status, charge_id, created_at"
                " FROM orders_legacy")
            self.db.execute("DROP TABLE orders_legacy")
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)")

    # ---------- настройки ----------
    def get_setting(self, key: str, default: str = "") -> str:
        with self.lock:
            row = self.db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.lock:
            self.db.execute("INSERT INTO settings(key, value) VALUES(?,?)"
                            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                            (key, value))
            self.db.commit()

    # ---------- товары ----------
    def add_product(self, title: str, description: str, price: int,
                    cover: str = "", currency: str = "RUB",
                    category: str = "Разное") -> int:
        with self.lock:
            cur = self.db.execute(
                "INSERT INTO products(title, description, price, currency, cover, category,"
                " created_at) VALUES(?,?,?,?,?,?,?)",
                (title, description, price, currency, cover, category, int(time.time())))
            self.db.commit()
            return int(cur.lastrowid)

    def set_cover(self, product_id: int, cover: str) -> None:
        with self.lock:
            self.db.execute("UPDATE products SET cover = ? WHERE id = ?", (cover, product_id))
            self.db.commit()

    def products(self, active_only: bool = True, category: str | None = None) -> list[dict]:
        where = []
        args: list = []
        if active_only:
            where.append("active = 1")
        if category:
            where.append("category = ?")
            args.append(category)
        sql = "SELECT * FROM products"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY category, id"
        with self.lock:
            rows = self.db.execute(sql, args).fetchall()
        result = []
        for r in rows:
            item = dict(r)
            item["left"] = self.stock_left(item["id"])
            result.append(item)
        return result

    def categories(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT category, COUNT(*) AS count FROM products WHERE active = 1"
                " GROUP BY category ORDER BY count DESC, category").fetchall()
        return [dict(r) for r in rows]

    def get_product(self, product_id: int) -> dict:
        with self.lock:
            row = self.db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return dict(row) if row else {}

    def set_active(self, product_id: int, active: bool) -> None:
        with self.lock:
            self.db.execute("UPDATE products SET active = ? WHERE id = ?",
                            (1 if active else 0, product_id))
            self.db.commit()

    def set_price(self, product_id: int, price: int) -> None:
        with self.lock:
            self.db.execute("UPDATE products SET price = ? WHERE id = ?", (price, product_id))
            self.db.commit()

    # ---------- склад ----------
    def add_stock(self, product_id: int, items: list[str]) -> int:
        now = int(time.time())
        with self.lock:
            self.db.executemany(
                "INSERT INTO stock(product_id, payload, created_at) VALUES(?,?,?)",
                [(product_id, i, now) for i in items])
            self.db.commit()
        return len(items)

    def stock_left(self, product_id: int) -> int:
        with self.lock:
            row = self.db.execute(
                "SELECT COUNT(*) c FROM stock WHERE product_id = ? AND used = 0",
                (product_id,)).fetchone()
        return int(row["c"]) if row else 0

    def is_file_product(self, product_id: int) -> bool:
        """Товар-файл: выдаётся документом и не расходует склад."""
        with self.lock:
            row = self.db.execute(
                "SELECT 1 FROM stock WHERE product_id = ? AND payload LIKE 'file:%' LIMIT 1",
                (product_id,)).fetchone()
        return row is not None

    # ---------- заказы ----------
    def create_order(self, user_id: int, product_id: int, price: int,
                     base_price: int = 0, discount: int = 0, bonus_used: int = 0) -> int:
        with self.lock:
            cur = self.db.execute(
                "INSERT INTO orders(user_id, product_id, price, base_price, discount,"
                " bonus_used, created_at) VALUES(?,?,?,?,?,?,?)",
                (user_id, product_id, price, base_price or price, discount, bonus_used,
                 int(time.time())))
            self.db.commit()
            return int(cur.lastrowid)

    def order(self, order_id: int) -> dict:
        with self.lock:
            row = self.db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return dict(row) if row else {}

    def set_status(self, order_id: int, status: str, charge_id: str | None = None) -> None:
        with self.lock:
            if charge_id:
                self.db.execute("UPDATE orders SET status = ?, charge_id = ? WHERE id = ?",
                                (status, charge_id, order_id))
            else:
                self.db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
            self.db.commit()

    def deliver(self, order_id: int, charge_id: str | None = None) -> tuple[str, str, str] | None:
        """Выдаёт товар со склада и помечает заказ оплаченным (одной транзакцией)."""
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                order = self.db.execute("SELECT * FROM orders WHERE id = ?",
                                        (order_id,)).fetchone()
                if order is None or order["status"] in (STATUS_PAID, STATUS_CANCELED):
                    self.db.rollback()
                    return None
                product = self.db.execute("SELECT * FROM products WHERE id = ?",
                                          (order["product_id"],)).fetchone()
                title = product["title"] if product else "товар"
                item = self.db.execute(
                    "SELECT id, payload FROM stock WHERE product_id = ? AND used = 0"
                    " ORDER BY id LIMIT 1", (order["product_id"],)).fetchone()
                if item is None:
                    self.db.execute(
                        "UPDATE orders SET status = ?, charge_id = COALESCE(?, charge_id)"
                        " WHERE id = ?", (STATUS_NO_STOCK, charge_id, order_id))
                    self.db.commit()
                    return ("", title, STATUS_NO_STOCK)
                # файлы можно выдавать многократно — не сжигаем склад
                if not item["payload"].startswith("file:"):
                    self.db.execute("UPDATE stock SET used = 1, order_id = ? WHERE id = ?",
                                    (order_id, item["id"]))
                else:
                    self.db.execute("UPDATE stock SET order_id = ? WHERE id = ?",
                                    (order_id, item["id"]))
                self.db.execute(
                    "UPDATE orders SET status = ?, charge_id = COALESCE(?, charge_id)"
                    " WHERE id = ?", (STATUS_PAID, charge_id, order_id))
                self.db.commit()
                return (item["payload"], title, STATUS_PAID)
            except Exception:
                self.db.rollback()
                raise

    def purchases(self, user_id: int, limit: int = 10) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT o.id, o.price, o.status, o.created_at, p.title, s.payload"
                " FROM orders o LEFT JOIN products p ON p.id = o.product_id"
                " LEFT JOIN stock s ON s.order_id = o.id"
                " WHERE o.user_id = ? AND o.status IN (?, ?)"
                " ORDER BY o.id DESC LIMIT ?",
                (user_id, STATUS_PAID, STATUS_NO_STOCK, limit)).fetchall()
        return [dict(r) for r in rows]

    # ---------- пользователи, промокоды, рефералы ----------
    def ensure_user(self, user_id: int, ref_id: int | None = None,
                    source: str = "") -> dict:
        now = int(time.time())
        with self.lock:
            row = self.db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is None:
                if ref_id == user_id:
                    ref_id = None
                self.db.execute(
                    "INSERT INTO users(id, ref_id, source, created_at) VALUES(?,?,?,?)",
                    (user_id, ref_id, (source or "")[:40], now))
                self.db.commit()
            else:
                if ref_id and not row["ref_id"] and ref_id != user_id:
                    self.db.execute("UPDATE users SET ref_id = ? WHERE id = ?",
                                    (ref_id, user_id))
                if source and not row["source"]:
                    self.db.execute("UPDATE users SET source = ? WHERE id = ?",
                                    (source[:40], user_id))
                self.db.commit()
            return self.get_user(user_id)

    def get_user(self, user_id: int) -> dict:
        with self.lock:
            row = self.db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else {}

    def add_balance(self, user_id: int, amount: int) -> int:
        with self.lock:
            self.db.execute("UPDATE users SET balance = balance + ? WHERE id = ?",
                            (amount, user_id))
            self.db.commit()
            return self.get_user(user_id).get("balance", 0)

    def spend_balance(self, user_id: int, amount: int) -> None:
        if amount <= 0:
            return
        with self.lock:
            self.db.execute("UPDATE users SET balance = MAX(0, balance - ?) WHERE id = ?",
                            (amount, user_id))
            self.db.commit()

    def clear_discount(self, user_id: int) -> None:
        with self.lock:
            self.db.execute("UPDATE users SET discount = 0, discount_uses = 0 WHERE id = ?",
                            (user_id,))
            self.db.commit()

    def add_promo(self, code: str, percent: int, max_uses: int = 0) -> None:
        with self.lock:
            self.db.execute(
                "INSERT INTO promos(code, percent, max_uses, created_at) VALUES(?,?,?,?)"
                " ON CONFLICT(code) DO UPDATE SET percent = excluded.percent,"
                " max_uses = excluded.max_uses, active = 1",
                (code.upper(), percent, max_uses, int(time.time())))
            self.db.commit()

    def promos(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT * FROM promos ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def activate_promo(self, user_id: int, code: str) -> tuple[bool, int | str]:
        code = code.strip().upper()
        with self.lock:
            promo = self.db.execute("SELECT * FROM promos WHERE code = ?", (code,)).fetchone()
            if promo is None or not promo["active"]:
                return False, "Такого промокода нет."
            if promo["max_uses"] and promo["used"] >= promo["max_uses"]:
                return False, "Промокод уже закончился."
            used = self.db.execute(
                "SELECT 1 FROM promo_uses WHERE user_id = ? AND code = ?",
                (user_id, code)).fetchone()
            if used:
                return False, "Вы уже активировали этот промокод."
            self.db.execute("INSERT INTO promo_uses(user_id, code, used_at) VALUES(?,?,?)",
                            (user_id, code, int(time.time())))
            self.db.execute("UPDATE promos SET used = used + 1 WHERE code = ?", (code,))
            self.db.execute("UPDATE users SET discount = ?, discount_uses = 1 WHERE id = ?",
                            (promo["percent"], user_id))
            self.db.commit()
            return True, int(promo["percent"])

    def stats_by_source(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT COALESCE(NULLIF(u.source, ''), 'напрямую') AS src,"
                " COUNT(DISTINCT u.id) AS users,"
                " COUNT(DISTINCT CASE WHEN o.status = ? THEN o.id END) AS orders,"
                " COALESCE(SUM(CASE WHEN o.status = ? THEN o.price ELSE 0 END), 0) AS revenue"
                " FROM users u LEFT JOIN orders o ON o.user_id = u.id"
                " GROUP BY src ORDER BY users DESC",
                (STATUS_PAID, STATUS_PAID)).fetchall()
        return [dict(r) for r in rows]

    def top_referrers(self, limit: int = 10) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT u.id, u.balance, COUNT(r.id) AS invited"
                " FROM users u LEFT JOIN users r ON r.ref_id = u.id"
                " GROUP BY u.id HAVING invited > 0 ORDER BY invited DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(r) for r in rows]

    def recent_orders(self, limit: int = 15) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT o.id, o.user_id, o.price, o.base_price, o.discount, o.bonus_used,"
                " o.status, o.created_at, p.title"
                " FROM orders o LEFT JOIN products p ON p.id = o.product_id"
                " ORDER BY o.id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        with self.lock:
            products = self.db.execute(
                "SELECT COUNT(*) c FROM products WHERE active = 1").fetchone()["c"]
            stock = self.db.execute(
                "SELECT COUNT(*) c FROM stock WHERE used = 0").fetchone()["c"]
            paid = self.db.execute(
                "SELECT COUNT(*) c, COALESCE(SUM(price),0) s FROM orders WHERE status = ?",
                (STATUS_PAID,)).fetchone()
            awaiting = self.db.execute(
                "SELECT COUNT(*) c FROM orders WHERE status IN (?, ?)",
                (STATUS_PENDING, STATUS_AWAITING)).fetchone()["c"]
            buyers = self.db.execute(
                "SELECT COUNT(DISTINCT user_id) c FROM orders WHERE status = ?",
                (STATUS_PAID,)).fetchone()["c"]
            today = self.db.execute(
                "SELECT COUNT(*) c, COALESCE(SUM(price),0) s FROM orders"
                " WHERE status = ? AND created_at > ?",
                (STATUS_PAID, int(time.time()) - 86400)).fetchone()
        return {"products": products, "stock": stock, "orders": paid["c"],
                "revenue": paid["s"], "awaiting": awaiting, "buyers": buyers,
                "today_orders": today["c"], "today_revenue": today["s"]}
