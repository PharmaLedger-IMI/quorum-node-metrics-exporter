FROM python:3.9-alpine

COPY source/requirements.txt .
RUN pip install -r requirements.txt

USER nobody
COPY source/main.py .
COPY source/utils/*.py ./utils/
CMD [ "python", "main.py" ]
