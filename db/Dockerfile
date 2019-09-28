FROM neo4j:3.5.9

COPY ./*.csv /var/lib/neo4j/import/

# load_data.sh must be run after container starts and db has loaded
COPY ./load_data.sh /var/lib/neo4j/load_data.sh
WORKDIR /var/lib/neo4j
RUN chmod +x load_data.sh