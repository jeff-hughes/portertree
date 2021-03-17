from datetime import datetime
import json
import os
import shutil
import tempfile

from flask import Flask, render_template, request, url_for
from flask_mailman import Mail, EmailMessage
from db import DBConnect

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
GENDER_MAP = { "M": "man", "F": "woman" }
APP_ROOT = "/app"

app = Flask(__name__)
app.config.from_envvar('FLASK_SETTINGS')
mail = Mail(app)

db = DBConnect()


@app.route('/')
def index():
    raw_data_file = None
    try:
        files = os.listdir(os.path.join(APP_ROOT, "static/data"))
        files = [f for f in files if f.endswith(".zip")]
        if len(files) > 0:
            files = sorted(files)
            raw_data_file = "data/" + files[-1]
        else:
            raw_data_file = "data/" + export_data()
    except FileNotFoundError:
        raw_data_file = "data/" + export_data()
    return render_template("index.html", raw_data=raw_data_file)


@app.route('/search', methods=['GET'])
def search():
    if len(request.args) > 0:
        terms = request.args.get("search", "").split()
        res = db.search_name(terms)
        res = sorted(res, key=birthdate_sorter)
        for r in res:
            r["display_name"] = create_display_name(r)
            r["life_span"] = create_life_span(r)
        return render_template("search_results.html", results=res)
    else:
        return render_template("search_results.html", results=[])


@app.route('/advsearch', methods=['GET'])
def adv_search():
    if len(request.args) > 0:
        res = db.search_advanced(request.args)
        res = sorted(res, key=birthdate_sorter)
        for r in res:
            r["display_name"] = create_display_name(r)
            r["life_span"] = create_life_span(r)
        return render_template("search_results.html", results=res)
    else:
        return render_template("adv_search.html")


@app.route('/p/<pid>')
def person_page(pid):
    data = {}
    p = db.get_person(pid)
    data["focal"] = format_person_data(p, emphasis=True)

    # get info on focal person's parents
    data["parents"] = []
    parent_ids = []
    parents = db.get_parents(pid)

    if len(parents) > 0:
        focal_birth_order = None
        for pr in parents:
            pr_dict = format_person_data(pr)
            parent_ids.append(pr_dict["id"])
            data["parents"].append(pr_dict)

        data["parents"] = sorted(data["parents"], key=birthdate_sorter)

        # get info on focal person's siblings
        siblings = db.get_children(parent_ids[0], parent_ids[1])
        data["siblings"] = []
        for i, sib in enumerate(siblings):
            if sib["id"] == pid:
                data["siblings"].append(data["focal"])
                focal_birth_order = i
            else:
                sib_dict = format_person_data(sib)
                data["siblings"].append(sib_dict)

    # get info on focal person's spouse(s)
    data["marriages"] = []
    marriages = db.get_marriages(pid, p["in_tree"])
    for m in marriages:
        marriage = m["marriage"]

        marriage["marriage_date"] = format_date(marriage, "day", "month", "year")
        if is_attr(marriage, "divorced") and marriage["divorced"]:
            marriage["divorced_date"] = format_date(marriage, "divorced_day", "divorced_month", "divorced_year")

        spouse = format_person_data(m["spouse"])
        marriage["spouse"] = spouse

        children = db.get_children(pid, spouse["id"])
        s_children = []
        for c in children:
            s_children.append(format_person_data(c))

        marriage["children"] = s_children
        data["marriages"].append(marriage)

    # if focal person's parents aren't in the database, we have to
    # adjust the graphical tree properly since their data isn't nested
    # under their parents
    if len(parents) == 0:
        treegraph = data["focal"]
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
    if data["focal"]["id"] in extended:
        return render_template(f"extended/person{data['focal']['id']}.html", data=data)
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


@app.route('/report', methods=['GET', 'POST'])
def report():
    if request.method == "POST":
        message = { "text": "", "style": "" }
        if request.form["details"] != "" and request.form["name"] != "" and request.form["email"] != "":
            name = request.form["name"].strip().replace("\r", "").replace("\n", "")
            email = request.form["email"].strip().replace("\r", "").replace("\n", "")
            msg_body = f"From: {name} ({email})\nURL: {request.form['url']}\n\n{request.form['details']}"
            try:
                msg = EmailMessage(
                    subject="Update for Porter family tree",
                    body=msg_body,
                    to=[app.config["MAIL_TO_ADDRESS"]],
                    reply_to=[email])
                msg.send()
                message["text"] = "Message sent. Thank you!"
                message["style"] = "success"
            except:
                message["text"] = "Error sending message. Please try again later, or send the information directly to " + app.config["MAIL_TO_ADDRESS"]
                message["style"] = "error"
        else:
            message["text"] = "One or more required fields was empty. Please fill out all form fields."
            message["style"] = "error"
        return render_template("report.html", message=message["text"], message_style=message["style"])

    else:
        return render_template("report.html", url=request.args.get("url", ""))


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
    # in case of unknown values, 1000000 will ensure they are sorted
    # to the end
    year, month, day = (1000000, 1000000, 1000000)
    if "birth_year" in record and record["birth_year"] is not None:
        try:
            # if year is integer, great
            year = int(record["birth_year"])
        except ValueError:
            try:
                # this should handle cases like "1945?" and
                # "1945 or 1946"
                year = int(record["birth_year"][0:4])
            except:
                pass

    if "birth_month" in record and record["birth_month"] is not None:
        try:
            month = MONTHS.index(record["birth_month"]) + 1
        except:
            pass
    
    if "birth_day" in record and record["birth_day"] is not None:
        try:
            day = int(record["birth_day"])
        except ValueError:
            try:
                day = int(record["birth_day"][0:2])
            except:
                pass
    return (year, month, day)

def format_person_data(record, emphasis=False):
    output = dict(record)
    output["display_name"] = create_display_name(record)
    output["life_span"] = create_life_span(record)

    output["birth_date"] = format_date(record, "birth_day", "birth_month", "birth_year", all_blanks=True)
    output["death_date"] = format_date(record, "death_day", "death_month", "death_year", all_blanks=True)

    # used in graphical tree
    output["name"] = create_short_name(record)
    if is_attr(output, "gender") and output["gender"] in GENDER_MAP:
        output["class"] = GENDER_MAP[output["gender"]]
    output["extra"] = { "url": url_for("person_page", pid=output["id"]) }
    
    if emphasis:
        output["textClass"] = "emphasis"
    return output

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

def format_date(record, day, month, year, all_blanks=False):
    string = ""
    if is_attr(record, day):
        if is_attr(record, month):
            string += f"{record[month]} {record[day]}"
        else:
            string += f"_____ {record[day]}"
    elif is_attr(record, month):
        if all_blanks:
            string += f"{record[month]} __"
        else:
            string += record[month]
    elif all_blanks:
        string += "_____ __"
    if is_attr(record, year):
        if string != "":
            string += ", " + record[year]
        else:
            string += record[year]
    elif all_blanks:
        string += ", ____"
    return string

def export_data():
    date = datetime.now().strftime("%Y%m%d")
    tables = ["people", "marriages", "children"]
    with tempfile.TemporaryDirectory() as tmpdir:
        for table in tables:
            with open(os.path.join(tmpdir, f"{table}_{date}.csv"), "w") as f:
                db.export_data(table, f)

        os.makedirs(os.path.join(APP_ROOT, "static/data"), exist_ok=True)
        shutil.make_archive(os.path.join(APP_ROOT, "static/data", f"data_{date}"), "zip", tmpdir)
    return f"data_{date}.zip"


if __name__ == "__main__":
    # Only for debugging while developing
    app.run(host='0.0.0.0', debug=True, port=80)
