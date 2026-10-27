# Image de production de la VM centrale (spec 1.6.1, ADR-0021). Contexte de
# build : vm-centrale/. Aucun secret dedans : .env, clé maître et scripts de
# dev (scripts/, tests/) ne sont jamais copiés (voir aussi .dockerignore).

# Images épinglées (jamais latest, comme searxng/Dockerfile). uv : même
# version que les lanceurs de dev.
FROM ghcr.io/astral-sh/uv:0.12.16 AS uv

FROM python:3.11.18-slim-trixie AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dépendances verrouillées par uv.lock (ADR-0011) : --locked échoue si le
# verrou ne suit plus pyproject.toml. Paquet installé non éditable, sans
# l'extra test.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-install-project --no-editable
COPY src ./src
RUN uv sync --locked --no-editable

FROM python:3.11.18-slim-trixie
# UID fixe (pas root, Sonar docker:S6471) : l'installation donne à cet UID
# la clé maître et donnees/pieces_jointes de l'hôte.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin vm-centrale
# Le .venv seul : les sources sont dans son site-packages (non éditable).
COPY --from=build /app/.venv /app/.venv
ARG VERSION=dev
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    VM_CENTRALE_VERSION=$VERSION
WORKDIR /app
USER vm-centrale
EXPOSE 8000
ENTRYPOINT ["python", "-m", "vm_centrale.exploitation"]
CMD ["serveur"]
