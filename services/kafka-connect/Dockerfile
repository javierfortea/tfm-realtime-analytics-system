FROM confluentinc/cp-server-connect-base:7.2.2

RUN confluent-hub install --no-prompt confluentinc/kafka-connect-s3:10.3.0

ENV CONNECT_REST_PORT=8080
EXPOSE 8080
