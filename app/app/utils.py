from datetime import datetime
import os
import shutil
import tempfile
from urllib.parse import urlparse, urljoin

from flask import request, url_for

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
GENDER_MAP = { "M": "man", "F": "woman" }
CURR_YEAR = datetime.today().year

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
    if ((not is_attr(record, "death_place")
            and not is_attr(record, "buried"))
        and is_attr(record, "birth_year")
        and record["birth_year"].isnumeric()
        and int(record["birth_year"]) >= (CURR_YEAR-100)):

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
    elif ((not is_attr(record, "death_month")
            and not is_attr(record, "death_day")
            and not is_attr(record, "death_year")
            and not is_attr(record, "death_place")
            and not is_attr(record, "buried"))
        and is_attr(record, "birth_year")
        and record["birth_year"].isnumeric()
        and int(record["birth_year"]) >= (CURR_YEAR-100)):

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
            string += str(record[month])
    elif all_blanks:
        string += "_____ __"

    if is_attr(record, year):
        if string != "":
            string += ", " + str(record[year])
        else:
            string += str(record[year])
    elif all_blanks:
        string += ", ____"

    if string == "":
        string = None
    return string

def get_latest_export():
    try:
        files = os.listdir(os.path.join(os.environ.get("APP_ROOT"), "static/data"))
        files = [f for f in files if f.endswith(".zip")]
        if len(files) > 0:
            files = sorted(files)
            return files[-1]
        else:
            return None
    except FileNotFoundError:
        return None

def export_data(db_conn):
    date = datetime.now().strftime("%Y%m%d")
    tables = ["people", "marriages", "children"]
    with tempfile.TemporaryDirectory() as tmpdir:
        for table in tables:
            with open(os.path.join(tmpdir, f"{table}_{date}.csv"), "w") as f:
                db_conn.export_data(table, f)

        os.makedirs(os.path.join(os.environ.get("APP_ROOT"), "static/data"), exist_ok=True)
        shutil.make_archive(os.path.join(os.environ.get("APP_ROOT"), "static/data", f"data_{date}"), "zip", tmpdir)
    return f"data_{date}.zip"

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc