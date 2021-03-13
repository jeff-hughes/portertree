CREATE TABLE people (
    id TEXT PRIMARY KEY,
    print_id TEXT,
    in_tree BOOLEAN NOT NULL,
    first_name TEXT,
    nickname TEXT,
    middle_name1 TEXT,
    middle_name2 TEXT,
    last_name TEXT,
    pref_name CHAR(2),
    gender CHAR(1),
    birth_month TEXT,
    birth_day INTEGER,
    birth_year TEXT,
    birth_place TEXT,
    death_month TEXT,
    death_day INTEGER,
    death_year TEXT,
    death_place TEXT,
    buried TEXT,
    additional_notes TEXT
);

CREATE TABLE marriages (
    id SERIAL PRIMARY KEY,
    pid1 TEXT NOT NULL,
    pid2 TEXT NOT NULL,
    marriage_order INTEGER,
    married_month TEXT,
    married_day INTEGER,
    married_year TEXT,
    married_place TEXT,
    divorced BOOLEAN,
    divorced_month TEXT,
    divorced_day INTEGER,
    divorced_year TEXT,
    FOREIGN KEY (pid1) REFERENCES people (id),
    FOREIGN KEY (pid2) REFERENCES people (id)
);

CREATE TABLE children (
    id SERIAL PRIMARY KEY,
    pid TEXT NOT NULL,
    cid TEXT NOT NULL,
    birth_order INTEGER,
    FOREIGN KEY (pid) REFERENCES people (id),
    FOREIGN KEY (cid) REFERENCES people (id)
);

COPY people (id, print_id, in_tree, first_name, nickname, middle_name1, middle_name2, last_name, pref_name, gender, birth_month, birth_day, birth_year, birth_place, death_month, death_day, death_year, death_place, buried, additional_notes) FROM '/data_imports/people.csv' CSV HEADER;

COPY marriages (pid1, pid2, marriage_order, married_month, married_day, married_year, married_place, divorced, divorced_month, divorced_day, divorced_year) FROM '/data_imports/marriages.csv' CSV HEADER;

COPY children (pid, cid, birth_order) FROM '/data_imports/children.csv' CSV HEADER;