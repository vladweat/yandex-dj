# Технический долг и риски

Реестр основан на состоянии кода на 2026-10-12. «Риск» означает ограничение или
возможный failure mode, а не подтверждённый production incident.

## High

| Компонент | Статус | Evidence | Потенциальное влияние | Рекомендация |
|---|---|---|---|---|
| Sessions | Подтверждённое ограничение | `frontend/src/features/auth/auth-provider.tsx:logout`; нет revoke route в `backend/app/api/v1/router.py` | Украденный Bearer действует до TTL; logout только локальный | Server-side revoke, cleanup expired sessions, тесты |
| Public scoring | Подтверждённый риск | `backend/app/api/v1/endpoints/scoring.py:rank_tracks` не использует `CurrentSession`; rate limiter отсутствует в `app/main.py` | Неаутентифицированная CPU/RAM нагрузка | Auth/rate limit либо убрать route из public deployment |
| Secret rotation | Подтверждённое ограничение | `backend/app/core/security.py:_get_fernet` поддерживает один `TOKEN_ENCRYPTION_KEY` | Замена ключа инвалидирует все ciphertext | Versioned keyring и re-encryption runbook |
| External/DB consistency | Подтверждённый риск | `PlaylistService.generate` экспортирует до `PlaylistGenerationRepository.create`, который commit делает отдельно | Плейлист Яндекса может создаться без history row | Idempotency/reconciliation и явная saga policy |

## Medium

| Компонент | Статус | Evidence | Потенциальное влияние | Рекомендация |
|---|---|---|---|---|
| Health/readiness | Подтверждённое ограничение | `HealthService.get_status` возвращает static status/version | Оркестратор не видит отказ БД/Redis/model | Разделить liveness/readiness и проверять критичные зависимости |
| Transactions | Подтверждённое ограничение | commit в `AuthService` и `PlaylistGenerationRepository`; `get_db` без boundary | Неочевидная атомарность, сложнее rollback | Единый Unit of Work или явно документированные service boundaries |
| Cover storage | Подтверждённое ограничение | `COVER_STORAGE_DIR`, bind mount только у `api` | Потери при ephemeral deploy, inconsistency multi-replica | Shared object storage или single-replica/backup contract |
| Redis lifecycle | Потенциальный resource risk | singleton `get_track_cache`; FastAPI shutdown закрывает только DB engine | Неявное освобождение connection pool | Явный lifespan close и тест |
| Browser session | Подтверждённый trade-off | `frontend/src/lib/api.ts:SESSION_STORAGE_KEY` использует `localStorage`; CSP не настроен | XSS может украсть Bearer | CSP/XSS hardening; оценить httpOnly model |
| Deployment | Подтверждённый пробел | только dev `docker-compose.yml`, API с `--reload`; нет deploy workflow/TLS | Dev topology ошибочно используют как production | Определить production topology, health, secrets, rollback |
| Backup/recovery | Подтверждённый пробел | volume есть, backup scripts нет | Непроверенное восстановление БД/covers | RPO/RTO, automated backups, restore drills |
| Observability | Подтверждённый пробел | стандартные text logs; нет request ID/tracing/error tracker | Сложная диагностика распределённых failures | Correlation ID, structured logs, metrics/tracing |
| Frontend API URL | Подтверждённый operational trap | `NEXT_PUBLIC_API_URL` читается browser bundle; runtime env не переписывает build | UI обращается к неверному API после deploy | Build-time config contract или runtime config endpoint |
| Background processing | Подтверждённое ограничение | `generate_playlist` использует `asyncio.wait_for`; Celery/ARQ нет | Долгий request, cancellation/timeout и retry complexity | Вводить queue только по p95/нагрузочному триггеру из PRODUCT |
| Retention/privacy | Подтверждённый пробел | нет delete API/jobs для sessions, generations, covers | Бесконечный рост и неопределённый data lifecycle | Политика retention и user deletion |

## Low

| Компонент | Статус | Evidence | Влияние | Рекомендация |
|---|---|---|---|---|
| Error mapping | Подтверждённый долг | локальные `try/except` во всех endpoints и `api/playlist_http.py` | Drift status codes/messages | Typed global handlers без переноса business logic в HTTP |
| Frontend contract | Подтверждённый drift | backend `exclude_languages`, frontend `PlaylistGenerateRequest` поля нет | UI не даёт задать поддерживаемую опцию | Синхронизировать types/UI либо явно оставить API-only |
| Offline package | Подтверждённый пробел | `scripts/pack-offline-bundle.sh` не включает frontend | Archive не является full product bundle | Включить frontend artifacts или переименовать backend bundle |
| CLI docs | Подтверждённый пробел | `backend/app/cli/main.py` шире списка в `backend/README.md` | Сложнее диагностика | Поддерживать command reference через `--help` |
| Dead local fonts | Требует решения | `frontend/src/fonts/` есть, `layout.tsx` использует Google Fonts | Лишние artifacts / runtime egress | Подключить local fonts или удалить отдельным change |

## Проверка приоритетов

Перед remediation подтвердить production topology, threat model, требуемые
RPO/RTO и фактические p95. Архитектурный backlog очередей и multi-replica
storage не следует реализовывать только ради закрытия документационного риска.
