FROM python:3.12

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=setup.settings

WORKDIR /app

# Índice do PyTorch: CPU por padrão. O perfil `compose.gpu.yaml` sobrescreve
# com o índice CUDA (ex.: cu124) para gerar a imagem finance-web:gpu.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

# A imagem `python:3.12` (não-slim) já traz curl e libgomp1, necessários
# respectivamente para o healthcheck e para o PyTorch. Isso evita depender
# do apt durante o build, que pode estar bloqueado em algumas redes.
RUN python -c "import ctypes; ctypes.CDLL('libgomp.so.1')"

# Instala o PyTorch antes das demais dependências para evitar
# que o pip baixe a variante errada (CUDA gigante no perfil CPU).
RUN pip install --upgrade pip \
    && pip install torch --index-url ${TORCH_INDEX_URL}

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/data /app/staticfiles /app/exports \
    && python manage.py collectstatic --noinput

RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["gunicorn", "setup.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
