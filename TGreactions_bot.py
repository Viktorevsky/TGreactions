
import json
import logging
from collections import defaultdict
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================================
TOKEN = "8358332356:AAHo1J_LtkAfDxVSYpXRkl-Jz5-U5FviJFk"
JSON_FILE = "result.json"          # путь к JSON-файлу экспорта
# ================================

logging.basicConfig(level=logging.WARNING)
 
 
def load_data(filepath: str) -> dict:
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)
 
 
def analyze(data: dict) -> dict:
    totals = defaultdict(int)
    msg_totals = []
    messages = [m for m in data.get("messages", []) if m.get("type") == "message"]
 
    for msg in messages:
        reactions = msg.get("reactions", [])
        if not reactions:
            continue
        msg_sum = 0
        for r in reactions:
            count = r.get("count", 0)
            msg_sum += count
            if r.get("type") == "emoji":
                key = r.get("emoji", "?")
            elif r.get("type") == "paid":
                key = "PAID"
            elif r.get("type") == "custom_emoji":
                key = "CUSTOM"
            else:
                key = r.get("type", "?")
            totals[key] += count
 
        text = msg.get("text", "")
        if isinstance(text, list):
            text = "".join(t if isinstance(t, str) else t.get("text", "") for t in text)
        preview = (text[:45] + "…") if len(text) > 45 else (text or "[медиа]")
        msg_totals.append((msg_sum, msg.get("id"), msg.get("date", "")[:10], preview))
 
    msg_totals.sort(reverse=True)
    msgs_with_r = sum(1 for m in messages if m.get("reactions"))
 
    return {
        "channel": data.get("name", "канал"),
        "total_messages": len(messages),
        "msgs_with_reactions": msgs_with_r,
        "totals": dict(totals),
        "top_posts": msg_totals[:10],
        "total_reactions": sum(totals.values()),
    }
 
 
def fmt_num(n: int) -> str:
    """1234567 → 1.2M, 12345 → 12.3K"""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)
 
 
def bar(count: int, max_count: int, width: int = 10) -> str:
    filled = round(count / max_count * width)
    return "▓" * filled + "░" * (width - filled)
 
 
CACHE = analyze(load_data(JSON_FILE))
 
 
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = CACHE
    await update.message.reply_text(
        f"╔══ 📡 {c['channel']} ══╗\n"
        f"║  Бот аналитики реакций\n"
        f"╚{'═' * (len(c['channel']) + 14)}╝\n\n"
        f"📌 Команды:\n"
        f"  /top    — топ реакций\n"
        f"  /posts  — горячие посты\n"
        f"  /stats  — статистика канала"
    )
 
 
async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    totals = CACHE["totals"]
    total_all = CACHE["total_reactions"]
 
    # Разделяем на категории
    special = {k: v for k, v in totals.items() if k in ("PAID", "CUSTOM")}
    emoji = {k: v for k, v in totals.items() if k not in ("PAID", "CUSTOM")}
 
    sorted_emoji = sorted(emoji.items(), key=lambda x: x[1], reverse=True)
    max_emoji = sorted_emoji[0][1] if sorted_emoji else 1
 
    lines = [f"🏆  ТОП РЕАКЦИЙ — {CACHE['channel']}\n"]
 
    # Спецреакции отдельным блоком
    if special:
        lines.append("── Спецреакции ──────────────")
        if "CUSTOM" in special:
            pct = special["CUSTOM"] / total_all * 100
            lines.append(f"  ✨ Premium emoji   {fmt_num(special['CUSTOM']):>6}  ({pct:.1f}%)")
        if "PAID" in special:
            pct = special["PAID"] / total_all * 100
            lines.append(f"  ⭐ Paid stars      {fmt_num(special['PAID']):>6}  ({pct:.1f}%)")
        lines.append("")
 
    # Обычные эмодзи
    lines.append("── Эмодзи ───────────────────")
    medals = ["🥇", "🥈", "🥉"]
    for rank, (emoji_sym, count) in enumerate(sorted_emoji[:10]):
        prefix = medals[rank] if rank < 3 else f" {rank+1}."
        b = bar(count, max_emoji)
        pct = count / total_all * 100
        lines.append(f"  {prefix} {emoji_sym}  {b}  {fmt_num(count):>6}  {pct:.1f}%")
 
    lines.append(f"\n{'─'*30}")
    lines.append(f"  📦 Итого: {fmt_num(total_all)} реакций")
 
    await update.message.reply_text("\n".join(lines))
 
 
async def cmd_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [f"🔥  ГОРЯЧИЕ ПОСТЫ — {CACHE['channel']}\n"]
    medals = ["🥇", "🥈", "🥉", "4.", "5."]
 
    for rank, (total, msg_id, date, preview) in enumerate(CACHE["top_posts"][:5]):
        medal = medals[rank]
        lines.append(f"{medal}  {fmt_num(total)} реакций  ·  {date}")
        lines.append(f"    {preview}")
        lines.append("")
 
    await update.message.reply_text("\n".join(lines))
 
 
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = CACHE
    pct_r = c["msgs_with_reactions"] / c["total_messages"] * 100 if c["total_messages"] else 0
    avg = c["total_reactions"] // max(c["msgs_with_reactions"], 1)
 
    # Топ-3 реакции для превью
    emoji_totals = {k: v for k, v in c["totals"].items() if k not in ("PAID", "CUSTOM")}
    top3 = sorted(emoji_totals.items(), key=lambda x: x[1], reverse=True)[:3]
    top3_str = "  ".join(f"{e} {fmt_num(n)}" for e, n in top3)
 
    lines = [
        f"📊  СТАТИСТИКА — {c['channel']}",
        f"{'─'*32}",
        f"  📨 Сообщений:      {c['total_messages']:,}",
        f"  💬 С реакциями:    {c['msgs_with_reactions']:,}  ({pct_r:.0f}%)",
        f"  ❤️  Всего реакций:  {fmt_num(c['total_reactions'])}",
        f"  📈 Среднее/пост:   {fmt_num(avg)}",
        f"{'─'*32}",
        f"  Топ эмодзи:  {top3_str}",
    ]
 
    await update.message.reply_text("\n".join(lines))
 
 
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("posts", cmd_posts))
    app.add_handler(CommandHandler("stats", cmd_stats))
    print(f"🤖 Бот запущен | {CACHE['channel']} | {CACHE['total_messages']} сообщений")
    app.run_polling()
 
 
if __name__ == "__main__":
    main()
 