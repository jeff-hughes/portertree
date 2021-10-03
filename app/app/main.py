import json
import os
from urllib.parse import urlparse, urljoin

from flask import abort, Flask, flash, redirect, render_template, request, url_for
from flask_login import current_user, LoginManager, login_required, login_user, logout_user
from flask_mailman import Mail, EmailMessage

from auth import User, hash_pass
from db import DBConnect, DBEntry, DBEntryType, PERSON_COLS, MARRIAGE_COLS
import utils

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
    raw_data_file = utils.get_latest_export()
    if raw_data_file is None:
        raw_data_file = utils.export_data(db)
    raw_data_file = "data/" + raw_data_file
    return render_template("index.html", raw_data=raw_data_file)


@app.route('/search', methods=['GET'])
def search():
    if len(request.args) > 0:
        terms = request.args.get("search", "").split()
        res = db.search_name(terms)
        res = sorted(res, key=utils.birthdate_sorter)
        for r in res:
            r["display_name"] = utils.create_display_name(r)
            r["life_span"] = utils.create_life_span(r)
        return render_template("search_results.html", results=res)
    else:
        return render_template("search_results.html", results=[])


@app.route('/advsearch', methods=['GET'])
def adv_search():
    if len(request.args) > 0:
        res = db.search_advanced(request.args)
        res = sorted(res, key=utils.birthdate_sorter)
        for r in res:
            r["display_name"] = utils.create_display_name(r)
            r["life_span"] = utils.create_life_span(r)
        return render_template("search_results.html", results=res)
    else:
        return render_template("adv_search.html")


@app.route('/p/<pid>')
def person_page(pid):
    data = {}
    p = db.get_person(pid)
    if p is None:
        abort(404)

    data["focal"] = utils.format_person_data(p, focal=True)

    # get info on focal person's parents
    data["parents"] = []
    bio_parent_ids = []
    adopt_parent_ids = []
    parent_ids = []
    parents = db.get_parents(pid)

    if len(parents) > 0:
        focal_birth_order = None
        for pr in parents:
            pr_dict = utils.format_person_data(pr)
            if pr["adoptive"]:
                adopt_parent_ids.append(pr_dict["id"])
            else:
                bio_parent_ids.append(pr_dict["id"])
            data["parents"].append(pr_dict)

        data["parents"] = sorted(data["parents"], key=utils.birthdate_sorter)

        # there are a few cases in the data where we have two biological
        # parents listed, plus an adoptive parent, and the graphical tree
        # in particular just doesn't handle more than two parents very
        # well...
        if len(adopt_parent_ids) > 0 and len(bio_parent_ids) < 2:
            parent_ids = bio_parent_ids + adopt_parent_ids
        else:
            parent_ids = bio_parent_ids

        # get info on focal person's siblings
        if len(parent_ids) == 2:
            siblings = db.get_children(parent_ids[0], parent_ids[1])
            data["siblings"] = []
            for i, sib in enumerate(siblings):
                if sib["id"] == pid:
                    data["siblings"].append(data["focal"])
                    focal_birth_order = i
                else:
                    sib_dict = utils.format_person_data(sib)
                    data["siblings"].append(sib_dict)

    # get info on focal person's spouse(s)
    data["marriages"] = []
    marriages = db.get_marriages(pid)
    for m in marriages:
        marriage = m["marriage"]

        marriage["marriage_date"] = utils.format_date(marriage, "married_day", "married_month", "married_year")
        if utils.is_attr(marriage, "divorced") and marriage["divorced"]:
            marriage["divorced_date"] = utils.format_date(marriage, "divorced_day", "divorced_month", "divorced_year")

        spouse = utils.format_person_data(m["spouse"])
        marriage["spouse"] = spouse

        children = db.get_children(pid, spouse["id"])
        s_children = []
        for c in children:
            s_children.append(utils.format_person_data(c))

        marriage["children"] = s_children
        data["marriages"].append(marriage)

    # if focal person's parents aren't in the database, we have to
    # adjust the graphical tree properly since their data isn't nested
    # under their parents
    if len(parent_ids) != 2:
        treegraph = data["focal"]
        treegraph["marriages"] = data["marriages"]
    elif len(parents) > 2:
        # special case of biological and adoptive parents
        tree_parents = [p for p in data["parents"] if p["id"] in parent_ids]
        treegraph = tree_parents[0]
        treegraph["marriages"] = [{}]
        treegraph["marriages"][0]["spouse"] = tree_parents[1]
        treegraph["marriages"][0]["children"] = data["siblings"]
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


@app.route('/report')
def report():
    return render_template("report.html", url=request.args.get("url", ""))

@app.route('/last-export-date')
def last_export():
    raw_data_file = utils.get_latest_export()
    if raw_data_file is None:
        raw_data_file = utils.export_data(db)

    no_ext = raw_data_file.split(".")[0]
    date = no_ext.split("_")[1]
    return date

@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html'), 404


# ADMIN ROUTES -------------------------------------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == "POST":
        user = User.get(request.form["username"])
        if user is not None:
            pass_hash = hash_pass(request.form["password"])
            if user.password == pass_hash:
                login_user(user)

                flash("Logged in successfully.")
                nexturl = request.args.get("next")
                if not utils.is_safe_url(nexturl):
                    return abort(400)
                return redirect(nexturl or url_for("admin_index"))
        return render_template("admin/login.html", message="Error: Incorrect username and/or password.", message_style="error")
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
        data_fn = utils.export_data(db)
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
                parent["adoptive"] = request.form.get(f"parent_adoptive_p{parent_num}")
                parents_data.append(DBEntry(parent, DBEntryType.PARENT_CHILD_REL, update_p))
                parent_num += 1

            marriage_cols = [c for c in MARRIAGE_COLS if c not in ("id", "pid1", "pid2")]
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
                    elif col == "common_law":  # checkbox
                        marriage["common_law"] = True if request.form.get(col_with_num) else None
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
                marriages = db.get_marriages(pid)
                for i, m in enumerate(marriages):
                    marriages[i]["children"] = db.get_children(pid, m["spouse"]["id"])
                return render_template("admin/editdata.html", focal=focal, parents=parents, marriages=marriages, update=True)

    return render_template("admin/editdata.html", focal={}, parents={}, marriages={})


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


if __name__ == "__main__":
    # Only for debugging while developing
    app.run(host='0.0.0.0', debug=True, port=80)
