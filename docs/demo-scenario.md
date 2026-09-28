# Сценарий демонстрации

## Подготовка

### 1. Перезапустить стенд

```powershell
cd C:\1c-pgbouncer-arbiter
docker-compose restart
```

### 2. Открыть Grafana

```
http://localhost:3000
```

Логин `admin`, пароль `admin`.

### 3. Запустить генератор нагрузки

```powershell
docker-compose --profile load run load-generator
```

## Что смотреть в Grafana

### Requests by Priority

График показывает, сколько запросов в секунду идёт через каждый пул. VIP-запросы идут через HIGH, фон — через LOW.

### VIP Latency p95

Показывает 95-й процентиль latency для VIP-запросов. Должен оставаться низким, даже когда LOW-пул загружен.

### Preemptions

Счётчик отменённых read-only LOW-запросов. Если HIGH перегружен, арбитр начинает вытеснять LOW.

### Errors by Type

Ошибки соединений. Должно быть пусто.

## Что говорить

> «Смотрите: генератор имитирует трёх пользователей. VIP — гендир, лёгкие запросы. NORMAL — бухгалтеры. LOW — фоновое перепроведение, тяжёлые запросы. Все идут через один арбитр, но арбитр размечает их по `application_name` и направляет в разные пулы. VIP latency остаётся низким, пока LOW загружен. Это изоляция соединений.»

## Ограничение

В реальной 1С арбитр не сработает так же — 1С не передаёт `application_name`. Для прода нужен либо модифицированный клиент 1С, либо три базы в кластере.

## Проверка через psql

Параллельно с генератором можно смотреть, что происходит в PostgreSQL:

```powershell
& "C:\Program Files\PostgreSQL\18.4-1.1C\bin\psql.exe" "host=localhost port=5432 user=postgres dbname=demo_pgbouncer" --command="select application_name, count(*), state from pg_stat_activity where datname='demo_pgbouncer' group by application_name, state;"
```

Ожидаешь увидеть:

```
 application_name | count | state
------------------+-------+--------
 vip_1            |     2 | active
 vip_2            |     1 | idle
 manager_5        |     3 | active
 background_1     |     2 | active
 background_2     |     1 | active
```

VIP-соединения идут через HIGH, фоновые — через LOW.
