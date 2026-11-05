.PHONY: install clean venv build up down pack migrate test logs auth-poll deps-frontend up-frontend typecheck test-frontend logs-frontend

# Одна команда: venv + модель + libgomp + проверка
install:
	./scripts/build-venv.sh

clean:
	rm -rf backend/.venv backend/.libs backend/.models backend/.cache
	rm -rf backend/build backend/prompt_dj.egg-info dist

venv: install

build:
	docker compose build api bot

up:
	docker compose up -d

down:
	docker compose down

pack:
	./scripts/pack-offline-bundle.sh

# Команды локальной инфраструктуры.
migrate:
	docker compose exec -T api python -m alembic upgrade head

test:
	./scripts/test-backend.sh

logs:
	docker compose logs -f api db

auth-poll:
	docker compose exec api python -m app.cli.main auth poll

deps-frontend:
	bash frontend/scripts/prepare-deps.sh

up-frontend:
	docker compose build frontend && docker compose up -d frontend

typecheck:
	cd frontend && npx tsc --noEmit

test-frontend:
	cd frontend && npm test

logs-frontend:
	docker compose logs -f frontend
