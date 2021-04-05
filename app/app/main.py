from datetime import datetime
import json
import os
import shutil
import tempfile
from urllib.parse import urlparse, urljoin

from flask import abort, Flask, flash, redirect, render_template, request, url_for
from flask_login import current_user, LoginManager, login_required, login_user, logout_user
from flask_mailman import Mail, EmailMessage

from auth import User, hash_pass
from db import DBConnect, DBEntry, DBEntryType, PERSON_COLS, MARRIAGE_COLS

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
GENDER_MAP = { "M": "man", "F": "woman" }
APP_ROOT = "/app"
CURR_YEAR = datetime.today().year

# special cases with extended notes about the early family members
EXTENDED_NOTES = ["1", "1.1", "1.2", "1.3", "1.5", "1.6", "1.7", "1.8"]

app = Flask(__name__)
app.config.from_envvar('FLASK_SETTINGS')
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = "admin_login"

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
    if p is None:
        abort(404)

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
        if len(parents) == 2:
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
    if len(parents) != 2:
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
    if pid in EXTENDED_NOTES:
        return render_template(f"extended/person{pid}.html", data=data)
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


# ADMIN ROUTES -------------------------------------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == "POST":
        user = User.get(request.form["username"])
        if (user is not None):
            pass_hash = hash_pass(request.form["password"])
            if (user.password == pass_hash):
                login_user(user)

                flash("Logged in successfully.")
                nexturl = request.args.get("next")
                if not is_safe_url(nexturl):
                    return abort(400)

        return redirect(nexturl or url_for("admin_index"))
    return render_template("admin/login.html")


@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for("index"))


@app.route('/admin', methods=['GET'])
@login_required
def admin_index():
    if len(request.args) > 0 and int(request.args.get("export")) == 1:
        # re-export data from database to CSV file
        data_fn = export_data()
        data_path = url_for("static", filename="data/"+data_fn)
        if data_path.startswith("/"):
            data_path = data_path[1:]
        data_path = request.url_root + data_path
        return render_template("admin/index.html", exported_data=data_path)
    else:
        return render_template("admin/index.html")


@app.route('/admin/editdata', methods=['GET', 'POST'])
@login_required
def admin_editdata():
    if request.method == "POST":
        focal = {}
        focal_data = None
        parents_data = []
        marriages_data = []
        spouses_data = []

        focal_update = request.form["update"] != ""
        for col in PERSON_COLS:
            if col == "in_tree":  # checkbox
                focal["in_tree"] = True if request.form.get("in_tree") else False
            elif focal_update:
                # if updating, explicitly set null values in case we're
                # erasing something
                col_data = request.form.get(col, "")
                if col_data == "":
                    col_data = None
                focal[col] = col_data
            elif request.form.get(col, "") != "":
                # only add non-empty values
                focal[col] = request.form.get(col)
        focal_data = DBEntry(focal, DBEntryType.PERSON, focal_update)

        if focal.get("id"):
            # get birth order based on last digit of ID
            focal_id = focal.get("id")
            digits = focal_id.split(".")
            last_num = "".join([c for c in digits[-1] if c.isnumeric()])

            parent_num = 1
            while request.form.get(f"parent_id_p{parent_num}") is not None:
                parent = {}
                update_p = request.form.get(f"update_p{parent_num}") != ""
                if update_p:
                    parent["id"] = request.form.get(f"update_p{parent_num}")
                parent["pid"] = request.form.get(f"parent_id_p{parent_num}")
                parent["cid"] = focal.get("id")
                parent["birth_order"] = int(last_num)
                parents_data.append(DBEntry(parent, DBEntryType.PARENT_CHILD_REL, update_p))
                parent_num += 1

            marriage_cols = [c for c in MARRIAGE_COLS if c not in ("pid1", "pid2")]
            marriage_num = 1
            while request.form.get(f"marriage_order_m{marriage_num}") is not None:
                marriage = {}
                update_m = request.form.get(f"update_m{marriage_num}") != ""
                if update_m:
                    marriage["id"] = request.form.get(f"update_m{marriage_num}")

                if focal.get("in_tree", False):
                    marriage["pid1"] = focal.get("id")
                    marriage["pid2"] = request.form.get(f"id_s{marriage_num}")
                else:
                    marriage["pid2"] = focal.get("id")
                    marriage["pid1"] = request.form.get(f"id_s{marriage_num}")

                for col in marriage_cols:
                    col_with_num = f"{col}_m{marriage_num}"
                    if col == "divorced":  # checkbox
                        marriage["divorced"] = True if request.form.get(col_with_num) else None
                    elif col == "marriage_order":
                        marriage["marriage_order"] = int(request.form.get(col_with_num))
                    elif update_m:
                        # if updating, explicitly set null values in
                        # case we're erasing something
                        col_data = request.form.get(col_with_num, "")
                        if col_data == "":
                            col_data = None
                        marriage[col] = col_data
                    elif request.form.get(col_with_num, "") != "":
                        # only add non-empty
                        marriage[col] = request.form.get(col_with_num)

                spouse = {}
                for col in PERSON_COLS:
                    col_with_num = f"{col}_s{marriage_num}"
                    if col == "in_tree":  # checkbox
                        spouse["in_tree"] = True if request.form.get(col_with_num) else False
                    elif update_m:
                        # if updating, explicitly set null values in
                        # case we're erasing something
                        col_data = request.form.get(col_with_num, "")
                        if col_data == "":
                            col_data = None
                        spouse[col] = col_data
                    elif request.form.get(col_with_num, "") != "":
                        # only add non-empty
                        spouse[col] = request.form.get(col_with_num)

                marriages_data.append(DBEntry(marriage, DBEntryType.MARRIAGE, update_m))
                spouses_data.append(DBEntry(spouse, DBEntryType.PERSON, update_m))
                marriage_num += 1

        # go through all queries one at a time, but rollback transaction
        # on failure
        queries = [focal_data] + spouses_data + parents_data + marriages_data
        db.run_transaction(queries)

        # return json.dumps({ "focal": focal_data, "marriages": marriages_data, "spouses": spouses_data })

    elif len(request.args) > 0:
        pid = request.args.get("search_id")
        if pid is not None:
            focal = db.get_person(pid)
            if focal is not None:
                parents = db.get_parents(pid)
                marriages = db.get_marriages(pid, focal["in_tree"])
                for i, m in enumerate(marriages):
                    marriages[i]["children"] = db.get_children(pid, m["spouse"]["id"])
                return render_template("admin/editdata.html", focal=focal, parents=parents, marriages=marriages, update=True)

    return render_template("admin/editdata.html", focal={}, parents={}, marriages={})


# Helper functions ---------------------------------------------------

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
    if is_attr(output, "birth_year") and record["birth_year"].isnumeric() and int(record["birth_year"]) >= (CURR_YEAR-100):
        output["death_date"] = format_date(record, "death_day", "death_month", "death_year")
        # assume the best if someone is less than 100 years old :)
    else:
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
    elif is_attr(record, "birth_year") and record["birth_year"].isnumeric() and int(record["birth_year"]) >= (CURR_YEAR-100):
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

    if string == "":
        string = None
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

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc


if __name__ == "__main__":
    # Only for debugging while developing
    app.run(host='0.0.0.0', debug=True, port=80)
