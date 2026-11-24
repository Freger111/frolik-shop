"""Frolik Shop — магазин цифровых товаров с автовыдачей.

Цены в рублях, оплата по реквизитам с подтверждением админом
или через ЮKassa (если заданы ключи).

Запуск:       python bot.py
Самопроверка: python bot.py --selftest   (без токена и без сети)
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import config, design, keyboards as kb, payments  # noqa: E402
from core.storage import (STATUS_AWAITING, STATUS_CANCELED, STATUS_NO_STOCK,  # noqa: E402
                          STATUS_PAID, STATUS_PENDING, Storage)


# ---------------------------------------------------------------- Telegram API
def _multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    boundary = "----shop" + uuid.uuid4().hex
    parts: list[bytes] = []
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"'
                     f"\r\n\r\n{value}\r\n".encode("utf-8"))
    for key, (filename, data, mime) in files.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"; '
                     f'filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode("utf-8"))
        parts.append(data)
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class Telegram:
    def __init__(self, token: str, transport=None):
        self.token = token
        self.transport = transport
        self.base = f"https://api.telegram.org/bot{token}"

    def call(self, method: str, files: dict | None = None, **params) -> dict:
        if self.transport is not None:
            return self.transport(method, params, files)
        import ssl
        import urllib.error
        import urllib.request

        url = f"{self.base}/{method}"
        params = {k: v for k, v in params.items() if v is not None}
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                if files:
                    body, ctype = _multipart(params, files)
                    req = urllib.request.Request(url, data=body,
                                                 headers={"Content-Type": ctype})
                else:
                    req = urllib.request.Request(
                        url, data=json.dumps(params, ensure_ascii=False).encode("utf-8"),
                        headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, ssl.SSLError, TimeoutError, ConnectionError) as exc:
                last_error = exc
                time.sleep(0.6 * (attempt + 1))
        raise last_error if last_error else RuntimeError("telegram call failed")


# ---------------------------------------------------------------- магазин
class ShopBot:
    def __init__(self, tg: Telegram, db: Storage, admins: set[int] | None = None):
        self.tg = tg
        self.db = db
        self.admins = admins or set()
        self.wizards: dict[int, dict] = {}
        self.awaiting_promo: set[int] = set()
        self.username = ""
        self.offset = 0

    # ---------- отправка ----------
    def say(self, chat_id: int, text: str, markup: dict | None = None) -> dict:
        return self.tg.call("sendMessage", chat_id=chat_id, text=text[:4000],
                            parse_mode="HTML", reply_markup=markup,
                            disable_web_page_preview=True)

    def say_photo(self, chat_id: int, photo, caption: str, markup: dict | None = None) -> dict:
        if isinstance(photo, bytes):
            return self.tg.call("sendPhoto",
                                files={"photo": ("cover.jpg", photo, "image/jpeg")},
                                chat_id=chat_id, caption=caption[:1000],
                                parse_mode="HTML", reply_markup=markup)
        return self.tg.call("sendPhoto", chat_id=chat_id, photo=photo,
                            caption=caption[:1000], parse_mode="HTML", reply_markup=markup)

    def send_banner(self, chat_id: int, caption: str, markup: dict) -> None:
        file_id = self.db.get_setting("banner_file_id")
        if file_id:
            try:
                self.say_photo(chat_id, file_id, caption, markup)
                return
            except Exception:
                pass
        try:
            result = self.say_photo(chat_id, design.banner(config.SHOP_NAME), caption, markup)
            photo = ((result.get("result") or {}).get("photo") or [])
            if photo:
                self.db.set_setting("banner_file_id", photo[-1]["file_id"])
        except Exception:
            self.say(chat_id, caption, markup)

    def send_product_card(self, chat_id: int, product: dict, caption: str, markup: dict) -> None:
        cover = product.get("cover") or ""
        if cover and "/" not in cover and len(cover) > 20:
            try:
                self.say_photo(chat_id, cover, caption, markup)
                return
            except Exception:
                pass
        try:
            result = self.say_photo(chat_id, design.cover(product["title"], product["id"]),
                                    caption, markup)
            photo = ((result.get("result") or {}).get("photo") or [])
            if photo:
                self.db.set_cover(product["id"], photo[-1]["file_id"])
        except Exception:
            self.say(chat_id, caption, markup)

    def send_document(self, chat_id: int, rel_path: str, caption: str) -> bool:
        """Отдаёт файл из папки проекта (цифровой товар)."""
        path = config.ROOT / rel_path
        if not path.exists():
            self.say(chat_id, "⚠️ Файл товара не найден — напишите администратору.")
            return False
        data = path.read_bytes()
        mime = "application/zip" if path.suffix == ".zip" else "application/octet-stream"
        self.tg.call("sendDocument", files={"document": (path.name, data, mime)},
                     chat_id=chat_id, caption=caption[:1000], parse_mode="HTML")
        return True

    def deliver_to_user(self, user_id: int, order_id: int, title: str, item: str) -> None:
        """Выдаёт товар: файл — документом, иначе — текстом."""
        if item.startswith("file:"):
            self.send_document(
                user_id, item[5:],
                f"🎉 <b>Заказ #{order_id}</b>\n\n"
                f"{title}\n\n"
                f"В архиве — оверлеи, экраны, алерты, звуки и инструкция (guide.html).\n"
                f"Файл всегда доступен в «Мои покупки».")
        else:
            self.say(user_id,
                     f"🎉 <b>Заказ #{order_id} выдан</b>\n\n"
                     f"Товар: {title}\n\n"
                     f"<code>{item}</code>\n\n"
                     f"Сохраните это сообщение.", kb.back("my", "📦 Мои покупки"))

    def pay_referral(self, order: dict) -> None:
        """Начисляет пригласившему 15% от суммы заказа."""
        buyer = self.db.get_user(order["user_id"])
        ref = buyer.get("ref_id")
        if not ref or ref == order["user_id"]:
            return
        reward = max(1, round(order["price"] * 0.15))
        balance = self.db.add_balance(ref, reward)
        product = self.db.get_product(order["product_id"])
        try:
            self.say(ref,
                     f"💸 Ваш друг купил «{product.get('title', 'товар')}».\n"
                     f"Вам начислено <b>{kb.money(reward)}</b> бонусами.\n"
                     f"Всего бонусов: <b>{kb.money(balance)}</b> — ими можно оплачивать заказы.")
        except Exception:
            pass

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admins

    def notify_admins(self, text: str, markup: dict | None = None) -> None:
        for admin in self.admins:
            try:
                self.say(admin, text, markup)
            except Exception:
                pass

    def _log_visit(self, user_id: int, username: str, text: str) -> None:
        if self.tg.transport is not None:
            return  # в самотестах не мусорим в реальный лог
        try:
            path = Path("data/visits.log")
            path.parent.mkdir(exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} id={user_id} "
                        f"@{username or '-'} :: {text[:60]}\n")
        except Exception:
            pass

    # ---------- вход ----------
    def handle_update(self, update: dict) -> None:
        try:
            if "callback_query" in update:
                self.on_callback(update["callback_query"])
            elif "pre_checkout_query" in update:
                self.tg.call("answerPreCheckoutQuery",
                             pre_checkout_query_id=update["pre_checkout_query"].get("id"),
                             ok=True)
            elif "message" in update:
                self.on_message(update["message"])
        except Exception:
            Path("data/error.log").write_text(traceback.format_exc(), encoding="utf-8")

    def on_message(self, msg: dict) -> None:
        chat_id = msg["chat"]["id"]
        frm = msg.get("from") or {}
        user_id = frm.get("id", chat_id)
        text = (msg.get("text") or "").strip()
        self._log_visit(user_id, frm.get("username", ""), text)

        args = text.split(maxsplit=1)
        payload = args[1].strip() if len(args) > 1 else ""

        if user_id in self.wizards and text and not text.startswith("/"):
            self.wizard_step(chat_id, user_id, text)
            return

        if text.startswith("/start"):
            ref_id = None
            source = ""
            if payload.startswith("ref_") and payload[4:].isdigit():
                ref_id = int(payload[4:])
            elif payload.startswith("src_"):
                source = payload[4:]
            user = self.db.ensure_user(user_id, ref_id=ref_id, source=source)
            caption = kb.WELCOME.format(shop=config.SHOP_NAME)
            if ref_id and ref_id != user_id:
                caption += "\n\n🎁 Вы пришли по приглашению — другу начислим бонус с покупки."
            self.send_banner(chat_id, caption, kb.main_menu(self.is_admin(user_id)))
            return

        user = self.db.ensure_user(user_id)

        if user_id in self.awaiting_promo and text and not text.startswith("/"):
            self.awaiting_promo.discard(user_id)
            self.apply_promo(chat_id, user_id, text)
        elif text.startswith("/promo"):
            code = payload.strip()
            if code:
                self.apply_promo(chat_id, user_id, code)
            else:
                self.awaiting_promo.add(user_id)
                self.say(chat_id, "Введите промокод одним сообщением.")
        elif text.startswith("/invite"):
            self.show_invite(chat_id, user_id)
        elif text.startswith("/free"):
            self.send_document(
                chat_id, "assets/free_pack.zip",
                "🎁 <b>Бесплатный мини-пак</b>\n\n"
                "Внутри: рамка для стрима, плашка с ником и звук алерта.\n"
                "Инструкция — в файле «КАК_ПОДКЛЮЧИТЬ.txt».\n\n"
                "Полные паки — в /catalog")
        elif text.startswith("/ad"):
            path = config.ROOT / "assets" / "obs_bot_ad.gif"
            if path.exists():
                self.tg.call("sendAnimation",
                             files={"animation": (path.name, path.read_bytes(), "image/gif")},
                             chat_id=chat_id,
                             caption="📺 Рекламный виджет для OBS (760×180, прозрачные углы).\n"
                                     "OBS → Источники → Медиа → этот файл → «Зациклить».\n"
                                     "HTML-версия: assets/widgets/bot_ad.html")
            else:
                self.say(chat_id, "GIF не найден.")
        elif text.startswith("/reel"):
            path = config.ROOT / "marketing" / "carousel" / "reel.mp4"
            if path.exists():
                self.tg.call("sendVideo",
                             files={"video": (path.name, path.read_bytes(), "video/mp4")},
                             chat_id=chat_id,
                             caption="🎬 Готовый ролик для TikTok (9 секунд, 1080×1920).\n"
                                     "Сохраните в галерею и загрузите в TikTok.")
            else:
                self.say(chat_id, "Ролик не найден.")
        elif text.startswith("/slides"):
            sent = 0
            for i in (1, 2, 3):
                path = config.ROOT / "marketing" / "carousel" / f"slide_{i}.jpg"
                if path.exists():
                    self.tg.call("sendPhoto",
                                 files={"photo": (path.name, path.read_bytes(), "image/jpeg")},
                                 chat_id=chat_id, caption=f"Слайд {i}/3 — сохраните в галерею")
                    sent += 1
            if not sent:
                self.say(chat_id, "Слайды не найдены.")
        elif text.startswith("/id"):
            self.say(chat_id, f"Ваш Telegram ID: <code>{user_id}</code>")
        elif text.startswith("/catalog"):
            self.show_catalog(chat_id)
        elif text.startswith("/my"):
            self.show_purchases(chat_id, user_id)
        elif text.startswith("/help"):
            self.say(chat_id, self._help_text(), kb.back())
        elif text.startswith("/admin"):
            self.show_admin(chat_id, user_id)
        else:
            self.say(chat_id, "Выберите раздел 👇", kb.main_menu(self.is_admin(user_id)))

    def apply_promo(self, chat_id: int, user_id: int, code: str) -> None:
        ok, result = self.db.activate_promo(user_id, code)
        if ok:
            self.say(chat_id,
                     f"🎉 Промокод активирован: скидка <b>{result}%</b>\n"
                     f"Применится к следующей покупке.", kb.main_menu(self.is_admin(user_id)))
        else:
            self.say(chat_id, f"⚠️ {result}", kb.main_menu(self.is_admin(user_id)))

    def show_invite(self, chat_id: int, user_id: int) -> None:
        link = f"https://t.me/{self.username}?start=ref_{user_id}" if self.username \
            else f"/start ref_{user_id}"
        user = self.db.get_user(user_id)
        self.say(chat_id,
                 f"👥 <b>Приглашайте друзей</b>\n\n"
                 f"За каждую покупку друга вы получаете <b>15%</b> от суммы "
                 f"на бонусный счёт. Бонусами можно оплачивать свои заказы.\n\n"
                 f"Ваша ссылка:\n<code>{link}</code>\n\n"
                 f"Бонусов на счету: <b>{kb.money(user.get('balance', 0))}</b>",
                 kb.main_menu(self.is_admin(user_id)))

    def _help_text(self) -> str:
        admin = next(iter(self.admins), "")
        return kb.HELP.format(admin=f"@{admin}" if admin else "напишите в этот чат")

    # ---------- кнопки ----------
    def on_callback(self, cq: dict) -> None:
        data = cq.get("data", "")
        msg = cq.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        frm = cq.get("from") or {}
        user_id = frm.get("id", chat_id)
        self.tg.call("answerCallbackQuery", callback_query_id=cq.get("id"))
        if chat_id is None:
            return

        if data == "menu":
            self.say(chat_id, "Главное меню 👇", kb.main_menu(self.is_admin(user_id)))
        elif data == "catalog":
            self.show_categories(chat_id)
        elif data.startswith("cat:"):
            self.show_catalog(chat_id, data[4:])
        elif data == "cat_all":
            self.show_catalog(chat_id, None)
        elif data == "help":
            self.say(chat_id, self._help_text(), kb.back())
        elif data == "my":
            self.show_purchases(chat_id, user_id)
        elif data == "promo":
            self.awaiting_promo.add(user_id)
            self.say(chat_id, "🎁 Введите промокод одним сообщением.")
        elif data == "invite":
            self.show_invite(chat_id, user_id)
        elif data == "free":
            self.send_document(
                chat_id, "assets/free_pack.zip",
                "🎁 <b>Бесплатный мини-пак</b>\n\n"
                "Внутри: рамка для стрима, плашка с ником и звук алерта.\n"
                "Инструкция — в файле «КАК_ПОДКЛЮЧИТЬ.txt».\n\n"
                "Полные паки — в /catalog")
        elif data.startswith("p:"):
            self.show_product(chat_id, int(data.split(":")[1]))
        elif data.startswith("buy:"):
            self.start_purchase(chat_id, user_id, int(data.split(":")[1]))
        elif data.startswith("paid:"):
            self.mark_paid(chat_id, user_id, int(data.split(":")[1]))
        elif data.startswith("cancel:"):
            self.cancel_order(chat_id, user_id, int(data.split(":")[1]))
        elif data == "adm":
            self.show_admin(chat_id, user_id)
        elif data.startswith("adm:"):
            self.admin_action(chat_id, user_id, data[4:])
        elif data.startswith("admok:"):
            self.confirm_payment(chat_id, user_id, int(data.split(":")[1]))
        elif data.startswith("admno:"):
            self.reject_payment(chat_id, user_id, int(data.split(":")[1]))

    # ---------- витрина ----------
    def show_categories(self, chat_id: int) -> None:
        categories = self.db.categories()
        if not categories:
            self.say(chat_id, "🛍 Каталог пока пуст — заходите позже.", kb.back())
            return
        self.say(chat_id, "🛍 <b>Каталог</b>\n\nВыберите раздел 👇",
                 kb.categories(categories))

    def show_catalog(self, chat_id: int, category: str | None = None) -> None:
        products = self.db.products(category=category)
        if not products:
            self.say(chat_id, "В этом разделе пока пусто.", kb.back("catalog", "← Разделы"))
            return
        title = f"🛍 <b>{category}</b>" if category else "🛍 <b>Все товары</b>"
        self.say(chat_id, title + "\n\nВыберите товар 👇", kb.catalog(products))

    def show_product(self, chat_id: int, product_id: int) -> None:
        p = self.db.get_product(product_id)
        if not p or not p.get("active"):
            self.say(chat_id, "Товар не найден.", kb.back("catalog", "← Каталог"))
            return
        left = self.db.stock_left(product_id)
        lines = [f"<b>{p['title']}</b>", ""]
        if p["description"]:
            lines += [p["description"], ""]
        lines += ["━━━━━━━━━━━━━━",
                  f"💰 <b>{kb.money(p['price'])}</b>"]
        if self.db.is_file_product(product_id):
            lines.append("📎 Цифровой товар · файл, выдача сразу")
        else:
            lines.append(f"📦 В наличии: <b>{left}</b> шт.")
        self.send_product_card(chat_id, p, "\n".join(lines), kb.product_card({**p, "left": left}))

    # ---------- покупка ----------
    def start_purchase(self, chat_id: int, user_id: int, product_id: int) -> None:
        p = self.db.get_product(product_id)
        if not p or not p.get("active"):
            self.say(chat_id, "Товар недоступен.", kb.back("catalog", "← Каталог"))
            return
        if self.db.stock_left(product_id) <= 0:
            self.say(chat_id, "😔 Этот товар закончился. Загляните позже.",
                     kb.back("catalog", "← Каталог"))
            return
        user = self.db.ensure_user(user_id)
        base = int(p["price"])
        percent = int(user.get("discount") or 0) if user.get("discount_uses") else 0
        discount = round(base * percent / 100) if percent else 0
        after_discount = base - discount
        bonus = min(int(user.get("balance") or 0), after_discount)
        total = after_discount - bonus

        order_id = self.db.create_order(user_id, product_id, total, base, discount, bonus)
        if percent:
            self.db.clear_discount(user_id)
        if bonus:
            self.db.spend_balance(user_id, bonus)

        breakdown = ""
        if discount or bonus:
            parts = [f"Цена: {kb.money(base)}"]
            if discount:
                parts.append(f"Промокод −{percent}%: −{kb.money(discount)}")
            if bonus:
                parts.append(f"Бонусы: −{kb.money(bonus)}")
            parts.append(f"<b>К оплате: {kb.money(total)}</b>")
            breakdown = "\n".join(parts) + "\n\n"

        if config.PAYMENT_MODE == "yookassa" and payments.yookassa_ready():
            url = payments.create_payment(total, order_id, p["title"])
            if url:
                self.say(chat_id,
                         f"🧾 <b>Заказ #{order_id}</b>\n\n{p['title']}\n"
                         f"{breakdown}"
                         f"Оплатите картой или через СБП — товар придёт автоматически.",
                         kb.pay_link(url, order_id))
                threading.Thread(target=self._watch_payment, args=(order_id, user_id),
                                 daemon=True).start()
                return
            self.say(chat_id, "⚠️ Не удалось создать платёж, попробуйте позже.")

        # ручная оплата по реквизитам
        lines = [f"🧾 <b>Заказ #{order_id}</b>", "",
                 f"Товар: {p['title']}"]
        if breakdown:
            lines.append("")
            lines.append(breakdown.rstrip())
        else:
            lines.append(f"Сумма: <b>{kb.money(total)}</b>")
        lines.append("")
        if config.PAY_SBP:
            lines.append(f"📱 СБП: <code>{config.PAY_SBP}</code>")
        if config.PAY_CARD:
            lines.append(f"💳 Карта: <code>{config.PAY_CARD}</code>")
        if config.PAY_NAME:
            lines.append(f"👤 Получатель: {config.PAY_NAME}")
        if not (config.PAY_SBP or config.PAY_CARD):
            lines.append("⚠️ Реквизиты ещё не настроены — напишите администратору.")
        lines += ["", config.PAY_NOTE,
                  "", "После перевода нажмите кнопку ниже 👇"]
        self.say(chat_id, "\n".join(lines), kb.pay_manual(order_id))

    def mark_paid(self, chat_id: int, user_id: int, order_id: int) -> None:
        order = self.db.order(order_id)
        if not order or order["user_id"] != user_id:
            self.say(chat_id, "Заказ не найден.")
            return
        if order["status"] == STATUS_PAID:
            self.say(chat_id, "Этот заказ уже оплачен и выдан.")
            return
        if order["status"] == STATUS_AWAITING:
            self.say(chat_id, "Уже проверяю оплату — скоро пришлю товар.")
            return
        if order["status"] == STATUS_CANCELED:
            self.say(chat_id, "Заказ отменён. Создайте новый.", kb.back("catalog", "← Каталог"))
            return
        self.db.set_status(order_id, STATUS_AWAITING)
        self.say(chat_id, "✅ Принял. Проверяю оплату — товар придёт в этот чат.")
        product = self.db.get_product(order["product_id"])
        self.notify_admins(
            f"💸 <b>Оплата заявлена</b>\n\n"
            f"Заказ: #{order_id}\n"
            f"Товар: {product.get('title', '—')}\n"
            f"Сумма: <b>{kb.money(order['price'])}</b>\n"
            f"Покупатель: {user_id}",
            kb.admin_confirm(order_id))

    def confirm_payment(self, chat_id: int, admin_id: int, order_id: int) -> None:
        if not self.is_admin(admin_id):
            return
        order = self.db.order(order_id)
        if not order:
            self.say(chat_id, "Заказ не найден.")
            return
        result = self.db.deliver(order_id, charge_id=f"manual:{admin_id}:{int(time.time())}")
        if result is None:
            self.say(chat_id, "Этот заказ уже обработан.")
            return
        item, title, status = result
        if status == STATUS_NO_STOCK:
            self.say(chat_id, f"⚠️ По заказу #{order_id} нет товара на складе — пополните и повторите.")
            try:
                self.say(order["user_id"], "⚠️ Оплата получена, но товар закончился. "
                                           "Администратор свяжется с вами.")
            except Exception:
                pass
            return
        self.say(chat_id, f"✅ Заказ #{order_id} выдан.")
        try:
            self.deliver_to_user(order["user_id"], order_id, title, item)
            self.pay_referral(order)
        except Exception:
            pass

    def reject_payment(self, chat_id: int, admin_id: int, order_id: int) -> None:
        if not self.is_admin(admin_id):
            return
        order = self.db.order(order_id)
        if not order:
            return
        self.db.set_status(order_id, STATUS_CANCELED)
        self.say(chat_id, f"Заказ #{order_id} отклонён.")
        try:
            self.say(order["user_id"],
                     f"❌ Заказ #{order_id} не подтверждён.\n"
                     f"Если вы оплатили — напишите администратору.")
        except Exception:
            pass

    def cancel_order(self, chat_id: int, user_id: int, order_id: int) -> None:
        order = self.db.order(order_id)
        if order and order["user_id"] == user_id and order["status"] == STATUS_PENDING:
            self.db.set_status(order_id, STATUS_CANCELED)
        self.say(chat_id, "Заказ отменён.", kb.back("catalog", "← Каталог"))

    def _watch_payment(self, order_id: int, user_id: int) -> None:
        """Ждёт подтверждения оплаты в ЮKassa и выдаёт товар."""
        deadline = time.time() + config.ORDER_TTL_MINUTES * 60
        while time.time() < deadline:
            st = payments.payment_status(f"order-{order_id}")
            if st == "succeeded":
                result = self.db.deliver(order_id, charge_id=f"yookassa:{order_id}")
                if result:
                    item, title, status = result
                    if status == STATUS_PAID:
                        try:
                            self.deliver_to_user(user_id, order_id, title, item)
                            self.pay_referral(self.db.order(order_id))
                        except Exception:
                            pass
                        self.notify_admins(f"💰 Оплата получена: заказ #{order_id}")
                return
            if st == "canceled":
                self.db.set_status(order_id, STATUS_CANCELED)
                return
            time.sleep(5)

    # ---------- история ----------
    def show_purchases(self, chat_id: int, user_id: int) -> None:
        rows = self.db.purchases(user_id)
        if not rows:
            self.say(chat_id, "Покупок пока нет.", kb.back("catalog", "← Каталог"))
            return
        lines = ["📦 <b>Мои покупки</b>", ""]
        for r in rows:
            when = time.strftime("%d.%m %H:%M", time.localtime(r["created_at"]))
            payload = r.get("payload") or ""
            if r["status"] == STATUS_PAID and payload.startswith("file:"):
                lines.append(f"• <b>{r['title']}</b> — 📎 файл отправлен в чат\n  <i>{when}</i>")
            elif r["status"] == STATUS_PAID and payload:
                lines.append(f"• <b>{r['title']}</b> — <code>{payload}</code>\n  <i>{when}</i>")
            else:
                lines.append(f"• {r['title']} — ожидает выдачи ({when})")
        self.say(chat_id, "\n".join(lines), kb.back())

    # ---------- админка ----------
    def show_admin(self, chat_id: int, user_id: int) -> None:
        if not self.is_admin(user_id):
            self.say(chat_id, "Раздел только для администратора.")
            return
        self.say(chat_id, "⚙️ <b>Админ-панель</b>", kb.admin_panel())

    def admin_action(self, chat_id: int, user_id: int, action: str) -> None:
        if not self.is_admin(user_id):
            return
        if action == "add":
            self.wizards[user_id] = {"step": "title", "draft": {}}
            self.say(chat_id, "1/4. Название товара:")
        elif action == "topup":
            products = self.db.products(active_only=False)
            if not products:
                self.say(chat_id, "Сначала добавьте товар.", kb.admin_panel())
                return
            self.say(chat_id, "Выберите товар:", kb.products_picker(products, "adm:stock"))
        elif action == "orders":
            self.show_orders(chat_id)
        elif action == "stats":
            s = self.db.stats()
            self.say(chat_id,
                     f"📊 <b>Статистика</b>\n\n"
                     f"Товаров: {s['products']}\n"
                     f"На складе: {s['stock']} шт.\n"
                     f"Продаж всего: {s['orders']}\n"
                     f"Выручка: <b>{kb.money(s['revenue'])}</b>\n"
                     f"За сутки: {s['today_orders']} продаж на {kb.money(s['today_revenue'])}\n"
                     f"Ждут подтверждения: {s['awaiting']}\n"
                     f"Покупателей: {s['buyers']}", kb.admin_panel())
        elif action.startswith("stock:"):
            product_id = int(action.split(":")[1])
            p = self.db.get_product(product_id)
            self.wizards[user_id] = {"step": "stock", "draft": {"product_id": product_id}}
            self.say(chat_id,
                     f"Пришлите позиции для «{p.get('title', product_id)}» — по одной в строке.\n"
                     f"Сейчас на складе: {self.db.stock_left(product_id)} шт.")

    def show_orders(self, chat_id: int) -> None:
        rows = self.db.recent_orders(15)
        if not rows:
            self.say(chat_id, "Заказов пока нет.", kb.admin_panel())
            return
        labels = {STATUS_PENDING: "ждёт оплаты", STATUS_AWAITING: "ждут проверки",
                  STATUS_PAID: "выдан", STATUS_NO_STOCK: "нет на складе",
                  STATUS_CANCELED: "отменён"}
        lines = ["🧾 <b>Последние заказы</b>", ""]
        for r in rows:
            when = time.strftime("%d.%m %H:%M", time.localtime(r["created_at"]))
            lines.append(f"#{r['id']} · {r['title']} · {kb.money(r['price'])} · "
                         f"{labels.get(r['status'], r['status'])} · {when}")
        self.say(chat_id, "\n".join(lines), kb.admin_panel())

    def wizard_step(self, chat_id: int, user_id: int, text: str) -> None:
        wiz = self.wizards.get(user_id)
        if not wiz:
            return
        step, draft = wiz["step"], wiz["draft"]

        if step == "title":
            draft["title"] = text[:60]
            wiz["step"] = "price"
            self.say(chat_id, "2/4. Цена в рублях (целое число):")
        elif step == "price":
            if not text.isdigit() or int(text) <= 0:
                self.say(chat_id, "Нужно число больше нуля. Повторите цену:")
                return
            draft["price"] = int(text)
            wiz["step"] = "desc"
            self.say(chat_id, "3/4. Описание (или «-», чтобы пропустить):")
        elif step == "desc":
            draft["description"] = "" if text.strip() == "-" else text[:500]
            wiz["step"] = "stock"
            self.say(chat_id, "4/4. Позиции склада — по одной в строке, или «-».")
        elif step == "stock":
            product_id = draft.get("product_id")
            if product_id is None:
                product_id = self.db.add_product(draft["title"], draft["description"],
                                                 draft["price"])
            items = [line.strip() for line in text.splitlines() if line.strip()]
            if items and items != ["-"]:
                self.db.add_stock(product_id, items[:config.MAX_ITEMS_PER_ADD])
            self.wizards.pop(user_id, None)
            p = self.db.get_product(product_id)
            self.say(chat_id,
                     f"✅ Товар добавлен: <b>{p['title']}</b>\n"
                     f"Цена: {kb.money(p['price'])}\n"
                     f"На складе: {self.db.stock_left(product_id)} шт.",
                     kb.admin_panel())

    # ---------- цикл ----------
    def poll_forever(self) -> None:
        try:
            self.username = (self.tg.call("getMe").get("result") or {}).get("username", "")
        except Exception:
            pass
        try:
            self.tg.call("setMyCommands", commands=[
                {"command": "start", "description": "Магазин"},
                {"command": "catalog", "description": "Каталог"},
                {"command": "promo", "description": "Промокод"},
                {"command": "invite", "description": "Пригласить друга"},
                {"command": "my", "description": "Мои покупки"},
                {"command": "help", "description": "Помощь"},
            ])
        except Exception:
            pass
        while True:
            try:
                data = self.tg.call("getUpdates", offset=self.offset, timeout=30,
                                    allowed_updates=["message", "callback_query",
                                                     "pre_checkout_query"])
                for update in data.get("result", []):
                    self.offset = update["update_id"] + 1
                    self.handle_update(update)
            except KeyboardInterrupt:
                return
            except Exception:
                time.sleep(3)


# ---------------------------------------------------------------- самопроверка
class FakeTransport:
    def __init__(self):
        self.calls: list[tuple[str, dict, dict | None]] = []
        self._id = 0

    def __call__(self, method: str, params: dict, files: dict | None) -> dict:
        self.calls.append((method, params, files))
        self._id += 1
        if method == "sendPhoto":
            return {"ok": True, "result": {"message_id": self._id,
                                           "photo": [{"file_id": f"FILE{self._id}"}]}}
        return {"ok": True, "result": {"message_id": self._id}}

    def last_text(self) -> str:
        for method, params, _ in reversed(self.calls):
            if method in ("sendMessage", "sendPhoto"):
                return params.get("text") or params.get("caption") or ""
        return ""

    def has_text(self, needle: str) -> bool:
        return any(needle in ((c[1].get("text") or "") + (c[1].get("caption") or ""))
                   for c in self.calls if c[0] in ("sendMessage", "sendPhoto"))

    def last_markup(self) -> dict:
        for method, params, _ in reversed(self.calls):
            if method in ("sendMessage", "sendPhoto"):
                return params.get("reply_markup") or {}
        return {}

    def markup_with(self, needle: str) -> dict:
        for method, params, _ in reversed(self.calls):
            markup = params.get("reply_markup") or {}
            text = json.dumps(markup, ensure_ascii=False)
            if needle in text:
                return markup
        return {}

    def count(self, method: str) -> int:
        return len([c for c in self.calls if c[0] == method])


def selftest() -> int:
    import tempfile

    ok = True

    def check(name: str, condition: bool) -> None:
        nonlocal ok
        print(("  ✓ " if condition else "  ✗ ") + name)
        ok = ok and condition

    db = Storage(Path(tempfile.mkdtemp()) / "shop.db")
    tg = Telegram("test", transport=FakeTransport())
    bot = ShopBot(tg, db, admins={1})
    t = tg.transport

    def msg(user: int, text: str) -> None:
        bot.handle_update({"message": {"chat": {"id": user}, "from": {"id": user},
                                       "text": text}})

    def cb(user: int, data: str) -> None:
        bot.handle_update({"callback_query": {"id": "x", "data": data,
                                              "message": {"chat": {"id": user}},
                                              "from": {"id": user}}})

    print("1. Приветствие с баннером")
    msg(42, "/start")
    check("баннер отправлен", t.count("sendPhoto") >= 1)
    check("текст с названием магазина", "Frolik Shop" in t.last_text() or
          "магазин" in t.last_text().lower())

    print("2. Админ добавляет товар (цена в рублях)")
    msg(1, "/admin")
    cb(1, "adm:add")
    msg(1, "Ключ на 30 дней")
    msg(1, "500")
    msg(1, "Доступ к закрытому чату")
    msg(1, "KEY-AAAA-1111\nKEY-BBBB-2222")
    products = db.products()
    check("товар создан", len(products) == 1)
    check("цена в рублях", products and products[0]["price"] == 500)
    check("на складе 2 позиции", products and products[0]["left"] == 2)

    print("2b. Каталог: разделы и все товары")
    cb(42, "catalog")
    check("раздел «Разное» в меню",
          "Разное" in json.dumps(t.last_markup(), ensure_ascii=False))
    cb(42, "cat_all")
    check("видны все товары",
          "Ключ на 30 дней" in json.dumps(t.last_markup(), ensure_ascii=False))

    print("3. Карточка товара с обложкой")
    pid = products[0]["id"]
    cb(42, f"p:{pid}")
    check("карточка с фото", t.count("sendPhoto") >= 2)
    check("цена в ₽", "500" in t.last_text() and "₽" in t.last_text())

    print("4. Покупка: рубли и реквизиты")
    cb(42, f"buy:{pid}")
    check("показан номер заказа", "#1" in t.last_text() or "Заказ #1" in t.last_text())
    check("сумма в рублях", "500" in t.last_text() and "₽" in t.last_text())
    check("есть кнопка «Я оплатил»", "Я оплатил" in json.dumps(t.last_markup(), ensure_ascii=False))

    print("5. Клиент нажал «оплатил» → админу уходит подтверждение")
    cb(42, "paid:1")
    check("клиенту сказано «проверяю»", t.has_text("Проверяю") or t.has_text("Принял"))
    check("админу пришли кнопки", bool(t.markup_with("admok:1")))

    print("6. Админ подтверждает — товар выдаётся")
    cb(1, "admok:1")
    check("покупателю выдан код", t.has_text("KEY-AAAA-1111"))
    check("склад уменьшился", db.stock_left(pid) == 1)
    check("статус paid", db.order(1)["status"] == STATUS_PAID)
    check("выручка учтена", db.stats()["revenue"] == 500)

    print("7. Повторное подтверждение не выдаёт второй товар")
    cb(1, "admok:1")
    check("склад не изменился", db.stock_left(pid) == 1)

    print("8. Отклонение заказа")
    cb(42, f"buy:{pid}")
    cb(42, "paid:2")
    cb(1, "admno:2")
    check("заказ отменён", db.order(2)["status"] == STATUS_CANCELED)
    check("покупателю сообщили", t.has_text("не подтверждён"))

    print("9. Мои покупки и статистика")
    cb(42, "my")
    check("покупка видна", t.has_text("KEY-AAAA-1111"))
    msg(1, "/admin")
    cb(1, "adm:stats")
    check("статистика в рублях", "500" in t.last_text() and "₽" in t.last_text())

    print("10. Распродажа и запрет покупки без остатка")
    cb(42, f"buy:{pid}")
    cb(42, "paid:3")
    cb(1, "admok:3")
    check("склад пуст", db.stock_left(pid) == 0)
    before = t.count("sendMessage")
    cb(42, f"buy:{pid}")
    check("покупка не началась", t.count("sendMessage") > before)
    check("сообщение «закончился»", "закончился" in t.last_text().lower())

    print("11. Доступ в админку")
    cb(42, "adm")
    check("закрыто для обычных", "только для администратора" in t.last_text().lower())

    print("12. Цифровой товар-файл")
    fid = db.add_product("OBS-пак", "Оверлеи и звуки", 690)
    db.add_stock(fid, ["file:assets/obs_pack.zip"])
    cb(42, f"buy:{fid}")
    cb(42, "paid:4")
    cb(1, "admok:4")
    check("файл отправлен документом", t.count("sendDocument") >= 1)
    check("склад не сожжён (файл многоразовый)", db.stock_left(fid) == 1)
    check("заказ оплачен", db.order(4)["status"] == STATUS_PAID)

    print("13. Промокод, реферал, источники")
    db.add_promo("TEST30", 30, 5)
    msg(42, "/promo TEST30")
    check("промокод активирован", db.get_user(42)["discount"] == 30)
    cb(42, f"buy:{fid}")
    discounted = db.recent_orders(1)[0]
    check("скидка применена к заказу", discounted["price"] == 483 and discounted["discount"] == 207)
    cb(42, f"paid:{discounted['id']}")
    cb(1, f"admok:{discounted['id']}")
    check("заказ со скидкой выдан", db.order(discounted["id"])["status"] == STATUS_PAID)
    check("промокод сгорел после покупки", db.get_user(42)["discount"] == 0)

    msg(77, "/start ref_42")
    check("реферер записан", db.get_user(77)["ref_id"] == 42)
    cb(77, f"buy:{fid}")
    referred = db.recent_orders(1)[0]
    cb(77, f"paid:{referred['id']}")
    cb(1, f"admok:{referred['id']}")
    check("пригласившему начислен бонус", db.get_user(42)["balance"] >= 100)

    msg(88, "/start src_tiktok")
    sources = {r["src"]: r for r in db.stats_by_source()}
    check("метка источника tiktok учтена", "tiktok" in sources)

    print("\nИтог:", "всё работает" if ok else "есть ошибки")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        code = selftest()
        os._exit(code)
    if not config.BOT_TOKEN:
        print("Нет BOT_TOKEN. Заполните .env или запустите: python bot.py --selftest")
        raise SystemExit(1)
    bot = ShopBot(Telegram(config.BOT_TOKEN), Storage(config.DB_PATH), config.ADMIN_IDS)
    print("Магазин запущен. Ctrl+C — остановить.")
    bot.poll_forever()
