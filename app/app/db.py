import os
from typing import Any, Dict, List
import psycopg2

PERSON_COLS = ("id", "print_id", "in_tree", "first_name", "nickname", "middle_name1", "middle_name2", "last_name", "pref_name", "gender", "birth_month", "birth_day", "birth_year", "birth_place", "death_month", "death_day", "death_year", "death_place", "buried", "additional_notes")
MARRIAGE_COLS = ("pid1", "pid2", "marriage_order", "married_month", "married_day", "married_year", "married_place", "divorced", "divorced_month", "divorced_day", "divorced_year")

class DBConnect():
    def __init__(self):
        self.conn = psycopg2.connect(f"host='{os.environ['POSTGRES_HOST']}' port='{os.environ['POSTGRES_PORT']}' dbname='{os.environ['POSTGRES_DB']}' user='{os.environ['POSTGRES_USER']}' password='{os.environ['POSTGRES_PASSWORD']}'")
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
        return { k: v for k, v in zip(PERSON_COLS, p) }

    def get_parents(self, pid: str) -> List[Dict[str, Any]]:
        self.cursor.execute("""
            SELECT
                p.id, p.print_id, p.in_tree, p.first_name, p.nickname,
                p.middle_name1, p.middle_name2, p.last_name, p.pref_name,
                p.gender, p.birth_month, p.birth_day, p.birth_year,
                p.birth_place, p.death_month, p.death_day, p.death_year,
                p.death_place, p.buried, p.additional_notes
            FROM children c
            LEFT JOIN people p ON c.pid = p.id
            WHERE c.cid = %s""", (pid,))
        parents = self.cursor.fetchall()

        out = []
        for pr in parents:
            out.append({ k: v for k, v in zip(PERSON_COLS, pr) })
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
            out.append({ k: v for k, v in zip(PERSON_COLS, c) })
        return out

    def get_marriages(self, pid: str, in_tree: bool) -> List[Dict[str, Any]]:
        # the person "in tree" (i.e. related by blood) will always be
        # the first one listed, pid1
        if in_tree:
            matchid = "pid1"
            joinid = "pid2"
        else:
            matchid = "pid2"
            joinid = "pid1"
        self.cursor.execute(f"""
            SELECT
                p.id, p.print_id, p.in_tree, p.first_name, p.nickname,
                p.middle_name1, p.middle_name2, p.last_name, p.pref_name,
                p.gender, p.birth_month, p.birth_day, p.birth_year,
                p.birth_place, p.death_month, p.death_day, p.death_year,
                p.death_place, p.buried, p.additional_notes,
                m.pid1, m.pid2, m.marriage_order, m.married_month,
                m.married_day, m.married_year, m.married_place,
                m.divorced, m.divorced_month, m.divorced_day,
                m.divorced_year
            FROM marriages m
            LEFT JOIN people p ON m.{joinid} = p.id
            WHERE m.{matchid} = %s
            ORDER BY m.marriage_order""", (pid,))
        spouses = self.cursor.fetchall()

        out = []
        for s in spouses:
            spouse = { k: v for k, v in zip(PERSON_COLS, s[:20]) }
            marriage = { k: v for k, v in zip(MARRIAGE_COLS, s[20:]) }
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