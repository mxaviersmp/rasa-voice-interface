FROM rasa/rasa:2.3.4-full

USER root
RUN pip install --upgrade pip

COPY *.py /app/
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 5005

USER 1001
