VERSION := $(shell python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
IMAGE ?= shop-model
GIT_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo nogit)
SOURCE ?=
LABELS := $(if $(SOURCE),--label org.opencontainers.image.source=$(SOURCE))
GATE_SPLIT ?= holdout
ROUTE ?= both
SHOW ?=
BY ?= department
STORE_SHA := $(shell sha256sum kg/build/shop.nt 2>/dev/null | cut -c1-16 || echo nostore)

.PHONY: install lint test validate gate build publish up train register champion version ask profile sales kg-version kg-release kg-load kg-count kg-ask kg-clean kg-check ci

install:
	python3 -m pip install -r requirements.txt
	python3 -m pip install --no-deps -e ".[dev]"

lint:
	ruff check src tests

test:
	pytest -q

validate:
	shop-validate

gate:
	shop-gate --split $(GATE_SPLIT)

train:
	shop-train

register: train
	shop-registry register

ask:
	shop-ask questions --route $(ROUTE) $(SHOW)

profile:
	shop-ask profile

sales:
	shop-ask sales-by $(BY)

KG_VERSION := $(shell sed -n 's/^version: "\(.*\)"$$/\1/p' kg/schema.yaml)

kg-version:
	@echo $(KG_VERSION)

kg-load:
	shop-kg load

kg-count:
	shop-kg count

kg-ask:
	shop-kg ask

kg-clean:
	rm -f kg/build/shop.nt

kg-check:
	shop-kg check

kg-release: test kg-check
	@git diff --quiet HEAD || \
	{ echo "Commit your changes before releasing the knowledge."; exit 1; }
	git tag -d kg-v$(KG_VERSION) 2>/dev/null || true
	git push origin --delete kg-v$(KG_VERSION) 2>/dev/null || true
	git tag kg-v$(KG_VERSION) -m "Shop knowledge $(KG_VERSION); store sha256 $(STORE_SHA)"
	@echo "Push the tag with: git push origin kg-v$(KG_VERSION)"

build:
	docker build --build-arg APP_VERSION=$(VERSION) -t $(IMAGE):$(VERSION) -t $(IMAGE):$(VERSION)-$(GIT_SHA) $(LABELS) .

publish:
	docker push $(IMAGE):$(VERSION)
	docker push $(IMAGE):$(VERSION)-$(GIT_SHA)

up:
	APP_VERSION=$(VERSION) docker compose up -d --build

champion:
	shop-registry alias champion $(V)
	docker compose restart api

version:
	@echo $(VERSION)

ci: lint test validate gate kg-check build
