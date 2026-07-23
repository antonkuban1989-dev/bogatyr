import json
import os
import datetime
from flask import Flask, request, redirect

app = Flask(__name__)
DATA_FILE = "tasks.json"
META_FILE = "meta.json"   # тут храним списки категорий и исполнителей

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
RU_DAYS = ["понедельник","вторник","среда","четверг","пятница","суббота","воскресенье"]
DEFAULT_COLORS = {"WB": "#7b2ff7", "Пилатес": "#e84393", "Дом": "#0984e3", "Личное": "#00b894"}
PALETTE = ["#7b2ff7","#e84393","#0984e3","#00b894","#f39c12","#e74c3c","#16a085","#8e44ad","#2980b9","#d35400"]

TIMES = [f"{h:02d}:{m:02d}" for h in range(6, 24) for m in (0, 15, 30, 45)]

# ---------- хранение задач ----------
def load_tasks():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_tasks(tasks):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

# ---------- хранение категорий и исполнителей ----------
def load_meta():
    if os.path.exists(META_FILE):
        with open(META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"cats": dict(DEFAULT_COLORS), "execs": ["Антон", "Саша"]}

def save_meta(meta):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

# ---------- показывать ли задачу в конкретный день ----------
def shows_on(task, date):
    d_iso = date.isoformat()
    if d_iso in task.get("cancelled", []):      # это вхождение точечно удалено
        return False
    if task["type"] == "once":
        return task.get("date") == d_iso
    # повторяющаяся
    until = task.get("until")
    if until and d_iso > until:                 # цепочка завершена этой датой
        return False
    return date.weekday() in task.get("weekdays", [])

def date_range(period, start):
    n = {"today": 1, "week": 7, "month": 30, "year": 365}.get(period, 1)
    return [start + datetime.timedelta(days=i) for i in range(n)]

@app.route("/")
def home():
    tasks = load_tasks()
    meta = load_meta()
    colors = meta["cats"]
    execs = meta["execs"]

    period = request.args.get("period", "year")
    who = request.args.get("who", "Все")
    cat_filter = request.args.get("cat", "Все")
    sort = request.args.get("sort", "date")

    start = datetime.date.today()
    if period == "custom":
        try:
            p_from = datetime.date.fromisoformat(request.args.get("from"))
            p_to = datetime.date.fromisoformat(request.args.get("to"))
            dates = [p_from + datetime.timedelta(days=i) for i in range((p_to - p_from).days + 1)]
        except (ValueError, TypeError):
            dates = [start]
    else:
        dates = date_range(period, start)

    items = []
    for d in dates:
        for t in tasks:
            if (who == "Все" or t.get("executor") == who) and \
               (cat_filter == "Все" or t.get("cat") == cat_filter) and \
               shows_on(t, d):
                items.append((d, t))

    if sort == "cat":
        items.sort(key=lambda x: (x[1]["cat"], x[0], x[1].get("time") or "99:99"))
    elif sort == "time":
        items.sort(key=lambda x: (x[0], x[1].get("time") or "99:99"))  # без времени — в конец
    else:
        items.sort(key=lambda x: (x[0], x[1].get("time") or "99:99", x[1]["cat"]))

    show_dates = period != "today"
    rows = ""
    last_date = None
    for d, t in items:
        d_iso = d.isoformat()
        if show_dates and d != last_date:
            rows += f'<div style="color:#7b7b8a;font-size:13px;margin:16px 0 4px;">{d.strftime("%d.%m")} · {RU_DAYS[d.weekday()]}</div>'
            last_date = d
        is_done = d_iso in t.get("done_dates", [])
        style = "text-decoration:line-through;opacity:0.5;" if is_done else ""
        color = colors.get(t["cat"], "#555")
        time_badge = f'<span style="color:#c9c9d6;font-size:13px;font-variant-numeric:tabular-nums;">{t["time"]}</span>' if t.get("time") else ''
        # кнопка удаления: для повторяющейся — с выбором, для разовой — сразу
        if t["type"] == "recurring":
            del_btn = f'''<form method="POST" action="/delete/{t['id']}" style="margin:0;" onsubmit="return delRec(this)">
                <input type="hidden" name="date" value="{d_iso}"><input type="hidden" name="scope" value="">
                <button type="submit" style="background:none;border:none;color:#666;font-size:20px;cursor:pointer;">&times;</button></form>'''
        else:
            del_btn = f'''<form method="POST" action="/delete/{t['id']}" style="margin:0;">
                <button style="background:none;border:none;color:#666;font-size:20px;cursor:pointer;">&times;</button></form>'''
        rows += f'''
        <div style="display:flex;align-items:center;gap:10px;padding:12px 15px;margin:6px 0;background:#1e1e2e;border-radius:12px;{style}">
            <form method="POST" action="/toggle/{t['id']}" style="margin:0;">
                <input type="hidden" name="date" value="{d_iso}">
                <button style="width:24px;height:24px;border-radius:50%;border:2px solid {color};background:{'#00b894' if is_done else 'transparent'};cursor:pointer;"></button>
            </form>
            {time_badge}
            <span style="flex:1;color:#eee;font-size:16px;">{t['text']}</span>
            <span style="color:#888;font-size:12px;">{t.get('executor','')}</span>
            <span style="background:{color};color:#fff;padding:3px 9px;border-radius:20px;font-size:12px;">{t['cat']}</span>
            {del_btn}
        </div>'''
    if not rows:
        rows = '<p style="color:#666;text-align:center;padding:20px;">Задач нет</p>'

    def chips(name, current, values):
        out = ""
        for v, lbl in values:
            act = "background:#7b2ff7;color:#fff;" if v == current else "background:#1e1e2e;color:#888;"
            params = {"period": period, "who": who, "cat": cat_filter, "sort": sort, name: v}
            qs = "&".join(f"{k}={params[k]}" for k in params)
            out += f'<a href="/?{qs}" style="{act}text-decoration:none;padding:7px 13px;border-radius:18px;font-size:13px;margin:0 5px 5px 0;display:inline-block;">{lbl}</a>'
        return out

    period_chips = chips("period", period, [("today","Сегодня"),("week","Неделя"),("month","Месяц"),("year","Год"),("custom","Период")])
    who_chips = chips("who", who, [("Все","Все")] + [(e, e) for e in execs])
    cat_chips = chips("cat", cat_filter, [("Все","Все категории")] + [(c, c) for c in colors])
    sort_chips = chips("sort", sort, [("date","по дате"),("time","по времени"),("cat","по категории")])

    custom_form = ""
    if period == "custom":
        custom_form = f'''<form method="GET" action="/" style="display:flex;gap:8px;align-items:center;margin-bottom:14px;flex-wrap:wrap;">
            <input type="hidden" name="period" value="custom"><input type="hidden" name="who" value="{who}"><input type="hidden" name="cat" value="{cat_filter}"><input type="hidden" name="sort" value="{sort}">
            <span style="color:#888;font-size:13px;">с</span><input type="date" name="from" style="padding:7px;border-radius:8px;border:none;background:#1e1e2e;color:#eee;">
            <span style="color:#888;font-size:13px;">по</span><input type="date" name="to" style="padding:7px;border-radius:8px;border:none;background:#1e1e2e;color:#eee;">
            <button style="padding:7px 14px;border-radius:8px;border:none;background:#7b2ff7;color:#fff;cursor:pointer;">Показать</button></form>'''

    cat_opts = "".join(f'<option value="{c}">{c}</option>' for c in colors)
    exec_opts = "".join(f'<option value="{e}">{e}</option>' for e in execs)
    time_opts = "".join(f'<option value="{tm}">{tm}</option>' for tm in TIMES)
    wd_checks = "".join(f'<label style="color:#aaa;font-size:13px;margin-right:10px;white-space:nowrap;"><input type="checkbox" name="wd" value="{i}"> {w}</label>' for i, w in enumerate(WEEKDAYS))
    plus = 'width:38px;height:38px;border-radius:10px;border:none;background:#2a2a3a;color:#fff;font-size:20px;cursor:pointer;flex:none;'

    return f'''
    <html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Богатырь</title></head>
    <body style="font-family:sans-serif;background:#11111b;margin:0;padding:20px;max-width:660px;margin:auto;">
        <h1 style="color:#fff;margin-bottom:12px;">💪 Богатырь</h1>
        <div style="margin-bottom:6px;">{period_chips}</div>
        {custom_form}
        <div style="margin-bottom:6px;">{who_chips}</div>
        <div style="margin-bottom:6px;">{cat_chips}</div>
        <div style="margin-bottom:16px;color:#666;font-size:12px;">Сортировка: {sort_chips}</div>

        <details style="background:#181825;border-radius:12px;padding:12px 16px;margin-bottom:16px;">
          <summary style="color:#aaa;cursor:pointer;">+ Добавить задачу</summary>
          <form method="POST" action="/add" style="margin-top:12px;display:flex;flex-direction:column;gap:10px;">
            <input name="text" placeholder="Название задачи..." required style="padding:10px;border-radius:8px;border:none;background:#1e1e2e;color:#eee;">

            <div style="display:flex;gap:8px;align-items:center;">
              <select name="cat" style="flex:1;padding:10px;border-radius:8px;border:none;background:#1e1e2e;color:#eee;">{cat_opts}</select>
              <button type="button" onclick="addCat()" style="{plus}">+</button>
            </div>
            <div style="display:flex;gap:8px;align-items:center;">
              <select name="executor" style="flex:1;padding:10px;border-radius:8px;border:none;background:#1e1e2e;color:#eee;">{exec_opts}</select>
              <button type="button" onclick="addExec()" style="{plus}">+</button>
            </div>

            <label style="color:#aaa;font-size:14px;"><input type="checkbox" onchange="document.getElementById('recBox').style.display=this.checked?'block':'none'"> Повторяющаяся</label>
            <div id="recBox" style="display:none;background:#141420;border-radius:8px;padding:10px;">
              <div style="color:#666;font-size:12px;margin-bottom:6px;">Дни недели:</div>
              <div>{wd_checks}</div>
              <div style="color:#666;font-size:12px;margin:10px 0 4px;">До какой даты (пусто = 5 лет):</div>
              <input type="date" name="until" style="padding:8px;border-radius:8px;border:none;background:#1e1e2e;color:#eee;">
            </div>

            <div id="onceBox">
              <div style="color:#666;font-size:12px;margin-bottom:4px;">Дата (для разовой):</div>
              <input type="date" name="date" style="padding:8px;border-radius:8px;border:none;background:#1e1e2e;color:#eee;">
            </div>

            <label style="color:#aaa;font-size:14px;"><input type="checkbox" onchange="document.getElementById('timeBox').style.display=this.checked?'block':'none'"> Указать время</label>
            <div id="timeBox" style="display:none;">
              <select name="time" style="padding:10px;border-radius:8px;border:none;background:#1e1e2e;color:#eee;width:100%;">{time_opts}</select>
            </div>

            <button style="padding:10px;border-radius:8px;border:none;background:#7b2ff7;color:#fff;cursor:pointer;">Добавить</button>
          </form>
        </details>
        {rows}

        <script>
        function addCat(){{
            var name = prompt("Название новой категории:");
            if(name){{ window.location = "/add_cat?name=" + encodeURIComponent(name); }}
        }}
        function addExec(){{
            var name = prompt("Имя нового исполнителя:");
            if(name){{ window.location = "/add_exec?name=" + encodeURIComponent(name); }}
        }}
        function delRec(form){{
            var ans = prompt("Удалить: 1 — только это вхождение, 2 — всю цепочку (выполненные останутся). Введите 1 или 2:");
            if(ans !== "1" && ans !== "2"){{ return false; }}
            form.scope.value = (ans === "2") ? "chain" : "one";
            return true;
        }}
        </script>
    </body></html>'''

@app.route("/toggle/<int:task_id>", methods=["POST"])
def toggle(task_id):
    tasks = load_tasks()
    date = request.form.get("date")
    for t in tasks:
        if t["id"] == task_id:
            dd = t.setdefault("done_dates", [])
            dd.remove(date) if date in dd else dd.append(date)
    save_tasks(tasks)
    return redirect(request.referrer or "/")

@app.route("/add", methods=["POST"])
def add():
    tasks = load_tasks()
    text = request.form.get("text", "").strip()
    if text:
        is_rec = request.form.getlist("wd")  # если отмечены дни — считаем повторяющейся
        ttype = "recurring" if is_rec else "once"
        until = request.form.get("until") or None
        if ttype == "recurring" and not until:
            until = (datetime.date.today() + datetime.timedelta(days=365*5)).isoformat()
        tasks.append({
            "id": max([t["id"] for t in tasks], default=0) + 1,
            "text": text,
            "cat": request.form.get("cat", "Личное"),
            "executor": request.form.get("executor", "Антон"),
            "type": ttype,
            "weekdays": [int(x) for x in is_rec],
            "date": request.form.get("date") if ttype == "once" else None,
            "until": until,
            "time": request.form.get("time") or None,
            "cancelled": [],
            "done_dates": [],
        })
        save_tasks(tasks)
    return redirect(request.referrer or "/")

@app.route("/delete/<int:task_id>", methods=["POST"])
def delete(task_id):
    tasks = load_tasks()
    scope = request.form.get("scope", "")
    date = request.form.get("date")
    if scope == "one" and date:
        # убрать только это вхождение
        for t in tasks:
            if t["id"] == task_id:
                t.setdefault("cancelled", []).append(date)
    elif scope == "chain" and date:
        # завершить цепочку вчерашним днём — будущее исчезнет, прошлое (выполненное) останется
        for t in tasks:
            if t["id"] == task_id:
                t["until"] = (datetime.date.fromisoformat(date) - datetime.timedelta(days=1)).isoformat()
    else:
        # разовая — удалить совсем
        tasks = [t for t in tasks if t["id"] != task_id]
    save_tasks(tasks)
    return redirect(request.referrer or "/")

@app.route("/add_cat")
def add_cat():
    name = request.args.get("name", "").strip()
    if name:
        meta = load_meta()
        if name not in meta["cats"]:
            meta["cats"][name] = PALETTE[len(meta["cats"]) % len(PALETTE)]
            save_meta(meta)
    return redirect("/")

@app.route("/add_exec")
def add_exec():
    name = request.args.get("name", "").strip()
    if name:
        meta = load_meta()
        if name not in meta["execs"]:
            meta["execs"].append(name)
            save_meta(meta)
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
