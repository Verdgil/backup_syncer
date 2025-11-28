# backup_syncer

[eng](## English)

---

## Русский

### Описание

**backup_syncer** — pet-проект для проверки целостности резервных копий и (в будущем) синхронизации файлов между серверами.

Проект состоит из двух независимых модулей:

- **service** — серверный сервис, который собирает информацию о файлах и рассчитывает контрольные суммы
- **checker** — утилита для проверки файлов/результатов и валидации сохранённых данных

В перспективе проект будет расширен до полноценной системы синхронизации между серверами.

---

### Архитектура

```
backup_syncer/
├── service/ # Серверный модуль
└── checker/ # Проверяющий модуль
```

---

### Модуль `service`

Модуль `service` предназначен для запуска на серверах, где хранятся данные.

Основные возможности:

- Рекурсивный обход директорий
- Получение списка файлов, отсортированного по размеру
- Расчёт контрольных сумм:
  - `SHA256`
  - `MD5`
- Параллельная обработка файлов (multiprocessing)
- Автоматическое определение количества физических ядер
- Кросс-платформенная поддержка checksum-утилит:
  - Linux
  - FreeBSD
  - OpenBSD
  - SunOS
  - macOS
- Формирование JSON-отчётов
- Криптографическая подпись результата (`SHA3-512`)

Результат работы сервиса сохраняется в JSON-файл следующего вида:

- список файлов
- контрольные суммы
- ошибки (если были)
- время выполнения
- timestamp запуска
- имя группы
- подпись данных

---

### Конфигурация

Пример `config.py`:

```python
GROUPS = [
    {
        "name": "group1",
        "path": "/data/backups"
    }
]

OUTPUT_DIRECTORY = "/var/lib/backup_syncer/output"

```

### Запуск

Предполагается запуск по крону

---

### Модуль `checker`

Модуль `checker` предназначен для:

* проверки целостности файлов
* проверки контрольных сумм
* проверки подписи данных
* сравнения текущего состояния с ранее сохранёнными результатами

Код модуля активно развивается и предназначен для использования отдельно от сервиса.

---

### Планы на будущее

* синхронизация файлов между серверами
* сравнение состояний разных серверов
* инкрементальные проверки
* удалённое взаимодействие (API / agent-based)
* автоматическое восстановление повреждённых файлов

---

## English

### Description

**backup_syncer** is a pet project for backup integrity verification and (in the future) file synchronization between servers.

The project consists of two independent modules:

* **service** — a server-side service that scans files and calculates checksums
* **checker** — a utility for validating files and checking stored results

In the future, the project is planned to evolve into a full-featured server-to-server synchronization system.

---

### Architecture

```
backup_syncer/
├── service/     # Server-side module
└── checker/     # Validation module
```

---

### `service` Module

The `service` module is designed to run on servers where data is stored.

Main features:

* Recursive directory scanning
* File list generation sorted by file size
* Checksum calculation:

  * `SHA256`
  * `MD5`
* Parallel file processing (multiprocessing)
* Automatic detection of physical CPU cores
* Cross-platform checksum command support:

  * Linux
  * FreeBSD
  * OpenBSD
  * SunOS
  * macOS
* JSON report generation
* Cryptographic signing of results (`SHA3-512`)

Each run produces a signed JSON report containing:

* file list
* checksums
* errors (if any)
* execution time
* start timestamp
* group name
* data signature

---

### Configuration

Example `config.py`:

```python
GROUPS = [
    {
        "name": "group1",
        "path": "/data/backups"
    }
]

OUTPUT_DIRECTORY = "/var/lib/backup_syncer/output"
```

---

### Running the service

```bash
python service/main.py
```

The service processes all configured groups sequentially and stores results in `OUTPUT_DIRECTORY`.

---

### `checker` Module

The `checker` module is responsible for:

* file integrity validation
* checksum verification
* signature validation
* comparing current state with previously saved results

The module is under active development and can be used independently from the service.

---

### Roadmap

* file synchronization between servers
* cross-server state comparison
* incremental checks
* remote communication (API / agents)
* automatic recovery of corrupted files

