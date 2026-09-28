# Настройка кластера 1С

## 1. Создать три информационные базы

В кластере серверов 1С создай три базы, все указывают на одну физическую базу `demo_pgbouncer`, но через разные порты.

| Имя базы в кластере | Сервер баз данных | Пул |
|---|---|---|
| `demo_pgbouncer` | `127.0.0.1 port=6432` | HIGH |
| `demo_pgbouncer_normal` | `127.0.0.1 port=6433` | NORMAL |
| `demo_pgbouncer_low` | `127.0.0.1 port=6434` | LOW |

**Поля:**
- Тип СУБД: `PostgreSQL`
- Сервер баз данных: `127.0.0.1 port=6432` (с портом через пробел, не через двоеточие)
- База данных: `demo_pgbouncer` (одинаковая у всех трёх)
- Пользователь: `postgres`
- Пароль: `postgres`

## 2. Через rac (альтернатива GUI)

Сначала запусти RAS-службу:

```powershell
# от администратора, в cmd.exe
sc create "1C RAS 1545" binPath= "\"C:\Program Files\1cv8\8.3.27.2342\bin\ras.exe\" cluster --service --port=1545 localhost:1540" start= auto
sc start "1C RAS 1545"
```

Проверь:

```powershell
netstat -an | findstr 1545
```

Получи UUID кластера:

```powershell
& "C:\Program Files\1cv8\8.3.27.2342\bin\rac.exe" localhost:1545 cluster list
```

Создай базы:

```powershell
& "C:\Program Files\1cv8\8.3.27.2342\bin\rac.exe" infobase --cluster=<UUID> create --name=demo_pgbouncer_normal --dbms=PostgreSQL --db-server="127.0.0.1 port=6433" --db-name=demo_pgbouncer --db-user=postgres --db-pwd=postgres

& "C:\Program Files\1cv8\8.3.27.2342\bin\rac.exe" infobase --cluster=<UUID> create --name=demo_pgbouncer_low --dbms=PostgreSQL --db-server="127.0.0.1 port=6434" --db-name=demo_pgbouncer --db-user=postgres --db-pwd=postgres
```

## 3. Изменить существующую базу

Если база `demo_pgbouncer` уже есть и подключена к порту 5432, измени порт:

```powershell
& "C:\Program Files\1cv8\8.3.27.2342\bin\rac.exe" infobase --cluster=<UUID> update --infobase=<UUID_базы> --db-server="127.0.0.1 port=6432"
```

Если ошибка «Информационная база имеет непустой список соединений» — закрой всех клиентов 1С, подожди минуту, попробуй снова.

## 4. Перезапустить сервер 1С

```powershell
Get-Service | Where-Object {$_.Name -like "*1cv8*"}
Restart-Service "<имя_службы>"
```

## 5. Проверить

Запусти 1С, зайди в каждую базу. Потом:

```powershell
& "C:\Program Files\PostgreSQL\18.4-1.1C\bin\psql.exe" "host=localhost port=5432 user=postgres dbname=demo_pgbouncer" --command="select application_name, count(*) from pg_stat_activity where datname='demo_pgbouncer' and application_name like 'POOL%' group by application_name;"
```

Ожидаешь:

```
 application_name | count
------------------+-------
 POOL_HIGH        |     1
 POOL_NORMAL      |     1
 POOL_LOW         |     1
```
