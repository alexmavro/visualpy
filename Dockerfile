FROM python:3.12-slim
WORKDIR /app

COPY pyproject.toml README.md ./
COPY visualpy/ visualpy/
COPY static/ static/
RUN pip install --no-cache-dir -e ".[llm]"

COPY tests/fixtures/agentic_workflows/ /demo_project/

ARG GEMINI_API_KEY=""
RUN if [ -n "$GEMINI_API_KEY" ]; then \
        GEMINI_API_KEY=$GEMINI_API_KEY visualpy analyze /demo_project --summarize -o /demo_data.json; \
    else \
        visualpy analyze /demo_project -o /demo_data.json; \
    fi

EXPOSE 8123
CMD ["visualpy", "serve", "--from-json", "/demo_data.json", "--host", "0.0.0.0", "--port", "8123"]
