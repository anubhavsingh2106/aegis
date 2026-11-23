
FROM python:3.13-slim

# Install pytest when building the trusted runner image.
RUN pip install --no-cache-dir pytest

WORKDIR /workspace

# Disable bytecode writes during test execution.
ENV PYTHONDONTWRITEBYTECODE=1

# Run tests without creating pytest's cache.
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
