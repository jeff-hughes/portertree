import os

from py2neo import Graph

#from app import app
from flask import Flask
app = Flask(__name__)

graph = Graph(host='neo4j', auth=(os.environ["NEO4J_USERNAME"],
    os.environ["NEO4J_PASSWORD"]))

def is_attr(record, attr):
    if attr in record and record[attr] is not None:
        return True
    else:
        return False


@app.route('/')
def index():
    records = graph.run("MATCH (child:Person)<-[:PARENT_OF]-(parent:Person { id: {id} }) \
        RETURN child.first_name AS first_name, \
            child.nickname AS nickname, \
            child.middle_name1 AS middle_name1, \
            child.middle_name2 AS middle_name2, \
            child.last_name AS last_name, \
            child.pref_name AS pref_name, \
            child.gender AS gender, \
            child.birth_month AS birth_month, \
            child.birth_day AS birth_day, \
            child.birth_year AS birth_year, \
            child.birth_place AS birth_place, \
            child.death_month AS death_month, \
            child.death_day AS death_day, \
            child.death_year AS death_year, \
            child.death_place AS death_place, \
            child.buried AS buried, \
            child.additional_notes AS additional_notes, \
            child.birth_order AS order \
        ORDER BY child.birth_order",
        {'id': '1'}).data()
    string = ""
    for record in records:
        # name data
        string = "{} {}".format(string, record['first_name'])
        if is_attr(record, 'nickname'):
            string = "{} ({})".format(string, record['nickname'])
        if is_attr(record, 'middle_name1'):
            if record['pref_name'] == 'M1':
                string = "{} <u>{}</u>".format(string, record['middle_name1'])
            else:
                string = "{} {}".format(string, record['middle_name1'])
        if is_attr(record, 'middle_name2'):
            if record['pref_name'] == 'M2':
                string = "{} <u>{}</u>".format(string, record['middle_name2'])
            else:
                string = "{} {}".format(string, record['middle_name2'])
        string = "{} {}".format(string, record['last_name'])

        # birth and death years
        if is_attr(record, 'birth_year'):
            string = "{} ({}".format(string, record['birth_year'])
        else:
            string = "{} (? ".format(string)

        if is_attr(record, 'death_year'):
            string = "{} - {})<br>".format(string, record['death_year'])
        elif is_attr(record, 'birth_year') and int(record['birth_year']) >= (2019-100):
            string = "{} - present)<br>".format(string)
            # assume the best if someone is less than 100 years old :)
        else:
            string = "{} - ?)<br>".format(string)
    return string


if __name__ == "__main__":
    # Only for debugging while developing
    app.run(host='0.0.0.0', debug=True, port=80)
