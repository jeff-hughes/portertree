import json
import os

from py2neo import Graph, NodeMatcher

#from app import app
from flask import Flask, render_template, request, url_for
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
    gender_dict = { "M": "man", "F": "woman" }

    p = matcher.match("Person", id=pid).first()
    data["focus"] = dict(p)
    data["focus"]["display_name"] = create_display_name(p)
    data["focus"]["name"] = create_short_name(p)
    data["focus"]["life_span"] = create_life_span(p)
    if is_attr(data["focus"], "gender") and data["focus"]["gender"] in gender_dict:
        data["focus"]["class"] = gender_dict[data["focus"]["gender"]]
    data["focus"]["textClass"] = "emphasis"
    data["focus"]["extra"] = { "url": url_for("person_page", pid=data["focus"]["id"]) }

    # get info on focal person's parents
    data["parents"] = []
    parent_ids = [None, None]
    parents = graph.match((None, p), r_type="PARENT_OF")

    if len(parents) > 0:
        focal_birth_order = None
        for pr in parents:
            graph.pull(pr.start_node)
            pr_dict = dict(pr.start_node)
            pr_dict["display_name"] = create_display_name(pr.start_node)
            pr_dict["name"] = create_short_name(pr.start_node)
            pr_dict["life_span"] = create_life_span(pr.start_node)
            if is_attr(pr_dict, "gender") and pr_dict["gender"] in gender_dict:
                pr_dict["class"] = gender_dict[pr_dict["gender"]]
            pr_dict["extra"] = { "url": url_for("person_page", pid=pr_dict["id"]) }

            if pr_dict["in_tree"]:
                parent_ids[0] = pr_dict["id"]
            else:
                parent_ids[1] = pr_dict["id"]
            data["parents"].append(pr_dict)

        data["parents"] = sorted(data["parents"], key=birthdate_sorter)

        # get info on focal person's siblings
        siblings = get_children_of_parents(parent_ids[0], parent_ids[1])
        data["siblings"] = []
        for i, sib in enumerate(siblings):
            if sib["id"] == pid:
                data["siblings"].append(data["focus"])
                focal_birth_order = i
            else:
                sib_dict = dict(sib)
                sib_dict["display_name"] = create_display_name(sib)
                sib_dict["name"] = create_short_name(sib)
                sib_dict["life_span"] = create_life_span(sib)
                if is_attr(sib, "gender") and sib["gender"] in gender_dict:
                    sib_dict["class"] = gender_dict[sib["gender"]]
                sib_dict["extra"] = { "url": url_for("person_page", pid=sib["id"]) }
                data["siblings"].append(sib_dict)

    # get info on focal person's spouse(s)
    data["marriages"] = []
    spouses = graph.match(set((p, )), r_type="MARRIED_TO").order_by("_.marriage_order")
    for i, s in enumerate(spouses):
        if data["focus"]["in_tree"]:
            node = s.end_node
        else:
            node = s.start_node
        graph.pull(node)
        s_dict = dict(node)

        s_dict["display_name"] = create_display_name(node)
        s_dict["name"] = create_short_name(node)
        s_dict["life_span"] = create_life_span(node)
        if is_attr(s_dict, "gender") and s_dict["gender"] in gender_dict:
            s_dict["class"] = gender_dict[s_dict["gender"]]
        s_dict["extra"] = { "url": url_for("person_page", pid=s_dict["id"]) }

        data["marriages"].append({ "spouse": s_dict })

        children = get_children_of_parents(pid, s_dict["id"])
        s_children = []
        for c in children:
            c_dict = dict(c)
            c_dict["display_name"] = create_display_name(c)
            c_dict["name"] = create_short_name(c)
            c_dict["life_span"] = create_life_span(c)
            if is_attr(c, "gender") and c["gender"] in gender_dict:
                c_dict["class"] = gender_dict[c["gender"]]
            c_dict["extra"] = { "url": url_for("person_page", pid=c["id"]) }
            s_children.append(c_dict)

        data["marriages"][i]["children"] = s_children

    # if focal person's parents aren't in the database, we have to
    # adjust the graphical tree properly since their data isn't nested
    # under their parents
    if len(parents) == 0:
        treegraph = data["focus"]
        treegraph["marriages"] = data["marriages"]
    else:
        treegraph = data["parents"][0]
        treegraph["marriages"] = [{}]
        treegraph["marriages"][0]["spouse"] = data["parents"][1]
        treegraph["marriages"][0]["children"] = data["siblings"]

        if len(data["marriages"]) > 0:
            treegraph["marriages"][0]["children"][focal_birth_order]["marriages"] = data["marriages"]

    # add data formatted for the graphical tree
    data["treegraph"] = json.dumps([treegraph])

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

def create_short_name(record):
    name = ""
    if is_attr(record, "first_name"):
        if record["first_name"] == "Unnamed":
            return record["first_name"]
        name += record["first_name"]
    else:
        name += "_____"
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

def get_children_of_parents(pid1, pid2):
    return graph.run("MATCH (parent1:Person { id: {id1} })-[:PARENT_OF]->(child:Person)<-[:PARENT_OF]-(parent2:Person { id: {id2} }) \
    RETURN child.id AS id, \
        child.first_name AS first_name, \
        child.nickname AS nickname, \
        child.middle_name1 AS middle_name1, \
        child.middle_name2 AS middle_name2, \
        child.last_name AS last_name, \
        child.pref_name AS pref_name, \
        child.gender AS gender, \
        child.birth_month AS birth_month, \
        child.birth_day AS birth_day, \
        child.birth_year AS birth_year, \
        child.death_month AS death_month, \
        child.death_day AS death_day, \
        child.death_year AS death_year, \
        child.birth_order AS order \
    ORDER BY child.birth_order", {'id1': pid1, 'id2': pid2}).data()


if __name__ == "__main__":
    # Only for debugging while developing
    app.run(host='0.0.0.0', debug=True, port=80)
