# syntax=docker/dockerfile:1

FROM python:3.12-bullseye

WORKDIR /opt/oracle

RUN apt-get update && apt-get install -y libaio1 
RUN wget https://download.oracle.com/otn_software/linux/instantclient/instantclient-basiclite-linuxx64.zip && \
    unzip instantclient-basiclite-linuxx64.zip && rm -f instantclient-basiclite-linuxx64.zip && \
    cd /opt/oracle/instantclient* && rm -f *jdbc* *occi* *mysql* *README *jar uidrvci genezi adrci && \
    echo /opt/oracle/instantclient* > /etc/ld.so.conf.d/oracle-instantclient.conf && ldconfig

WORKDIR /app

ENV PYTHONIOENCODING=utf-8

ENV TZ="America/Sao_Paulo"

ENV PYTHONUNBUFFERED=1

RUN apt-get update

# estabelece padrão brasileiro no locale
RUN apt-get install -y locales locales-all
ENV LC_ALL pt_BR.UTF-8
ENV LANG pt_BR.UTF-8
ENV LANGUAGE pt_BR.UTF-8

COPY requirements.txt requirements.txt

RUN pip install --upgrade pip

#Pip command without proxy setting
RUN pip install -r requirements.txt

COPY . .

RUN chmod +x ./entrypoint.sh
ENTRYPOINT ["sh", "entrypoint.sh"]
