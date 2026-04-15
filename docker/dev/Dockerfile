FROM python:3.11-slim

LABEL maintainer="Train-Pet-Pipeline"
LABEL description="Unified development environment for pet-pipeline"

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    make \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    ruff>=0.4 \
    mypy>=1.10 \
    pytest>=8.0 \
    pip-tools>=7.0

WORKDIR /workspace

CMD ["bash"]
