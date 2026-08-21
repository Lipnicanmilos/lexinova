FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
# `--timeout` a `--retries`: build uz dvakrat spadol na tom, ze citanie z
# files.pythonhosted.org vyprsalo uprostred stahovania zavislosti (ReadTimeout).
# Predvolene ma pip timeout 15 s a 5 pokusov, co pri pomalom PyPI nestaci a
# zhodi cely deploy kvoli vypadku, ktory o minutu neskor uz neplati.
RUN pip install --no-cache-dir --timeout 120 --retries 10 -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips=*"]
