# Ubuntu + distro FreeCAD packages are more reliable than python-slim + apt freecad
# (fewer missing Qt/GL bits). Qt uses offscreen mode; Xvfb wraps CLI when /.dockerenv exists.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_APP=app.py \
    QT_QPA_PLATFORM=offscreen

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        freecad \
        xvfb \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && (command -v freecadcmd || command -v FreeCADCmd || (echo "FreeCAD CLI missing" && exit 1))

RUN python3 -m venv /opt/stlfactory
ENV PATH="/opt/stlfactory/bin:$PATH"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5000"]
