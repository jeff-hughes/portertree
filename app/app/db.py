from enum import Enum
import io
import os
from typing import Any, Dict, List
import psycopg2

PERSON_COLS = ["id", "print_id", "in_tree", "first_name", "nickname", "middle_name1", "middle_name2", "last_name", "pref_name", "gender", "birth_month", "birth_day", "birth_year", "birth_place", "death_month", "death_day", "death_year", "death_place", "buried", "additional_notes"]
MARRIAGE_COLS = ["id", "pid1", "pid2", "marriage_order", "married_month", "married_day", "married_year", "married_place", "common_law", "divorced", "divorced_month", "divorced_day", "divorced_year"]
CHILDREN_COLS = ["id", "pid", "cid", "birth_order", "adoptive"]


class DBEntryType(Enum):
    # people must be added to the database first so the foreign keys
    # exist; so the value for DBEntryType.PERSON must be the lowest
    # number
    PERSON = 1
    MARRIAGE = 2
    PARENT_CHILD_REL = 3


class DBEntry:
    def __init__(self, data: Dict[str, Any], entry_type: DBEntryType, update: bool) -> None:
        self.type = entry_type
        self.update = update
        if entry_type is DBEntryType.PERSON:
            if "id" not in data:
                raise KeyError("No 'id' value for Person: Cannot insert into database.")
            if "in_tree" not in data:
                raise KeyError("No 'in_tree' value for Person: Cannot insert null value in database.")
            self.data = { k: v for k, v in data.items() if k in PERSON_COLS }

        elif entry_type is DBEntryType.MARRIAGE:
            if "pid1" not in data or "pid2" not in data:
                raise KeyError("Must have both 'pid1' and 'pid2' values for Marriage: Cannot insert into database.")
            if update and "id" not in data:
                raise KeyError("No 'id' value for Marriage: Cannot update entry in database.")
            self.data = { k: v for k, v in data.items() if k in MARRIAGE_COLS }

        elif entry_type is DBEntryType.PARENT_CHILD_REL:
            if "pid" not in data:
                raise KeyError("No 'pid' value for Parent-Child Relationship: Cannot insert into database.")
            if "cid" not in data:
                raise KeyError("No 'cid' value for Parent-Child Relationship: Cannot insert into database.")
            if update and "id" not in data:
                raise KeyError("No 'id' value for Parent-Child Relationship: Cannot update entry in database.")
            self.data = { k: v for k, v in data.items() if k in CHILDREN_COLS }

        else:
            raise KeyError("Unknown DB entry type")

    def __lt__(self, other: DBEntryType) -> bool:
        # people must be added to the database first so the foreign keys
        # exist; so this relies on the enum value for DBEntryType.PERSON
        # being the lowest number
        return self.type.value < other.type.value


class DBConnect():
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.environ["POSTGRES_HOST"],
            port=os.environ["POSTGRES_PORT"],
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"])
        self.cursor = self.conn.cursor()

    def __del__(self):
        self.cursor.close()
        self.conn.close()

    def get_person(self, pid: str) -> Dict[str, Any]:
        self.cursor.execute("""
            SELECT
                id, print_id, in_tree, first_name, nickname,
                middle_name1, middle_name2, last_name, pref_name,
                gender, birth_month, birth_day, birth_year, birth_place,
                death_month, death_day, death_year, death_place, buried,
                additional_notes
            FROM people
            WHERE id = %s""", (pid,))
        p = self.cursor.fetchone()
        if p is None:
            return None
        return { k: v for k, v in zip(PERSON_COLS, p) }

    def get_parents(self, pid: str) -> List[Dict[str, Any]]:
        self.cursor.execute("""
            SELECT
                p.id, p.print_id, p.in_tree, p.first_name, p.nickname,
                p.middle_name1, p.middle_name2, p.last_name, p.pref_name,
                p.gender, p.birth_month, p.birth_day, p.birth_year,
                p.birth_place, p.death_month, p.death_day, p.death_year,
                p.death_place, p.buried, p.additional_notes, c.adoptive, c.id as row_id
            FROM children c
            LEFT JOIN people p ON c.pid = p.id
            WHERE c.cid = %s""", (pid,))
        parents = self.cursor.fetchall()

        out = []
        for pr in parents:
            out.append({ k: v for k, v in zip(PERSON_COLS + ["adoptive", "row_id"], pr) })
        return out

    def get_children(self, pid1: str, pid2: str) -> List[Dict[str, Any]]:
        # logic from https://stackoverflow.com/questions/15537892/postgresql-select-must-match-across-multiple-rows
        self.cursor.execute("""
            SELECT
                p.id, p.print_id, p.in_tree, p.first_name, p.nickname,
                p.middle_name1, p.middle_name2, p.last_name, p.pref_name,
                p.gender, p.birth_month, p.birth_day, p.birth_year,
                p.birth_place, p.death_month, p.death_day, p.death_year,
                p.death_place, p.buried, p.additional_notes
            FROM (
                SELECT DISTINCT a.cid, a.birth_order
                FROM children a
                INNER JOIN
                (
                    SELECT
                        cid,
                        SUM((pid = %s)::integer + (pid = %s)::integer) AS match
                    FROM children
                    GROUP BY cid
                ) b ON a.cid = b.cid
                WHERE match >= 2
            ) c
            LEFT JOIN people p on c.cid = p.id
            ORDER BY c.birth_order""", (pid1, pid2))
        children = self.cursor.fetchall()

        out = []
        for c in children:
            out.append({ k: v for k, v in zip(PERSON_COLS + ["adoptive"], c) })
        return out

    def get_marriages(self, pid: str) -> List[Dict[str, Any]]:
        self.cursor.execute(f"""
            (SELECT
                p.id, p.print_id, p.in_tree, p.first_name, p.nickname,
                p.middle_name1, p.middle_name2, p.last_name, p.pref_name,
                p.gender, p.birth_month, p.birth_day, p.birth_year,
                p.birth_place, p.death_month, p.death_day, p.death_year,
                p.death_place, p.buried, p.additional_notes,
                m.id, m.pid1, m.pid2, m.marriage_order, m.married_month,
                m.married_day, m.married_year, m.married_place,
                m.common_law, m.divorced, m.divorced_month,
                m.divorced_day, m.divorced_year
            FROM marriages m
            LEFT JOIN people p ON m.pid2 = p.id
            WHERE m.pid1 = %s)
            UNION
            (SELECT
                p.id, p.print_id, p.in_tree, p.first_name, p.nickname,
                p.middle_name1, p.middle_name2, p.last_name, p.pref_name,
                p.gender, p.birth_month, p.birth_day, p.birth_year,
                p.birth_place, p.death_month, p.death_day, p.death_year,
                p.death_place, p.buried, p.additional_notes,
                m.id, m.pid1, m.pid2, m.marriage_order, m.married_month,
                m.married_day, m.married_year, m.married_place,
                m.common_law, m.divorced, m.divorced_month,
                m.divorced_day, m.divorced_year
            FROM marriages m
            LEFT JOIN people p ON m.pid1 = p.id
            WHERE m.pid2 = %s)
            ORDER BY marriage_order""", (pid, pid))
        spouses = self.cursor.fetchall()

        out = []
        for s in spouses:
            spouse = { k: v for k, v in zip(PERSON_COLS, s[:len(PERSON_COLS)]) }
            marriage = { k: v for k, v in zip(MARRIAGE_COLS, s[len(PERSON_COLS):]) }
            out.append({ "marriage": marriage, "spouse": spouse })
        return out
    
    def search_name(self, search_terms: List[str]) -> List[Dict[str, Any]]:
        # case insensitive matching for each term in the query
        match_stmts = ["(first_name ILIKE %s OR nickname ILIKE %s OR middle_name1 ILIKE %s OR middle_name2 ILIKE %s OR last_name ILIKE %s)"] * len(search_terms)
        match_stmt = " AND ".join(match_stmts)
        # repeat each term 5 times, once for each column to match on
        terms = [f"%{t}%" for t in search_terms for i in range(5)]
        self.cursor.execute(f"""
            SELECT
                id, print_id, in_tree, first_name, nickname,
                middle_name1, middle_name2, last_name, pref_name,
                gender, birth_month, birth_day, birth_year, birth_place,
                death_month, death_day, death_year, death_place, buried,
                additional_notes
            FROM people
            WHERE {match_stmt}""", terms)
        results = self.cursor.fetchall()

        out = []
        for p in results:
            out.append({ k: v for k, v in zip(PERSON_COLS, p) })
        return out

    def search_advanced(self, search_terms: Dict[str, Any]) -> List[Dict[str, Any]]:
        term_contains = ["first_name", "nickname", "last_name", "birth_place", "buried", "death_place", "additional_notes"]
        term_exact = ["birth_day", "birth_month", "birth_year", "death_day", "death_month", "death_year"]

        match_stmts = []
        terms = []
        for col, term in search_terms.items():
            if term != "":
                if col == "middle_name":
                    match_stmts.append("(middle_name1 ILIKE %s OR middle_name2 ILIKE %s)")
                    terms.append(f"%{term}%")
                    terms.append(f"%{term}%")
                elif col in term_contains:
                    match_stmts.append(f"{col} ILIKE %s")
                    terms.append(f"%{term}%")
                elif col in term_exact:
                    match_stmts.append(f"{col} = %s")
                    terms.append(term)
        match_stmt = " AND ".join(match_stmts)

        self.cursor.execute(f"""
            SELECT
                id, print_id, in_tree, first_name, nickname,
                middle_name1, middle_name2, last_name, pref_name,
                gender, birth_month, birth_day, birth_year, birth_place,
                death_month, death_day, death_year, death_place, buried,
                additional_notes
            FROM people
            WHERE {match_stmt}""", terms)
        results = self.cursor.fetchall()

        out = []
        for p in results:
            out.append({ k: v for k, v in zip(PERSON_COLS, p) })
        return out

    def run_transaction(self, data: List[DBEntry]) -> bool:
        query_map = {
            DBEntryType.PERSON: self.add_person,
            DBEntryType.PARENT_CHILD_REL: self.add_child_relationship,
            DBEntryType.MARRIAGE: self.add_marriage
        }

        # sort queries so that People are added before other queries, and
        # foreign keys exist
        queries = sorted(data)

        all_success = True
        for entry in queries:
            result = query_map[entry.type](entry.data, entry.update)
            if not result:
                all_success = False
                break

        if all_success:
            self.commit_transaction()
        else:
            self.rollback_transaction()
        return all_success

    def add_person(self, person: Dict[str, Any], update: bool) -> bool:
        if "id" not in person:
            raise KeyError("No 'id' value for Person: Cannot insert into database.")
        if "in_tree" not in person:
            raise KeyError("No 'in_tree' value for Person: Cannot insert null value in database.")

        if update:
            cols = [k for k in person.keys() if k in PERSON_COLS and k != "id"]
            blanks_list = ", ".join([f"{k} = %s" for k in cols])
            val_list = [person[k] for k in cols] + [person["id"]]
            self.cursor.execute(f"""
                UPDATE people
                SET {blanks_list}
                WHERE id = %s""", val_list)
            msg = self.cursor.statusmessage.split(" ")
            status = msg[0] == "UPDATE" and msg[1] == "1"
        else:
            cols = [k for k in person.keys() if k in PERSON_COLS]
            col_list = ", ".join(cols)
            blanks_list = ", ".join(["%s"] * len(cols))
            val_list = [person[k] for k in cols]
            self.cursor.execute(f"""
                INSERT INTO people ({col_list})
                VALUES
                ({blanks_list})""", val_list)
            msg = self.cursor.statusmessage.split(" ")
            status = msg[0] == "INSERT" and msg[2] == "1"
        return status

    def add_child_relationship(self, relationship: Dict[str, Any], update: bool) -> bool:
        if "pid" not in relationship:
            raise KeyError("No 'pid' value for Child Relationship: Cannot insert into database.")
        if "cid" not in relationship:
            raise KeyError("No 'cid' value for Child Relationship: Cannot insert into database.")
        if update and "id" not in relationship:
            raise KeyError("No 'id' value for Child Relationship: Cannot update entry in database.")

        if update:
            cols = [k for k in relationship.keys() if k in CHILDREN_COLS and k != "id"]
            blanks_list = ", ".join([f"{k} = %s" for k in cols])
            val_list = [relationship[k] for k in cols] + [relationship["id"]]
            self.cursor.execute(f"""
                UPDATE children
                SET {blanks_list}
                WHERE id = %s""", val_list)
            msg = self.cursor.statusmessage.split(" ")
            status = msg[0] == "UPDATE" and msg[1] == "1"
        else:
            cols = [k for k in relationship.keys() if k in CHILDREN_COLS]
            col_list = ", ".join(cols)
            blanks_list = ", ".join(["%s"] * len(cols))
            val_list = [relationship[k] for k in cols]
            self.cursor.execute(f"""
                INSERT INTO children ({col_list})
                VALUES
                ({blanks_list})""", val_list)
            msg = self.cursor.statusmessage.split(" ")
            status = msg[0] == "INSERT" and msg[2] == "1"
        return status

    def add_marriage(self, marriage: Dict[str, Any], update: bool) -> None:
        if "pid1" not in marriage or "pid2" not in marriage:
            raise KeyError("Must have both 'pid1' and 'pid2' values for Marriage: Cannot insert into database.")
        if update and "id" not in marriage:
            raise KeyError("No 'id' value for Marriage: Cannot update entry in database.")

        if update:
            cols = [k for k in marriage.keys() if k in MARRIAGE_COLS and k != "id"]
            blanks_list = ", ".join([f"{k} = %s" for k in cols])
            val_list = [marriage[k] for k in cols] + [marriage["id"]]
            self.cursor.execute(f"""
                UPDATE marriages
                SET {blanks_list}
                WHERE id = %s""", val_list)
            msg = self.cursor.statusmessage.split(" ")
            status = msg[0] == "UPDATE" and msg[1] == "1"
        else:
            cols = [k for k in marriage.keys() if k in MARRIAGE_COLS]
            col_list = ", ".join(cols)
            blanks_list = ", ".join(["%s"] * len(cols))
            val_list = [marriage[k] for k in cols]
            self.cursor.execute(f"""
                INSERT INTO marriages ({col_list})
                VALUES
                ({blanks_list})""", val_list)
            msg = self.cursor.statusmessage.split(" ")
            status = msg[0] == "INSERT" and msg[2] == "1"
        return status

    def export_data(self, table: str, file_handle: io.IOBase) -> None:
        if table == "people":
            self.cursor.copy_expert("""
                COPY people (id, print_id, in_tree, first_name, nickname,
                    middle_name1, middle_name2, last_name, pref_name,
                    gender, birth_month, birth_day, birth_year,
                    birth_place, death_month, death_day, death_year,
                    death_place, buried, additional_notes)
                TO STDOUT DELIMITER ',' CSV HEADER;""", file_handle)
        elif table == "marriages":
            self.cursor.copy_expert("""
                COPY marriages (pid1, pid2, marriage_order,
                    married_month, married_day, married_year,
                    married_place, common_law, divorced, divorced_month,
                    divorced_day, divorced_year)
                TO STDOUT DELIMITER ',' CSV HEADER;""", file_handle)
        elif table == "children":
            self.cursor.copy_expert("""
                COPY children (pid, cid, birth_order, adoptive)
                TO STDOUT DELIMITER ',' CSV HEADER;""", file_handle)
        else:
            raise ValueError

    def commit_transaction(self) -> None:
        self.conn.commit()

    def rollback_transaction(self) -> None:
        self.conn.rollback()