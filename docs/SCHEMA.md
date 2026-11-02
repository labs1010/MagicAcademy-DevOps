# Схема бази даних версії 1

| Таблиця | Поля і ключі | Обмеження |
|---|---|---|
| users | id, username, display_name, password_hash, role | username UNIQUE; role USER/ADMIN |
| courses | id, title, capacity | CHECK capacity > 0 |
| enrollments | id, user_id → users, course_id → courses | UNIQUE(user_id, course_id); індекси обох FK |

users 1:N enrollments N:1 courses. Вільні місця — capacity мінус COUNT(enrollments),
окремий лічильник не зберігається, тому він не може розійтися з таблицею записів.

FastAPI lifespan викликає `Base.metadata.create_all(engine)`: створює відсутні таблиці,
але не видаляє дані і не оновлює існуючі стовпці. Для цього MVP з однією версією схеми
окрема бібліотека міграцій не потрібна. Якщо схема зміниться після розгортання,
потрібні явні SQL-міграції або Alembic і резервна копія. `create_all` їх не замінює.

Sandbox: magic_sandbox. Production: magic_production. Tests: magic_test.
У Compose production має окремий project name і окремий volume, не лише іншу назву БД.
Ініціалізація POSTGRES_* офіційного образу виконується тільки для порожнього volume.
Зміна пароля в .env не змінює пароль уже створеної PostgreSQL-ролі.
