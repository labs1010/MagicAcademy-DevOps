# Фактична перевірка 2026-11-02

## Підтверджено в Work

| Перевірка | Результат | Доказ |
|---|---|---|
| Встановлення Python-залежностей | Успішне у чистому Python 3.12 venv | results/installed_versions.txt |
| Сумісність залежностей | pip check PASS | results/dependencies.txt |
| Синтаксис 21 Python-файлу | compileall PASS | Команда виконана без помилок |
| Ruff lint і format | PASS | results/ruff.txt |
| Unit та HTTP/ORM тести | 19 passed; 3 PostgreSQL skipped | results/pytest.txt, pytest.xml |
| Реєстрація, login, USER/ADMIN, IDOR | PASS на тестовому SQLite | tests/test_api.py |
| Послідовні курси, дубль і місткість | PASS на тестовому SQLite | tests/test_api.py |
| Pre-commit | Два погані коміти відхилено, виправлений прийнято | results/precommit_demo.txt |
| Compose sandbox/production/dev | Офіційний Compose 2.40.3 прийняв конфігурації | results/compose_validation.txt |
| GitHub Actions YAML | Розбір і перевірка тригерів/кроків PASS | results/workflow_validation.txt |
| Locust сценарії | Імпорт і --list PASS | results/locust_validation.txt |
| Word-звіти | 5 DOCX, по 2 сторінки; render та візуальна перевірка | reports/ |

Одна DeprecationWarning походить від сумісності Starlette TestClient/AnyIO; тести не падають.

## НЕ підтверджено і чому

- PostgreSQL-з'єднання, SQL-обмеження та блокування: initdb відмовився працювати від root;
  доступного непривілейованого UID немає. Три PostgreSQL-тести явно skipped.
- Docker build, старт, фактичні healthcheck, persistence та hot-reload: Docker daemon socket
  недоступний у цьому середовищі. Спроба up --build збережена у results/docker_attempt.txt.
- Реальна ізоляція двох запущених баз: конфігурація перевірена, контейнери не працювали.
- Цільове навантаження Locust на PostgreSQL: не проводилося. RPS, mean/min/max/p95,
  Error Rate, CPU та RAM НЕ виміряно; числові графіки результатів не створювалися.
- Hosted GitHub Actions: проєкт не опубліковано у GitHub, workflow віддалено не виконувався.

SQLite використовується виключно у тестовій fixture, ніколи як режим додатка.
Він не підтримує еквівалент PostgreSQL FOR UPDATE, тому не доводить правильність гонок.
Якщо TEST_DATABASE_URL задано, HTTP/ORM-тести також працюють на справжньому PostgreSQL.

## Як закрити залишок на Windows

1. scripts/configure.py; docker compose up --build; створити ADMIN.
2. python scripts/run_tests.py — усі тести на PostgreSQL magic_test без skips.
3. python scripts/verify_docker.py — build, healthy, API, SQL та persistence в окремому проєкті.
4. Повернути звичайний режим без reload і виконати run_load.py normal та spike.
5. Додати отримані CSV, таблицю і графік до ЛР4; перевірити outcomes та capacity_invariant_ok.
6. Показати reload у dev і розділення sandbox/production; зафіксувати свої журнали.
7. Після push/PR перевірити зелений hosted workflow та його артефакти.

Не називайте 50 балів отриманою оцінкою. Це максимум критеріїв. Відсутні вимірювання ЛР4
та runtime-докази ЛР5 можуть вплинути на оцінку, доки не виконано локальні перевірки.
