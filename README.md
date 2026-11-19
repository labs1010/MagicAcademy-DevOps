# Magic Academy — лабораторні 1–5

Python 3.12 · FastAPI · PostgreSQL 16 · SQLAlchemy · Locust · Docker Compose.
Офіційний варіант: «Креативний Sci-Fi та Фентезі», №2.

## Швидкий старт Windows

```powershell
py -3.12 scripts/configure.py
docker compose up --build
```

Перед цим встановіть Python 3.12 та Docker Desktop і дочекайтеся запуску Linux engine.
Після одноразової генерації конфігурацій система запускається **однією командою** `docker compose up --build`.
Swagger: http://localhost:8000/docs. Перевірка БД: http://localhost:8000/health.
Адміністратор: в іншому терміналі `docker compose exec api python -m app.manage admin`.
Пароль вводиться інтерактивно; стандартного пароля адміністратора немає.

## Два середовища

Sandbox використовує `.env` (копію `.env.sandbox`) і БД `magic_sandbox`.
Production запускається окремим Compose-проєктом, порт 8001, власний volume та БД:

```powershell
docker compose --env-file .env.production -p magic-production up --build -d
```

Це локальна production-конфігурація, а не опублікований інтернет-сервіс.
При локальному запуску Python `APP_ENV` обирає `.env.sandbox` або `.env.production`.
Реальні env-змінні мають пріоритет. Клас Settings забороняє production з sandbox-БД.
Детальні traceback-відповіді вимкнено в обох середовищах; `Settings.debug` у production — False.

## Де шукати пояснення

- [START_GUIDE.md](START_GUIDE.md) — покроковий запуск Windows і сценарій демонстрації.
- [DEFENSE_GUIDE_RU.md](DEFENSE_GUIDE_RU.md) — пояснення, 28 питань, план на дві години.
- [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) — усі пункти методичок і бали.
- [docs/VERIFICATION.md](docs/VERIFICATION.md) — реальний обсяг перевірок та обмеження.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — архітектура та захист від race condition.
- [docs/LOAD_PLAN.md](docs/LOAD_PLAN.md) — профілі навантаження й трактування метрик.
- [docs/SCHEMA.md](docs/SCHEMA.md) — структура та ініціалізація БД.
- `reports/` — п'ять окремих звітів Word.

## Перевірки

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/run_tests.py
.\.venv\Scripts\python.exe scripts/verify_docker.py
```

Звичайний pytest без TEST_DATABASE_URL виконує HTTP/ORM-тести на SQLite, а PostgreSQL-тести
явно пропускає. `run_tests.py` запускає dev-stack і всі тести на окремій БД `magic_test`.
Ці тести видаляють таблиці **тільки magic_test**; не використовуйте для неї цінні дані.
`verify_docker.py` створює тимчасовий Compose-проєкт і перевіряє збереження користувача
після `down`/`up`, після чого видаляє лише власний тестовий volume.

## Git та хуки

Архів містить локальний Git-репозиторій. Після розпакування встановіть хук для свого Python:

```powershell
.\.venv\Scripts\python.exe -m pre_commit install
.\.venv\Scripts\python.exe -m pre_commit run --all-files
.\.venv\Scripts\python.exe scripts/demo_precommit.py
```

В активованому virtualenv команда `git commit` блокується при помилках Ruff.
У репозиторії немає реальних секретів; `.env*` з паролями ігноруються.
Після публікації репозиторію на GitHub workflow автоматично працює для PR та push у main.
Публікацію на GitHub і виконання hosted Actions тут не здійснювали.

## DevOps №2 — Continuous Integration

Из корня проекта в PowerShell с запущенным Docker Desktop:

```powershell
py -3.12 scripts/configure.py
docker compose up --build -d --wait
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod "http://localhost:8010/groups?students=21&group_size=10"
```

Планировщик вернёт три группы. Для проверки тестов обоих сервисов:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python scripts/run_tests.py
.\.venv\Scripts\python -m pytest -q planner/test_planner.py
```

### Публикация и проверка образов

Включите GitHub Actions в репозитории. Job публикации запрашивает
`packages: write` для встроенного `GITHUB_TOKEN`. Политика организации должна
разрешать запись в GHCR. Для уже существующего пакета дайте репозиторию
доступ Write в настройках пакета. После успешного push откройте оба пакета в
GitHub Packages и скопируйте полный SHA коммита из запуска Actions.

Для проверки скачанных образов выполните в новом окне PowerShell из корня
проекта с уже созданным локальным файлом .env. Введите owner/repo строчными
буквами. Для приватных пакетов предварительно войдите через docker login ghcr.io
с именем GitHub и токеном с правом read:packages.

```powershell
$repo = (Read-Host "GitHub owner/repo").ToLowerInvariant()
$sha = Read-Host "Full commit SHA"
$env:API_IMAGE = "ghcr.io/${repo}-api:${sha}"
$env:PLANNER_IMAGE = "ghcr.io/${repo}-planner:${sha}"
docker pull $env:API_IMAGE
docker pull $env:PLANNER_IMAGE
docker compose up --no-build --force-recreate -d --wait
docker compose images
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod "http://localhost:8010/groups?students=21&group_size=10"
```

### Защита main и демонстрация

1. После первого успешного запуска CI откройте Settings → Branches →
   Add classic branch protection rule. Укажите main.
2. Включите Require a pull request before merging и Require status checks to
   pass before merging. Выберите API checks, Planner checks и Docker build.
   Для самостоятельной работы можно оставить число обязательных одобрений равным нулю.
3. Включите Do not allow bypassing the above settings. Сохраните правило.
4. Для демонстрации создайте ветку demo/blocked-pr. В planner/test_planner.py
   замените ожидаемое значение в паре (21, 3) на (21, 2). Отправьте изменение
   в свою ветку и откройте PR в main. Покажите ошибку Planner checks и блокировку
   слияния. Верните (21, 3) следующим коммитом и покажите повторный запуск.
