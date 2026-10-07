# Transformer Digital Twin — Simulator
# simulator_README §11
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir .

# Copy source
COPY simulator/ simulator/
COPY scenarios/ scenarios/
COPY tests/ tests/

# Default: run the CLI help
ENTRYPOINT ["python", "-m", "simulator.cli"]
CMD ["--help"]
