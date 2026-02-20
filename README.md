# Деплой: страница /simple и сервер

Минимальный набор для **GitHub** и **Render**. Все шаги ниже выполняются **внутри этой папки** (`deploy`).

---

## Что внутри папки deploy

| Файл | Назначение |
|------|------------|
| `server.py` | HTTP-сервер: `/simple`, `/kp`, API чата и карт |
| `simple_floor_plan.html` | Страница **/simple** (планировка + чат) |
| `page_prototype.html` | Страница **/kp** |
| `rag_system.py` | RAG для чата |
| `cost_logger.py` | Логирование стоимости |
| `requirements.txt` | Зависимости Python |
| `render.yaml` | Конфиг для Render |
| `.gitignore` | Исключения для Git |

---

## Часть 1. Копирование в GitHub

**Важно:** все команды выполняйте из папки `deploy` (перейдите в неё: `cd deploy` или откройте папку «Ссылка на deploy (для GitHub и Render)»).

### Шаг 1. Создать репозиторий на GitHub

1. Зайдите на [github.com](https://github.com), войдите в аккаунт.
2. **New repository** (или «+» → New repository).
3. Название — например `kp-simple` или любое.
4. **Не** ставьте галочки «Add a README», «Add .gitignore» — они уже есть в папке `deploy`.
5. Нажмите **Create repository**.

### Шаг 2. Залить содержимое папки deploy

В терминале:

```bash
# Перейти в папку deploy (полный путь у вас может отличаться)
cd "/Users/annarybkina/Desktop/Allio/ИИ КП/deploy"

# Инициализировать репозиторий
git init

# Добавить все файлы ( .env не попадёт — он в .gitignore )
git add .
git status

# Первый коммит
git commit -m "Deploy: server and simple page"

# Ветка main
git branch -M main

# Подключить репозиторий (подставьте свой логин и имя репозитория)
git remote add origin https://github.com/VASH_LOGIN/VASH_REPO.git

# Отправить на GitHub
git push -u origin main
```

Замените `VASH_LOGIN` и `VASH_REPO` на ваш логин GitHub и имя созданного репозитория. Если GitHub попросит авторизацию — войдите (логин/пароль или токен).

После этого в репозитории на GitHub будет только то, что лежит в папке `deploy`.

---

## Часть 2. Деплой на Render

### Вариант A: через Blueprint (если репозиторий уже на GitHub)

1. Зайдите на [render.com](https://render.com), войдите (можно через GitHub).
2. **New** → **Blueprint**.
3. Подключите репозиторий с залитой папкой `deploy` (важно: в репозитории должны быть файлы из `deploy` в **корне** репо — т.е. вы пушили из папки `deploy`, и там в корне лежат `server.py`, `requirements.txt` и т.д.).
4. Render подхватит `render.yaml`. Нажмите **Apply**.
5. В **Environment** добавьте переменную **OPENAI_API_KEY** (тип **Secret**) — значение вашего ключа OpenAI для чата.
6. Сохраните. Дождитесь окончания деплоя.

### Вариант B: вручную (Web Service)

1. [render.com](https://render.com) → **New** → **Web Service**.
2. Подключите тот же GitHub-репозиторий (где в корне лежит содержимое `deploy`).
3. Настройки:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python server.py`
4. **Environment** → **Add Environment Variable**: ключ `OPENAI_API_KEY`, значение — ваш API-ключ (можно отметить как Secret).
5. **Create Web Service**. Дождитесь деплоя.

### После деплоя

Страница будет доступна по адресу вида:

**https://ВАШ_СЕРВИС.onrender.com/simple**

(имя сервиса вы задаёте при создании или Render присвоит его сам.)

---

## Локальный запуск (из папки deploy)

```bash
cd "/Users/annarybkina/Desktop/Allio/ИИ КП/deploy"
pip install -r requirements.txt
python server.py
```

Откройте в браузере: **http://localhost:5002/simple**

Для работы чата создайте в папке `deploy` файл `.env` с строкой `OPENAI_API_KEY=sk-...` (или задайте переменную окружения).
