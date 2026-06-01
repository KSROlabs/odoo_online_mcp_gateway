FROM python:3.10-slim

WORKDIR /app

COPY odoo_online_mcp_gateway /app/odoo_online_mcp_gateway
COPY README.md /app/README.md
COPY docker/config.example.json /app/config.example.json

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8787

CMD ["python", "-m", "odoo_online_mcp_gateway", "http", "--host", "0.0.0.0", "--port", "8787"]

