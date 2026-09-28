# Настройка PostgreSQL

## 1. Разрешить подключения из Docker

Открой `C:\Program Files\PostgreSQL\18.4-1.1C\data\postgresql.conf`.

Найди или добавь:

```ini
listen_addresses = '*'
```

Открой `C:\Program Files\PostgreSQL\18.4-1.1C\data\pg_hba.conf`.

Добавь **в конец файла**:

```
host    all             all             172.16.0.0/12           md5
host    all             all             192.168.0.0/16          md5
```

Почему именно эти подсети:
- `172.16.0.0/12` — покрывает `172.16.x.x`–`172.31.x.x`, стандартный диапазон Docker
- `192.168.0.0/16` — на случай другой конфигурации

Почему `md5`: в существующих строках стоит `md5`, пароль хранится в md5-хеше.

## 2. Перезапустить PostgreSQL

```powershell
Restart-Service postgresql-x64-18
```

Если имя службы другое:

```powershell
Get-Service | Where-Object {$_.Name -like "*postgres*"}
```

## 3. Проверить, что PostgreSQL слушает все интерфейсы

```powershell
netstat -an | findstr :5432
```

Должно быть:

```
TCP    0.0.0.0:5432    0.0.0.0:0    LISTENING
```

## 4. Проверить, что Docker видит PostgreSQL

```powershell
docker run --rm -it postgres:16 psql -h host.docker.internal -U postgres -d demo_pgbouncer -c "select 1;"
```

Введи пароль `postgres`. Если вернулась `1` — всё готово.

## 5. Если ошибка `no pg_hba.conf entry`

Строки из шага 1 не применились. Проверь:
- правил ли ты тот `pg_hba.conf` (в папке `18.4-1.1C\data\`)
- перезапустил ли службу
- нет ли опечаток в подсетях

## 6. Если ошибка `could not connect`

Файрвол Windows блокирует. Открой PowerShell от администратора:

```powershell
New-NetFirewallRule -DisplayName "PostgreSQL 5432" -Direction Inbound -Protocol TCP -LocalPort 5432 -Action Allow
```
