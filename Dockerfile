FROM python:3.11.4

RUN mkdir subtitles

RUN apt-get update && apt-get install -y mkvtoolnix

WORKDIR /app

RUN mkdir grabs
RUN mkdir progress
RUN mkdir -p temp/subs

COPY main.py .
COPY episodus.py .
COPY configus.py .
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

ENV ISDOCKER=docker

CMD ["python", "main.py"]


