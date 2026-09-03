FROM python:3.12-alpine
WORKDIR /app
COPY target/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY target/app.py .
COPY seed/accounts.json /seed/accounts.json
EXPOSE 80
CMD ["python3", "app.py"]
