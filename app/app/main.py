import os

from py2neo import Graph, NodeMatcher

#from app import app
from flask import Flask, render_template
app = Flask(__name__)

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

graph = Graph(host='neo4j', auth=(os.environ["NEO4J_USERNAME"],
                                  os.environ["NEO4J_PASSWORD"]))
matcher = NodeMatcher(graph)


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
        ORDER BY child.birth_order", {'id': '1'}).data()
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


@app.route('/p/<pid>')
def person_page(pid):
    data = {}
    p = matcher.match("Person", id=pid).first()
    data["focus"] = dict(p)
    data["focus"]["display_name"] = create_display_name(p)
    data["focus"]["life_span"] = create_life_span(p)

    # get info on focal person's parents
    data["parents"] = []
    parents = graph.match((None, p), r_type="PARENT_OF")
    for pr in parents:
        graph.pull(pr.start_node)
        pr_dict = dict(pr.start_node)
        pr_dict["display_name"] = create_display_name(pr.start_node)
        pr_dict["life_span"] = create_life_span(pr.start_node)

        # get info on focal person's siblings
        # TODO: this currently will end up duplicating all the full
        # siblings (half-siblings will only appear once); maybe there's
        # a more efficient way to create this list
        pr_dict["children"] = []
        pr_children = graph.match((pr.start_node, ), r_type="PARENT_OF")
        for prc in pr_children:
            graph.pull(prc.end_node)
            prc_dict = dict(prc.end_node)
            prc_dict["display_name"] = create_display_name(prc.end_node)
            prc_dict["life_span"] = create_life_span(prc.start_node)
            pr_dict["children"].append(prc_dict)
        pr_dict["children"] = sorted(pr_dict["children"],
            key=lambda k: k['birth_order'] if 'birth_order' in k else 1000000)
        data["parents"].append(pr_dict)
    data["parents"] = sorted(data["parents"], key=birthdate_sorter)

    # get info on focal person's spouse(s)
    data["spouses"] = []
    spouses = graph.match(set((p, )), r_type="MARRIED_TO")
    for s in spouses:
        graph.pull(s.end_node)
        s_dict = dict(s.end_node)
        s_dict["display_name"] = create_display_name(s.end_node)
        s_dict["life_span"] = create_life_span(s.start_node)
        data["spouses"].append(s_dict)

    # get info on focal person's children
    data["children"] = []
    children = graph.match((p, ), r_type="PARENT_OF")
    for c in children:
        graph.pull(c.end_node)
        c_dict = dict(c.end_node)
        c_dict["display_name"] = create_display_name(c.end_node)
        c_dict["life_span"] = create_life_span(c.start_node)
        data["children"].append(c_dict)
    data["children"] = sorted(data["children"],
        key=lambda k: k["birth_order"] if "birth_order" in k else 1000000)

    return render_template("person.html", data=data)


# Helper functions

def is_attr(record, attr):
    if attr in record and record[attr] is not None:
        return True
    else:
        return False

def birthdate_sorter(record):
    """Function for use in sorted(), to sort birthdates in chronological
    order. Returns a tuple of (year, month, day).
    """
    year, month, day = (None, None, None)
    if "birth_year" in record and record["birth_year"] is not None:
        try:
            # if year is integer, great
            year = int(record["birth_year"])
        except ValueError:
            try:
                # this should handle cases like "1945?" and
                # "1945 or 1946"
                year = int(record["birth_year"][0:4])
            except ValueError:
                year = 1000000  # sort to end

    if "birth_month" in record and record["birth_month"] is not None:
        try:
            month = MONTHS.index(record["birth_month"]) + 1
        except ValueError:
            month = 1000000  # sort to end
    
    if "birth_day" in record and record["birth_day"] is not None:
        try:
            day = int(record["birth_day"])
        except ValueError:
            try:
                day = int(record["birth_day"][0:2])
            except ValueError:
                day = 1000000  # sort to end
    return (year, month, day)

def create_display_name(record):
    name = ""
    if is_attr(record, "first_name"):
        if record["first_name"] == "Unnamed":
            return record["first_name"]
        name += record["first_name"]
    else:
        name += "_____"
    if is_attr(record, "nickname"):
        name += f" ({record['nickname']})"
    if is_attr(record, "middle_name1"):
        if record["pref_name"] == "M1":
            name += f" <u>{record['middle_name1']}</u>"
        else:
            name += " " + record['middle_name1']
    if is_attr(record, "middle_name2"):
        if record["pref_name"] == "M2":
            name += f" <u>{record['middle_name2']}</u>"
        else:
            name += " " + record['middle_name2']
    if is_attr(record, "last_name"):
        name += " " + record["last_name"]
    else:
        name += " _____"
    return name

def create_life_span(record):
    string = ""
    if is_attr(record, "birth_year"):
        string += f" ({record['birth_year']}"
    else:
        string += " (? "

    if is_attr(record, "death_year"):
        string += f" - {record['death_year']})"
    elif is_attr(record, "birth_year") and int(record["birth_year"]) >= (2019-100):
        string += " - present)"
        # assume the best if someone is less than 100 years old :)
    else:
        string += " - ?)"
    return string


if __name__ == "__main__":
    # Only for debugging while developing
    app.run(host='0.0.0.0', debug=True, port=80)
