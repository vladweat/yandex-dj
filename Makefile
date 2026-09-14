.PHONY: install clean venv build up down pack migrate test logs auth-poll

# Одна команда: venv + модель + libgomp + проверка
install:
	./scripts/build-venv.sh

clean:
	rm -rf backend/.venv backend/.libs backend/.models backend/.cache
	rm -rf backend/build backend/prompt_dj.egg-info dist

venv: install

build:
	docker compose build api

up:
	docker compose up -d

down:
	docker compose down

pack:
	./scripts/pack-offline-bundle.sh

# Инфраструктура — только в Makefile (как docwise)
migrate:
	docker compose exec -T api python -m alembic upgrade head

test:
	docker compose exec -T api python -m pytest tests/ -q

logs:
	docker compose logs -f api db

auth-poll:
	docker compose exec api python -m app.cli.main auth poll
