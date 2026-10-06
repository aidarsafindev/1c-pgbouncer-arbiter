# VIP не ждут. PgBouncer + PostgreSQL: приоритизация запросов для 1С

Демонстрационный репозиторий к докладу **«VIP не ждут. PgBouncer + PostgreSQL: как приоритизировать запросы и снизить хвостовые задержки для критичных пользователей 1С»**.

## Что это

У всех пользователей 1С равные права. Но не равная ценность для бизнеса. Когда генеральный директор открывает отчёт, а бухгалтер запустил массовое перепроведение — оба ждут одинаково долго. PgBouncer не различает, кто важнее. Он ставит запросы в очередь: первый пришёл — первый ушёл.

Этот репозиторий показывает, как PgBouncer можно научить приоритезации: **три экземпляра на разных портах с разными лимитами соединений + TCP-арбитр, который размечает запросы по контексту и направляет в нужный пул**.

## Что внутри

- Три экземпляра PgBouncer: HIGH, NORMAL, LOW
- **TCP-арбитр** на Python — читает startup-пакет PostgreSQL, смотрит на `application_name`, направляет в нужный пул
- **Безопасное вытеснение**: отменяются только read-only LOW-запросы через `pg_cancel_backend`
- **Генератор нагрузки**: имитирует VIP (лёгкие запросы), NORMAL (штатная работа), LOW (тяжёлые агрегации)
- **Дашборд Grafana** для мониторинга очередей и latency

## Быстрый старт

### 1. Подготовь PostgreSQL

`postgresql.conf`:

```ini
listen_addresses = '*'
```

`pg_hba.conf` — добавь в конец:

```
host    all             all             172.16.0.0/12           md5
host    all             all             192.168.0.0/16          md5
```

```powershell
Restart-Service postgresql-x64-18
```

### 2. Склонируй репозиторий

```powershell
git clone https://github.com/<твой-логин>/1c-pgbouncer-arbiter.git
cd 1c-pgbouncer-arbiter
```

### 3. Запусти стенд

```powershell
docker-compose up -d
docker-compose ps
```

### 4. Проверь пулы

```powershell
& "C:\Program Files\PostgreSQL\18.4-1.1C\bin\psql.exe" "host=localhost port=6432 user=postgres dbname=demo_pgbouncer application_name=" --command="select 1;"
```

### 5. Запусти генератор нагрузки

```powershell
docker-compose --profile load run load-generator
```

### 6. Открой Grafana

```
http://localhost:3000
```

Логин: `admin` / пароль: `admin`.

## Архитектура

```
1С (или генератор нагрузки)
        ↓
   TCP-арбитр :5432
        ↓
   ┌────┴────┬─────────┐
   ↓         ↓         ↓
PgBouncer  PgBouncer  PgBouncer
  HIGH      NORMAL     LOW
   ↓         ↓         ↓
        PostgreSQL
```

## Разметка запросов

Арбитр читает startup-пакет PostgreSQL. В нём есть поле `application_name`. Если клиент передаёт `application_name = vip`, арбитр направляет в HIGH. Если `background` — в LOW. Остальные — в NORMAL.

## Вытеснение

Если HIGH-пул перегружен, арбитр ищет в `pg_stat_activity` **читающие** LOW-запросы (`SELECT`) и отменяет самый старый через `pg_cancel_backend`. Пишущие (`INSERT`, `UPDATE`, `DELETE`) не трогает.

## Что не применимо к 1С напрямую

- **TCP-арбитр** — 1С не передаёт `application_name` в startup-пакете так, как это делает `psql`. Для реальной 1С нужен либо модифицированный клиент, либо разные пользователи СУБД, либо три базы в кластере.
- **Вытеснение `pg_cancel_backend`** — для 1С в `session` режиме отмена одного запроса не освобождает соединение.
- **`pool_mode = transaction`** — для 1С **не поддерживается**. В репозитории используется `session`.
- **Grafana** — метрики арбитра. Для реальной 1С метрики другие.

## Ограничения

- Приоритизация работает **только когда узкое место — соединения**. Если CPU или диск PostgreSQL на 100% — не поможет.
- Вытесняются **только read-only** фоновые запросы.
- 1С требует `pool_mode = session`.
- Три пула не изолируют данные. Блокировки общие. Если фон залочил таблицу, VIP будет ждать.

Подробно — в `docs/limitations.md`.

## Лицензия

MIT
