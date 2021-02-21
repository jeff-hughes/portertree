import os

from py2neo import Graph, NodeMatcher

#from app import app
from flask import Flask, render_template, request
app = Flask(__name__)

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

graph = Graph(host='neo4j', auth=(os.environ["NEO4J_USERNAME"],
                                  os.environ["NEO4J_PASSWORD"]))
matcher = NodeMatcher(graph)


@app.route('/')
def index():
    # records = graph.run("MATCH (child:Person)<-[:PARENT_OF]-(parent:Person { id: {id} }) \
    #     RETURN child.first_name AS first_name, \
    #         child.nickname AS nickname, \
    #         child.middle_name1 AS middle_name1, \
    #         child.middle_name2 AS middle_name2, \
    #         child.last_name AS last_name, \
    #         child.pref_name AS pref_name, \
    #         child.gender AS gender, \
    #         child.birth_month AS birth_month, \
    #         child.birth_day AS birth_day, \
    #         child.birth_year AS birth_year, \
    #         child.birth_place AS birth_place, \
    #         child.death_month AS death_month, \
    #         child.death_day AS death_day, \
    #         child.death_year AS death_year, \
    #         child.death_place AS death_place, \
    #         child.buried AS buried, \
    #         child.additional_notes AS additional_notes, \
    #         child.birth_order AS order \
    #     ORDER BY child.birth_order", {'id': '1'}).data()
    # string = ""
    # for record in records:
    #     # name data
    #     string = "{} {}".format(string, record['first_name'])
    #     if is_attr(record, 'nickname'):
    #         string = "{} ({})".format(string, record['nickname'])
    #     if is_attr(record, 'middle_name1'):
    #         if record['pref_name'] == 'M1':
    #             string = "{} <u>{}</u>".format(string, record['middle_name1'])
    #         else:
    #             string = "{} {}".format(string, record['middle_name1'])
    #     if is_attr(record, 'middle_name2'):
    #         if record['pref_name'] == 'M2':
    #             string = "{} <u>{}</u>".format(string, record['middle_name2'])
    #         else:
    #             string = "{} {}".format(string, record['middle_name2'])
    #     string = "{} {}".format(string, record['last_name'])

    #     # birth and death years
    #     if is_attr(record, 'birth_year'):
    #         string = "{} ({}".format(string, record['birth_year'])
    #     else:
    #         string = "{} (? ".format(string)

    #     if is_attr(record, 'death_year'):
    #         string = "{} - {})<br>".format(string, record['death_year'])
    #     elif is_attr(record, 'birth_year') and int(record['birth_year']) >= (2019-100):
    #         string = "{} - present)<br>".format(string)
    #         # assume the best if someone is less than 100 years old :)
    #     else:
    #         string = "{} - ?)<br>".format(string)
    # return string
    return render_template("index.html")


@app.route('/search', methods=['GET'])
def search():
    if len(request.args) > 0:
        terms = request.args.get("search", "").split()
        match_args = []
        for t in terms:
            # case insensitive matching for each space-separated term
            # in the query
            match_args.append(f"(_.first_name =~ '(?i).*{t}.*' OR _.nickname =~ '(?i).*{t}.*' OR _.middle_name1 =~ '(?i).*{t}.*' OR _.middle_name2 =~ '(?i).*{t}.*' OR _.last_name =~ '(?i).*{t}.*')")
        # apparently using multiple `where()` methods results in an
        # implicit "OR", so we're joining the queries together into one
        # big statement instead
        res = list(matcher.match("Person").where(" AND ".join(match_args)).order_by("_.birth_year"))
        for r in res:
            r["display_name"] = create_display_name(r)
            r["life_span"] = create_life_span(r)
        return render_template("search_results.html", results=res)
    else:
        return render_template("search_results.html", results=[])


@app.route('/advsearch', methods=['GET'])
def adv_search():
    if len(request.args) > 0:
        match_args = {}
        for k, v in request.args.items():
            if v != "":
                # suffix provides details to Neo4j about search type
                if k == "middle_name":
                    match_args["middle_name1__contains"] = v
                    match_args["middle_name2__contains"] = v
                elif "name" in k or k == "buried" or k == "additional_notes":
                    match_args[k + "__contains"] = v
                else:
                    match_args[k + "__exact"] = v
        
        res = list(matcher.match("Person", **match_args).order_by("_.birth_year"))
        for r in res:
            r["display_name"] = create_display_name(r)
            r["life_span"] = create_life_span(r)
        return render_template("search_results.html", results=res)
    else:
        return render_template("adv_search.html")


@app.route('/p/<pid>')
def person_page(pid):
    data = {}
    p = matcher.match("Person", id=pid).first()
    data["focus"] = dict(p)
    data["focus"]["display_name"] = create_display_name(p)
    data["focus"]["life_span"] = create_life_span(p)

    # if ID ends with a letter (e.g., "1.1.3a"), then this person
    # married into the family
    by_marriage = pid[-1].isalpha()

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
            prc_dict["life_span"] = create_life_span(prc.end_node)
            pr_dict["children"].append(prc_dict)
        pr_dict["children"] = sorted(pr_dict["children"],
            key=lambda k: k['birth_order'] if 'birth_order' in k else 1000000)
        data["parents"].append(pr_dict)
    data["parents"] = sorted(data["parents"], key=birthdate_sorter)

    # get info on focal person's spouse(s)
    data["spouses"] = []
    spouses = graph.match(set((p, )), r_type="MARRIED_TO")
    for s in spouses:
        if by_marriage:
            node = s.start_node
        else:
            node = s.end_node
        graph.pull(node)
        s_dict = dict(node)
        s_dict["display_name"] = create_display_name(node)
        s_dict["life_span"] = create_life_span(node)
        data["spouses"].append(s_dict)

    # get info on focal person's children
    data["children"] = []
    children = graph.match((p, ), r_type="PARENT_OF")
    for c in children:
        graph.pull(c.end_node)
        c_dict = dict(c.end_node)
        c_dict["display_name"] = create_display_name(c.end_node)
        c_dict["life_span"] = create_life_span(c.end_node)
        data["children"].append(c_dict)
    data["children"] = sorted(data["children"],
        key=lambda k: k["birth_order"] if "birth_order" in k else 1000000)

    # special cases with extended notes about the early family members
    extended = ["1", "1.1", "1.2", "1.3", "1.5", "1.6", "1.7", "1.8"]
    if data["focus"]["id"] in extended:
        return render_template(f"extended/person{data['focus']['id']}.html", data=data)
    else:
        return render_template("person.html", data=data)


@app.route('/in-memoriam')
def in_memoriam():
    return render_template("in_memoriam.html")


@app.route('/preface')
def preface():
    return render_template("preface.html")


@app.route('/numbering')
def numbering():
    return render_template("numbering.html")


@app.route('/maps')
def maps():
    return render_template("maps.html")


@app.route('/technical-details')
def technical_details():
    return render_template("technical_details.html")


@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html'), 404


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
    elif is_attr(record, "birth_year") and record["birth_year"].isnumeric() and int(record["birth_year"]) >= (2019-100):
        string += " - present)"
        # assume the best if someone is less than 100 years old :)
    else:
        string += " - ?)"
    return string


if __name__ == "__main__":
    # Only for debugging while developing
    app.run(host='0.0.0.0', debug=True, port=80)
