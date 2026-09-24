# Laptop dev image: Debian Bookworm (the Pi OS base) with libzbar0 from the same repo the Pi uses,
# so decoder behaviour on the laptop matches the Pi. Source is bind-mounted, not copied:
#   docker build -t vtb-dev .
#   docker run --rm -v "$PWD":/work vtb-dev
FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends libzbar0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# Tests that need zbar fail here instead of skipping if the library is missing.
# PYTHONPYCACHEPREFIX keeps Python from reading bytecode the host compiled into the bind-mounted
# __pycache__ directories, which put host paths into tracebacks (and into evidence captures) once.
ENV VTB_REQUIRE_ZBAR=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/pycache
CMD ["python", "-m", "pytest", "-p", "no:cacheprovider"]
