from datetime import datetime
import os
import shutil
import tempfile
from typing import Any, Dict, Optional, List, Tuple
from urllib.parse import urlparse, urljoin

from flask import request, url_for
from db import DBConnect

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
GENDER_MAP = { "M": "man", "F": "woman" }
CURR_YEAR = datetime.today().year

def is_attr(record: Dict[str, Any], attr: str) -> bool:
    """Identifies if attr exists in the record, and is non-empty."""
    if attr in record and record[attr] is not None and record[attr] != "":
        return True
    else:
        return False

def birthdate_sorter(record: Dict[str, Any]) -> Tuple[int, int, int]:
    """Function for use in sorted(), to sort birthdates in chronological
    order. Returns a tuple of (year, month, day).
    """
    # in case of unknown values, 1000000 will ensure they are sorted
    # to the end
    year, month, day = (1000000, 1000000, 1000000)
    if is_attr(record, "birth_year"):
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

    if is_attr(record, "birth_month"):
        try:
            month = MONTHS.index(record["birth_month"]) + 1
        except:
            pass
    
    if is_attr(record, "birth_day"):
        try:
            day = int(record["birth_day"])
        except ValueError:
            try:
                day = int(record["birth_day"][0:2])
            except:
                pass
    return (year, month, day)

def format_person_data(record: Dict[str, Any], focal: bool = False) -> Dict[str, Any]:
    """Given a dictionary of Person data from the database, this adds
    some additional derived fields, including the formatted name and
    life span, age or age at death, and formatted birth and death dates.
    Returns the original dict supplemented with these additional fields.
    """
    output = dict(record)
    output["display_name"] = create_display_name(record)
    if focal:
        output["title_name"] = create_display_name(record, underline=False)
    output["life_span"] = create_life_span(record)

    output["birth_date"] = format_date(record, "birth_day", "birth_month", "birth_year", all_blanks=True)
    output["deceased"] = is_deceased(record)

    if focal and output["deceased"]:
        output["death_date"] = format_date(record, "death_day", "death_month", "death_year", all_blanks=True)

        age_at_death, unsure = calc_age(record, deceased=True)
        if age_at_death is not None:
            if unsure > 0:
                output["age_at_death"] = f"{age_at_death}-{age_at_death+unsure}"
            else:
                output["age_at_death"] = str(age_at_death)
    else:
        output["death_date"] = format_date(record, "death_day", "death_month", "death_year")

        age, unsure = calc_age(record, deceased=False)
        if age is not None:
            if unsure > 0:
                output["age"] = f"{age}-{age+unsure}"
            else:
                output["age"] = str(age)

    # used in graphical tree
    output["name"] = create_short_name(record)
    if is_attr(output, "gender") and output["gender"] in GENDER_MAP:
        output["class"] = GENDER_MAP[output["gender"]]
    output["extra"] = { "url": url_for("person_page", pid=output["id"]) }
    
    if focal:
        output["textClass"] = "emphasis"
    return output

def create_display_name(record: Dict[str, Any], underline: bool = True) -> str:
    """Given a Person record, formats the first, middle, and last
    names, as well as nickname if it exists, into a string formatted
    with blank lines and indication of preferred name.
    """
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
        if underline and record["pref_name"] == "M1":
            name += f" <u>{record['middle_name1']}</u>"
        else:
            name += " " + record['middle_name1']
    if is_attr(record, "middle_name2"):
        if underline and record["pref_name"] == "M2":
            name += f" <u>{record['middle_name2']}</u>"
        else:
            name += " " + record['middle_name2']
    if is_attr(record, "last_name"):
        name += " " + record["last_name"]
    else:
        name += " _____"
    return name

def create_short_name(record: Dict[str, Any]) -> str:
    """Given a Person record, returns a formatted string with just
    preferred name and last name."""
    pref_name = "F"
    if is_attr(record, "pref_name"):
        pref_name = record["pref_name"].strip()

    name = ""
    if pref_name == "N" and is_attr(record, "nickname"):
        name += record["nickname"]
    elif pref_name == "M1" and is_attr(record, "middle_name1"):
        name += record["middle_name1"]
    elif pref_name == "M2" and is_attr(record, "middle_name2"):
        name += record["middle_name2"]
    elif is_attr(record, "first_name"):
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

def create_life_span(record: Dict[str, Any]) -> str:
    """Given a Person record, provides a formatted string with the
    person's life span, e.g., "(1985 - 2003)" or "(2012 - present)"."""
    string = ""
    if is_attr(record, "birth_year"):
        string += f" ({record['birth_year']}"
    else:
        string += " (? "

    if is_attr(record, "death_year"):
        string += f" - {record['death_year']})"
    elif not is_deceased(record):
        string += " - present)"
    else:
        string += " - ?)"
    return string

def is_deceased(record: Dict[str, Any]) -> bool:
    """Given a Person record, determines whether the person is likely
    to be deceased or not, based on the information we have on hand."""
    if (is_attr(record, "death_year")
        or is_attr(record, "death_month")
        or is_attr(record, "death_day")
        or is_attr(record, "death_place")
        or is_attr(record, "buried")):
        return True
    elif (is_attr(record, "birth_year")
        and record["birth_year"].isnumeric()
        and int(record["birth_year"]) >= (CURR_YEAR-100)):
        # assume the best if someone is less than 100 years old :)
        return False
    else:
        return True

def format_date(record: Dict[str, Any], day: str, month: str,
                year: str, all_blanks: bool = False) -> Optional[str]:
    """Given a Person record and the appropriate fields to use for the
    date (e.g., "birth_day", "death_day"), creates a string with the
    formatted date. If all_blanks == True, an unknown date will return
    as "_____ __, ____" rather than returning None."""
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

def calc_age(record: Dict[str, Any], deceased: bool = True) -> Tuple[Optional[int], Optional[int]]:
    """Given a Person record and whether the person should be presumed
    deceased, calculates either current age (for deceased == False) or
    age at death (for deceased == True), provided enough information
    about birth and death is available. In cases where the date(s) are
    somewhat uncertain, the second value of the tuple will provide the
    additional amount of uncertainty. For example, if we know someone's
    birth year but not the month/day, calculating their current age could
    be off by one year. Thus, their age might return as (33, 1) to
    indicate that they could be either 33 or 34.
    """
    birth_vals = { "year": None, "month": 1, "day": 1 }
    unsure_birth = False
    if is_attr(record, "birth_year"):
        try:
            birth_vals["year"] = int(record["birth_year"])
        except ValueError:
            try:
                birth_vals["year"] = int(record["birth_year"][0:4])
            except:
                # if we can't figure out birth year, no point in continuing
                return None, None
    else:
        return None, None

    if is_attr(record, "birth_month"):
        try:
            birth_vals["month"] = MONTHS.index(record["birth_month"]) + 1
        except:
            unsure_birth = True
    
    if is_attr(record, "birth_day"):
        try:
            birth_vals["day"] = int(record["birth_day"])
        except ValueError:
            try:
                birth_vals["day"] = int(record["birth_day"][0:2])
            except:
                unsure_birth = True

    birth_date = datetime(**birth_vals)

    if not deceased:
        today = datetime.today()
        duration = today - birth_date
        age = duration.days // 365
        return (age, int(unsure_birth))

    else:
        death_vals = { "year": None, "month": 1, "day": 1 }
        unsure_death = False
        if is_attr(record, "death_year"):
            try:
                death_vals["year"] = int(record["death_year"])
            except ValueError:
                try:
                    death_vals["year"] = int(record["death_year"][0:4])
                except:
                    # if we can't figure out death year, no point in continuing
                    return None, None
        else:
            return None, None

        if is_attr(record, "death_month"):
            try:
                death_vals["month"] = MONTHS.index(record["death_month"]) + 1
            except:
                unsure_death = True
        
        if is_attr(record, "death_day"):
            try:
                death_vals["day"] = int(record["death_day"])
            except ValueError:
                try:
                    death_vals["day"] = int(record["death_day"][0:2])
                except:
                    unsure_death = True

        death_date = datetime(**death_vals)
        duration = death_date - birth_date
        age = duration.days // 365
        return (age, int(unsure_birth) + int(unsure_death))

def get_latest_export() -> Optional[str]:
    """If the data has been exported from the database in the past,
    returns the date of that export, formatted as `%Y%m%d`."""
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

def export_data(db_conn: DBConnect) -> str:
    """Given a connection to the database, this exports the data to
    CSV files, zips them and saves them to the <APP_ROOT>/static/data/
    directory. Returns the name of the file (without the directory)."""
    date = datetime.now().strftime("%Y%m%d")
    tables = ["people", "marriages", "children"]
    with tempfile.TemporaryDirectory() as tmpdir:
        for table in tables:
            with open(os.path.join(tmpdir, f"{table}_{date}.csv"), "w") as f:
                db_conn.export_data(table, f)

        os.makedirs(os.path.join(os.environ.get("APP_ROOT"), "static/data"), exist_ok=True)
        shutil.make_archive(os.path.join(os.environ.get("APP_ROOT"), "static/data", f"data_{date}"), "zip", tmpdir)
    return f"data_{date}.zip"

def is_safe_url(target: str) -> bool:
    """Ensures that URL redirects used with Flask-Login are safe, i.e.
    are resolving to the same domain name. This helps to prevent
    against phishing attacks."""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc