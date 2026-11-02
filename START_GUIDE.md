# Запуск Magic Academy на Windows

## 0. Что уже проверено

Читайте `docs/VERIFICATION.md`: Python-код и HTTP-тесты проверены, но запуск PostgreSQL,
сборка контейнеров, сохранность Docker volume и целевое нагрузочное тестирование в Work
не выполнены. В проекте есть команды для этих проверок. Не выдавайте пропуски за успешные тесты.

## 1. Установить программы

1. Python **3.12 x64** с python.org; при установке включить Python Launcher и Add Python to PATH.
2. Git for Windows с git-scm.com.
3. Visual Studio Code с code.visualstudio.com, расширение Python от Microsoft.
4. Docker Desktop для Windows с docker.com. Использовать Linux containers и WSL 2 backend.
   Если Windows просит WSL: запустить PowerShell от администратора, выполнить `wsl --install`,
   перезагрузить ПК и закончить установку Docker Desktop.

Открыть Docker Desktop и дождаться сообщения о работающем Engine. Для первой установки
зависимостей и загрузки образов нужен интернет. Не устанавливайте PostgreSQL отдельно:
официальный образ запустится через Compose.

```powershell
py -3.12 --version
git --version
docker version
docker compose version
```

`docker version` должен показывать Client **и Server**, а не только Client.
Ошибка daemon означает, что Docker Desktop не запущен или WSL/виртуализация не готовы.

## 2. Открыть проект и создать конфигурации

Распаковать MagicAcademy.zip, открыть папку **MagicAcademy** в VS Code через File → Open Folder.
В Terminal → New Terminal выбрать PowerShell. Все команды ниже выполняются из папки,
где находятся `docker-compose.yml` и `README.md`, не из `app`.

```powershell
py -3.12 scripts/configure.py
```

Создаются `.env.sandbox`, `.env.production` и `.env` со случайными паролями и JWT-ключами.
Существующие файлы не перезаписываются. `.env` — копия sandbox для Compose; это не ссылка.
При ручном изменении `.env.sandbox` нужно обновить `.env` отдельно. Не отправляйте эти файлы в Git.
Файлы `.example` служат образцами, их placeholder-значения запускать нельзя.
Пароли генератора состоят из hex-символов: они безопасны для включения в URL без кодирования.

## 3. Запустить одной командой

```powershell
docker compose up --build
```

Первый запуск может занять несколько минут. PostgreSQL сначала проходит healthcheck,
затем API создаёт таблицы и запускается. В другом терминале:

```powershell
docker compose ps
```

У `db` и `api` ожидается статус healthy. Открыть:

- http://localhost:8000/ — стартовая страница;
- http://localhost:8000/health — status ok и environment sandbox;
- http://localhost:8000/docs — Swagger UI.

Можно запускать в фоне: `docker compose up --build -d`. Логи: `docker compose logs --tail 100 api db`.
Swagger использует внешние CDN-ресурсы; если UI пустой без интернета, сам API может работать.
JSON-схема доступна на `/openapi.json`, HTTP можно проверять PowerShell-командами ниже.

## 4. Создать администратора

```powershell
docker compose exec api python -m app.manage admin
```

Ввести дважды свой пароль длиной от 10 символов. Ввод скрыт — это нормально.
Повторное создание существующего имени запрещено. Пользователя через публичную регистрацию
нельзя сделать ADMIN. Пароль нигде не записывается открытым текстом.

## 5. Демонстрация Swagger от начала до конца

1. Пока не нажимали Authorize, выполнить GET `/users/me`: ожидается **401**.
2. В POST `/auth/register` → Try it out ввести:

```json
{"username":"student_one","password":"Learning-Only-Password-42"}
```

Это пример учебного пароля, не пароль вашей реальной учётной записи. Ответ **201**, роль USER.
3. Зарегистрировать `student_two` с другим выбранным паролем.
4. Нажать **Authorize** вверху Swagger. Ввести username `student_one` и его password.
   client_id/client_secret оставить пустыми. Swagger сам вызывает `/auth/token`.
5. GET `/users/me` → **200**. Запомнить id первого пользователя.
6. GET `/user/home` → **200**, HTML-заглушка. GET `/admin/home` → **403**.
7. PATCH `/users/{user_id}` с id второго пользователя и `{"display_name":"Changed"}` → **403**.
   Со своим id и `{"display_name":"First student"}` → **200**.
8. Authorize → Logout. Войти как `admin` с паролем, заданным командой создания.
9. GET `/admin/home` → **200**. POST `/admin/courses`:

```json
{"title":"Teleportation","capacity":1}
```

Ответ **201**; сохранить course id. GET `/courses` показывает available_seats = 1.
10. Выйти из admin, войти как student_one. POST `/courses/{course_id}/enroll` → **201**.
    Повторить → **409 Already enrolled**. GET `/enrollments/me` показывает запись.
11. Сохранить id записи. Войти как student_two, GET `/enrollments/{id}` → **403**.
    Собственный GET `/enrollments/me` вернёт пустой список. Запись на тот же курс → **409 Course is full**.
12. Выполнить POST `/auth/token` с неправильным паролем → **401**.

Профили принимают только display_name; передача role в PATCH или регистрации возвращает 422.
Защищённые HTML-заглушки удобно демонстрировать в Swagger: обычная адресная строка браузера
не отправляет Bearer-токен автоматически и покажет 401. Это ожидаемо.

## 6. Python-окружение, Ruff, pytest и pre-commit

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q app tests scripts load
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q
```

Последняя команда без TEST_DATABASE_URL использует SQLite для быстрых HTTP/ORM-тестов
и пропускает 3 PostgreSQL-теста. Это **не** проверка конкурентной записи PostgreSQL.
Для полноценного запуска на PostgreSQL:

```powershell
.\.venv\Scripts\python.exe scripts/run_tests.py
```

Скрипт переключит sandbox на dev-конфигурацию, откроет БД только на 127.0.0.1:5433,
создаст `magic_test` и запустит все тесты. Результат — `results/pytest_postgres.xml`.
Ожидаемый критерий — все тесты проходят, без PostgreSQL-skips. В Work такой результат не получен.

Тесты пересоздают таблицы magic_test. Скрипт откажется работать, если .env указывает production.
Не запускайте несколько наборов PostgreSQL-тестов параллельно на одной magic_test.

Установка и демонстрация хука:

```powershell
.\.venv\Scripts\python.exe -m pre_commit install
$env:Path = "$PWD\.venv\Scripts;$env:Path"
.\.venv\Scripts\python.exe -m pre_commit run --all-files
.\.venv\Scripts\python.exe scripts/demo_precommit.py
```

Последний скрипт создаёт временный Git-репозиторий: неверный стиль → отказ, синтаксическая
ошибка → отказ, исправленный код → успешный коммит. Основной проект он не портит.
Неактивный virtualenv может помешать system-hook найти Ruff: команда изменения Path выше
решает это для текущего PowerShell. Локальные хуки не переносятся автоматически при клонировании.

## 7. Нагрузочное тестирование Locust

Сначала создать администратора и убедиться, что sandbox работает. Если ранее запускали dev,
вернуться к обычному режиму **без hot-reload**, чтобы не искажать нагрузку:

```powershell
docker compose up --build -d --force-recreate
.\.venv\Scripts\python.exe scripts/run_load.py normal
.\.venv\Scripts\python.exe scripts/run_load.py spike
```

Каждый скрипт спросит имя и пароль администратора. Создание 50 пользователей занимает время,
после него начинается собственно 60-секундный тест. У normal 10 VUsers и разгон 5 с;
у spike 50 VUsers, разгон 5 с и общий момент записи на t=15 с.
Во время теста не перезапускайте приложение, не запускайте pytest и не изменяйте код.

Результаты лежат в `results/local/normal_ДАТА/` и `results/local/spike_ДАТА/`:

- `SUMMARY.md`, `summary.json` — RPS, mean/min/max/p95, ошибки и CPU/RAM;
- `locust.html` — HTML-отчёт;
- `latency_rps.png` — графики из реально записанного CSV;
- `load_stats.csv`, `load_stats_history.csv` — исходные данные;
- `resources.csv` — измерения api и db;
- `outcomes.json` — 201 и ожидаемые 409 отдельно;
- `metadata.json` — условия, результат проверки вместимости и ошибки сбора ресурсов;
- `locust.log` — диагностический журнал.

Если CPU/RAM не собраны, не ставьте 0: пишите «не измерено» и смотрите resource_errors.
Неожиданные ошибки Locust дают ненулевой код завершения. 409 из-за заполнения курса ожидаемы,
поэтому не считаются техническими ошибками; их нужно показать отдельно преподавателю.
Графики и таблицы после запуска вставить в Lab4_Report.docx вместо раздела ожидающих измерений.
Исходный отчёт честно фиксирует, что целевой эксперимент в Work не проведён.

Для повторной обработки существующего запуска:

```powershell
.\.venv\Scripts\python.exe scripts/summarize_load.py results/local/spike_ВАША_ДАТА
```

## 8. Проверка сохранности данных

Полностью автоматическая проверка сборки, API, SQL и пересоздания контейнеров:

```powershell
.\.venv\Scripts\python.exe scripts/verify_docker.py
```

Она создаёт отдельный временный Compose-проект с отдельным volume и свободным портом.
Результат — `results/docker_verification.json`. После проверки удаляется только временный проект.
Основной sandbox и его данные скрипт не удаляет.

Для наглядной ручной демонстрации запомнить id зарегистрированного пользователя, затем:

```powershell
docker compose down
docker compose up -d --wait
```

Снова войти с прежним паролем: GET `/users/me` должен вернуть прежний id, а записи — сохраниться.
SQL-проверка из контейнера:

```powershell
docker compose exec db psql -U academy -d magic_sandbox -c "SELECT id, username, role FROM users;"
docker compose exec db psql -U academy -d magic_sandbox -c "SELECT * FROM enrollments;"
```

Обычный `down` сохраняет volume. **`down -v` удаляет volume и все данные данной среды** —
это не команда обычной остановки. `docker compose stop` просто останавливает контейнеры.

## 9. Production и режим разработки

```powershell
docker compose --env-file .env.production -p magic-production up --build -d
```

Production API: http://localhost:8001/docs, БД magic_production, отдельный volume.
Создание администратора аналогично, но добавьте `--env-file .env.production -p magic-production`
перед `exec`. Остановка production использует те же флаги перед `down`.
Приложение привязано к localhost; публичное развёртывание, HTTPS и rate limiting не входят в этот MVP.

Dev с bind mounts и reload:

```powershell
docker compose -f docker-compose.yml -f compose.dev.yml up --build
```

Изменить текст заголовка в `app/main.py`, сохранить файл и обновить страницу.
Uvicorn перечитает код без сборки образа. Изменение зависимостей требует новой сборки.
Для обычного режима снова выполнить `docker compose up --build -d --force-recreate`.

Native API без контейнера приложения (БД всё ещё Docker):

```powershell
docker compose -f docker-compose.yml -f compose.dev.yml up -d db
$env:APP_ENV = "sandbox"
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8002
```

Он читает `.env.sandbox` и подключается к localhost:5433. Убедитесь, что пароли .env и
.env.sandbox совпадают. Для нагрузки на native API используйте --host http://127.0.0.1:8002
и --pid с PID Python-процесса; при таком режиме CPU/RAM БД нужно собирать отдельно или передать --db-pid.

## 10. GitHub Actions

На GitHub создать пустой репозиторий и отправить проект обычным git push (это действие здесь не выполнено).
Указать своё имя и email в локальном git config, настроить remote origin. Не добавлять .env.
Workflow `.github/workflows/ci.yml` запускается при push main и pull_request:
установка → pip check → Ruff → pytest с PostgreSQL service → Compose config → Docker persistence check.
Вкладка Actions показывает фактический статус, артефакт verification-results содержит результаты.
CI-пароль в YAML — публичный одноразовый пароль изолированной тестовой БД, не реальный секрет.

## 11. Команды для преподавателя

```powershell
git log --oneline
.\.venv\Scripts\python.exe scripts/demo_precommit.py
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe scripts/run_tests.py
docker compose ps
.\.venv\Scripts\python.exe scripts/run_load.py spike
.\.venv\Scripts\python.exe scripts/verify_docker.py
```

Перед защитой выполнить длинные установки и первый build. На защите показать исходные CSV,
график и журнал своего запуска, а не только рассказать об ожидаемом результате.

## 12. Если что-то не запускается

- Порт 8000 занят: поменять API_PORT в `.env`, адрес Swagger также изменится.
- Порт 5433 занят: остановить конфликтующий сервис либо согласованно изменить dev mapping и URL тестов.
- `ModuleNotFoundError`: использовать именно `.venv\Scripts\python.exe`, переустановить requirements-dev.
- `password authentication failed` после изменения .env: volume содержит старый пароль;
  восстановить прежнюю конфигурацию или явно изменить пароль роли в БД. Не удалять volume с нужными данными.
- Страница admin даёт 403: войти под созданным ADMIN, а не обычным пользователем с именем admin.
- Тесты skip: без TEST_DATABASE_URL так задумано; использовать scripts/run_tests.py.
- `/health` не 200: посмотреть логи db и api, статус healthcheck, соответствие APP_ENV и имени БД.
