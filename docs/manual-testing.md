# Дані для мануального тестування

Цей документ описує fixture `fixtures/manual_testing.json` і сценарії ручної
перевірки API. Дані призначені **лише для локального середовища**. Пароль
`ManualTest123!` є тестовим і не повинен використовуватися поза локальною
розробкою.

## Швидкий старт

```bash
# PostgreSQL і Redis мають бути запущені, міграції — застосовані.
uv run python manage.py migrate
uv run python manage.py loaddata fixtures/manual_testing.json
```

Якщо стек запущений через Docker Compose:

```bash
docker compose up -d --build
docker compose exec web python manage.py loaddata fixtures/manual_testing.json
```

Перевірка, що fixture завантажився:

```bash
curl "http://localhost:8000/api/v1/locations/?search=Manual"
```

Очікується `count: 3` (локації `9101`, `9102`, `9104`). Локація `9103`
soft-deleted і не входить до активного списку.

Swagger UI: `http://localhost:8000/api/v1/docs/`.

## Облікові записи

Усі користувачі мають пароль `ManualTest123!`.

| ID | Email | Username | Роль | Email verified | Active | Призначення |
|---:|---|---|---|---|---|---|
| 9001 | `admin@manual.test` | `manual_admin` | admin | так | так | Адмінські операції, перегляд усіх deleted locations |
| 9002 | `owner@manual.test` | `manual_owner` | user | так | так | Власник `9101`, `9103`, `9104`; отримує email про відгуки |
| 9003 | `reviewer@manual.test` | `manual_reviewer` | user | так | так | Автор `9201`, `9204`; підписаний на `9101` |
| 9004 | `subscriber@manual.test` | `manual_subscriber` | user | так | так | Автор `9202`; підписки на `9101`, `9103`; неактивна підписка на `9102` |
| 9005 | `unverified@manual.test` | `manual_unverified` | user | ні | так | Перевірка заборони входу без підтвердження email |
| 9006 | `other@manual.test` | `manual_other` | user | так | так | Власник `9102`; автор deleted-відгуку `9206` на `9101` |
| 9007 | `inactive@manual.test` | `manual_inactive` | user | так | ні | Перевірка заборони входу неактивного акаунта |

`manual_other` не має активного відгуку на `9101`, тому може створити новий
відгук і згенерувати email-доставки.

## Категорії

Fixture використовує категорії з seed-міграції `categories.0002_seed_categories`
за фіксованими PK:

| PK | Назва |
|---:|---|
| 1 | Cafe |
| 3 | Bar |
| 5 | Park |
| 7 | Gallery |
| 9 | Nature |

Fixture не створює нових категорій. Якщо категорії з цими PK були змінені або
видалені, завантажуйте fixture на чисту базу після `migrate`.

## Локації

| ID | Назва | Власник | Категорії | Стан | Рейтинг | Відгуків | Views 7d | Popularity |
|---:|---|---|---|---|---:|---:|---:|---:|
| 9101 | Manual Riverside Cafe | `manual_owner` | Cafe, Nature | active | 4.7 | 3 | 0 | 53.92 |
| 9102 | Manual Central Park | `manual_other` | Park, Nature | active | 3.5 | 2 | 0 | 40.00 |
| 9103 | Manual Hidden Bar | `manual_owner` | Bar | soft-deleted | — | 0 | 0 | — |
| 9104 | Manual Empty Gallery | `manual_owner` | Gallery | active | null | 0 | 0 | 0.00 |

Адреси та координати:

| ID | Адреса | Latitude | Longitude |
|---:|---|---:|---:|
| 9101 | 12 River Street, Kyiv | 50.450100 | 30.523400 |
| 9102 | 1 Park Avenue, Kyiv | 50.448000 | 30.521000 |
| 9103 | 7 Secret Lane, Kyiv | 50.452000 | 30.517000 |
| 9104 | 3 Quiet Square, Kyiv | 50.454000 | 30.519000 |

`9103` має `deleted_at = 2026-10-25T09:00:00Z`. Після restore вона стане
активною; рейтинг буде `null`, `review_count = 0`, `views_7d = 0`,
`popularity = 0.0`.

Початковий `views_7d = 0`, бо всі засіяні перегляди старші за 7 днів. Щоб
отримати свіжі перегляди, використовуйте `GET /api/v1/locations/{id}/`.

## Відгуки

| ID | Локація | Автор | Рейтинг | Коментар | Стан | Likes | Dislikes |
|---:|---:|---|---:|---|---|---:|---:|
| 9201 | 9101 | `manual_reviewer` | 5 | Excellent coffee and river view. | active | 2 | 0 |
| 9202 | 9101 | `manual_subscriber` | 4 | Nice place, a bit busy on weekends. | active | 0 | 1 |
| 9203 | 9101 | `manual_owner` | 5 | Owner's favorite spot. | active | 0 | 0 |
| 9204 | 9102 | `manual_reviewer` | 4 | Good for a walk. | active | 1 | 0 |
| 9205 | 9102 | `manual_owner` | 3 | A bit crowded on weekends. | active | 0 | 0 |
| 9206 | 9101 | `manual_other` | 2 | Historic review kept for audit. | deleted | 0 | 0 |

`9206` має `deleted_at = 2026-10-24T10:00:00Z` і не враховується в рейтингу та
`review_count`. Водночас він не заважає `manual_other` створити новий активний
відгук на `9101`.

## Реакції

| ID | Відгук | Користувач | Тип |
|---:|---:|---|---|
| 9301 | 9201 | `manual_subscriber` | like |
| 9302 | 9201 | `manual_owner` | like |
| 9303 | 9202 | `manual_reviewer` | dislike |
| 9304 | 9204 | `manual_owner` | like |

## Підписки

| ID | Локація | Користувач | Активна | Примітка |
|---:|---:|---|---|---|
| 9401 | 9101 | `manual_subscriber` | так | Отримує email про нові відгуки |
| 9402 | 9101 | `manual_reviewer` | так | Отримує email про нові відгуки |
| 9403 | 9102 | `manual_subscriber` | ні | `unsubscribed_at = 2026-10-20T09:00:00Z`; можна реактивувати через `PUT` |
| 9404 | 9103 | `manual_subscriber` | так | Залишається активною, навіть коли локація soft-deleted |

Підписки на `9103` не скасовуються soft delete. Після restore локації
сповіщення поновлюються без повторної підписки.

## Перегляди

| ID | Локація | Identity hash | Viewed at |
|---:|---:|---|---|
| 9501 | 9101 | `aaaa…` (64 символи) | 2026-09-01T12:00:00Z |
| 9502 | 9101 | `bbbb…` (64 символи) | 2026-09-15T12:00:00Z |
| 9503 | 9103 | `cccc…` (64 символи) | 2026-09-20T12:00:00Z |

Усі перегляди старші за 7 днів, тому `views_7d = 0`. Вони залишаються в базі
для перевірки віконного фільтра.

## Email-доставки

Fixture не створює `EmailDelivery`. Щоб перевірити outbox:

1. Увійдіть як `other@manual.test`.
2. Створіть відгук на `9101`.
3. Очікуйте `201` і три `pending` доставки: власнику `9002` та активним
   підписникам `9003`, `9004`.
4. Перевірте MailHog: `http://localhost:8025/`.
5. Перевірте статуси через admin або shell:

```bash
uv run python manage.py shell -c \
  "from apps.notifications.models import EmailDelivery; print(list(EmailDelivery.objects.values('id','review_id','recipient_id','status')))"
```

Редагування відгуку через `PATCH`/`PUT` не створює нових доставок.

## Сценарії ручної перевірки

### 1. Автентифікація

- `GET /api/v1/auth/csrf/` — `200`, повертає `csrf_token` і cookie.
- `POST /api/v1/auth/login/` з `owner@manual.test` / `ManualTest123!` — `200`.
- `GET /api/v1/auth/me/` — профіль `manual_owner`.
- `POST /api/v1/auth/logout/` — `204`.
- Логін `unverified@manual.test` — `401 invalid_credentials`.
- Логін `inactive@manual.test` — `401 invalid_credentials`.
- Логін `admin@manual.test` — `200`, роль `admin`.

Приклад отримання CSRF і логіну через curl (bash/Git Bash):

```bash
curl -s -c cookies.txt http://localhost:8000/api/v1/auth/csrf/ > /dev/null
CSRF=$(awk '$6 == "csrftoken" {print $7}' cookies.txt)
curl -s -b cookies.txt -c cookies.txt \
  -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -d '{"email":"owner@manual.test","password":"ManualTest123!"}'
```

Після login повторно прочитайте `csrftoken` з `cookies.txt`, якщо будете
виконувати інші небезпечні методи (`POST`, `PUT`, `PATCH`, `DELETE`).

### 2. Категорії

- `GET /api/v1/categories/` — 12 seed-категорій.
- `POST /api/v1/categories/` як admin — `201`.
- `POST /api/v1/categories/` як звичайний користувач — `403`.
- `DELETE /api/v1/categories/{id-Cafe}/` — `409 category_in_use`, бо `9101`
  використовує Cafe.
- Створіть нову категорію як admin і видаліть її — `204`.

### 3. Локації

- `GET /api/v1/locations/` — `count: 3`, порядок: `9101`, `9102`, `9104`.
- `?search=river` — `9101`.
- `?search=park` — `9102`.
- `?search=   ` — пробільний пошук ігнорується, повертаються всі 3.
- `?category=Cafe` — `9101`.
- `?category=Park&category=Gallery` — `9102`, `9104`.
- `?author=manual_owner` — `9101`, `9104` (`9103` deleted).
- `?author=manual_other` — `9102`.
- `?rating_min=4` — `9101`.
- `?rating_max=3.5` — `9102`.
- `?popularity_min=50` — `9101`.
- `?ordering=rating` — `9101`, `9102`, `9104` (null останнім).
- `?ordering=-created_at` — `9104`, `9102`, `9101`.
- `?page_size=2` — `count: 3`, два results, `next` не null.
- Невалідний `ordering` — `400 invalid_ordering`.
- `page=0` — `400 invalid_pagination`; `page=999` — `404 not_found`.
- `GET /api/v1/locations/export/?format=json` — 3 рядки.
- `GET /api/v1/locations/export/?format=csv` — CSV attachment.
- `GET /api/v1/locations/export/` без `format` — `400 unsupported_export_format`.
- `GET /api/v1/locations/9101/` — `200`; `GET /api/v1/locations/9103/` — `404`.
- `PATCH /api/v1/locations/9104/` як owner — `200`; як `manual_other` — `403`;
  анонімно — `401`.
- `DELETE /api/v1/locations/9104/` як owner — `204`; локація зникає з active
  list, з'являється в `/api/v1/locations/deleted/`; restore — `200`.
- `GET /api/v1/locations/deleted/`:
  - owner бачить `9103` (і `9104`, якщо його щойно видалили);
  - `manual_other` не бачить чужих deleted locations;
  - admin бачить усі deleted locations.
- `POST /api/v1/locations/9103/restore/` як owner — `200`, локація знову
  активна. Після перевірки поверніть її в deleted-стан або перезавантажте
  fixture.

### 4. Відгуки та реакції

- `GET /api/v1/locations/9101/reviews/` — `count: 3`, порядок `9203`, `9202`,
  `9201`; у `9201` `likes_count: 2`, у `9202` `dislikes_count: 1`.
- `GET /api/v1/reviews/9201/` — `200`; `GET /api/v1/reviews/9206/` — `404`.
- `POST /api/v1/locations/9101/reviews/` як `manual_other` — `201`.
- Повторний `POST` тим самим автором на `9101` — `409 review_already_exists`.
- `PATCH /api/v1/reviews/9201/` як `manual_reviewer` з `{"rating": 4}` —
  `200`, новий review ID, коментар `Excellent coffee and river view.`
  зберігається; старий `9201` стає historical і повертає `404`.
- `PUT /api/v1/reviews/9202/` як `manual_subscriber` з новими `rating` і
  `comment` — `200`, старий запис soft-deleted.
- `PATCH`/`DELETE` чужого відгуку — `403`.
- `DELETE /api/v1/reviews/9203/` як owner — `204`; рейтинг `9101` стає `4.5`,
  `review_count` — `2`.
- `GET /api/v1/reviews/9201/reaction/` як `manual_owner` — `like` (реакція
  `9302`).
- `PUT` з `{"type":"dislike"}` — `200`, стан змінюється.
- `DELETE` — `204`, реакція зникає; повторний `DELETE` — `204`.
- Анонімні реакції — `401`.

### 5. Підписки

- `GET /api/v1/locations/9101/subscription/` як `manual_subscriber` —
  `is_active: true`.
- `GET /api/v1/locations/9101/subscription/` як `manual_other` —
  `is_active: false`.
- `PUT /api/v1/locations/9101/subscription/` як `manual_other` — `200`,
  створює активну підписку; повторний `PUT` ідемпотентний.
- `DELETE /api/v1/locations/9101/subscription/` — `204`, підписка стає
  неактивною, історичний рядок зберігається.
- `GET /api/v1/locations/9103/subscription/` як `manual_subscriber` — `200`,
  `is_active: true` навіть для soft-deleted локації.
- `PUT /api/v1/locations/9103/subscription/` — `404`, бо локація не активна.
- `PUT /api/v1/locations/9102/subscription/` як `manual_subscriber` —
  реактивує `9403`.

### 6. Нотифікації

1. Увійдіть як `manual_other`.
2. `POST /api/v1/locations/9101/reviews/` з `rating` 3 і коментарем.
3. Перевірте `EmailDelivery`: має бути 3 `pending` записи для `9002`, `9003`,
   `9004`.
4. Перевірте MailHog `http://localhost:8025/` після роботи worker/beat.
5. `PATCH` цього відгуку — нових доставок не буде.
6. Soft-delete `9103`, спробуйте створити відгук — `404`; після restore
   створіть відгук як `manual_reviewer` — з'являться доставки власнику та
   активному підписнику `9404`.

### 7. Кеш списку

- `GET /api/v1/locations/` двічі — другий запит обслуговується кешем.
- `PATCH /api/v1/locations/9104/` з новою назвою як owner — наступний
  `GET /api/v1/locations/` має показати нову назву (інвалідація після commit).
- Створення/редагування/видалення відгуку також інвалідує list cache.
- Перегляди та реакції **не** інвалідують list cache: `views_7d` у списку може
  оновлюватися із затримкою до `LOCATION_LIST_CACHE_TTL_SECONDS` (60 секунд).
  Detail endpoint показує свіжі метрики.

### 8. Перегляди та cooldown

- `GET /api/v1/locations/9101/` з новим cookie jar — у відповіді
  `views_7d: 0`, після чого перегляд записується.
- Повторний `GET` тим самим cookie jar — `views_7d: 1`, але новий перегляд не
  додається (cooldown 3600 секунд).
- `GET` з іншим cookie jar — `views_7d: 1`, після чого записується другий
  перегляд.
- Наступний detail з іншого identity (або list після TTL/інвалідації) показує
  `views_7d: 2`.
- Старі перегляди `9501`, `9502` не враховуються.
- `GET /api/v1/locations/999999/` — `404`, перегляд не створюється.
- Якщо cooldown заважає тестуванню, очистіть Redis DB для переглядів:
  `docker compose exec redis redis-cli -n 2 FLUSHDB` (лише локальне
  середовище).

### 9. OpenAPI

- `GET /api/v1/docs/` — Swagger UI, `200`.
- `GET /api/v1/schema/` — OpenAPI schema, `200`.
- У schema присутня схема автентифікації `cookieAuth`.

## Очищення та повторне завантаження

`loaddata` оновлює записи з тими самими PK, але не видаляє дані, створені
вручну. Для повного скидання використовуйте окрему локальну базу або
перестворіть Docker volume (це знищить усі локальні дані):

```bash
docker compose down -v
docker compose up -d --build
docker compose exec web python manage.py loaddata fixtures/manual_testing.json
```

Не виконуйте `down -v` на спільній або production-базі.

## Обмеження fixture

- Використовуються seed-категорії з PK `1, 3, 5, 7, 9`; fixture розрахований на
  чисту базу після `migrate`.
- Початкові `views_7d` дорівнюють `0`; свіжі перегляди створюються через API.
- Email-доставки не засіяні; їх створює новий відгук.
- Пароль `ManualTest123!` — локальний тестовий пароль, не production secret.
- Деякі сценарії змінюють дані (наприклад, soft delete або заміна відгуку).
  Після них перезавантажте fixture або скиньте локальну базу.
