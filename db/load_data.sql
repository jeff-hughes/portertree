CREATE TABLE people (
    id VARCHAR(50) PRIMARY KEY,
    print_id VARCHAR(50),
    in_tree BOOLEAN NOT NULL,
    first_name VARCHAR(100),
    nickname VARCHAR(100),
    middle_name1 VARCHAR(100),
    middle_name2 VARCHAR(100),
    last_name VARCHAR(100),
    pref_name CHAR(2),
    gender CHAR(1),
    birth_month CHAR(9),
    birth_day INTEGER,
    birth_year VARCHAR(50),
    birth_place VARCHAR(100),
    death_month CHAR(9),
    death_day INTEGER,
    death_year VARCHAR(50),
    death_place VARCHAR(100),
    buried VARCHAR(100),
    additional_notes TEXT,
    birth_order INTEGER
);

CREATE TABLE marriages (
    id serial PRIMARY KEY,
    mid VARCHAR(50) UNIQUE NOT NULL,
    pid1 VARCHAR(50) NOT NULL,
    pid2 VARCHAR(50) NOT NULL,
    marriage_order INTEGER,
    month CHAR(9),
    day INTEGER,
    year VARCHAR(50),
    place VARCHAR(100),
    divorced BOOLEAN,
    divorced_month CHAR(9),
    divorced_day INTEGER,
    divorced_year VARCHAR(50),
    FOREIGN KEY (pid1) REFERENCES people (id),
    FOREIGN KEY (pid2) REFERENCES people (id)
);

CREATE TABLE children (
    id serial PRIMARY KEY,
    rel_id VARCHAR(50) UNIQUE NOT NULL,
    pid VARCHAR(50) NOT NULL,
    cid VARCHAR(50) NOT NULL,
    birth_order INTEGER,
    FOREIGN KEY (pid) REFERENCES people (id),
    FOREIGN KEY (cid) REFERENCES people (id)
);

COPY people (id, print_id, in_tree, first_name, nickname, middle_name1, middle_name2, last_name, pref_name, gender, birth_month, birth_day, birth_year, birth_place, death_month, death_day, death_year, death_place, buried, additional_notes, birth_order) FROM '/csv_data/people.csv' CSV HEADER;

COPY marriages (mid, pid1, pid2, marriage_order, month, day, year, place, divorced, divorced_month, divorced_day, divorced_year) FROM '/csv_data/marriages.csv' CSV HEADER;

COPY children (rel_id, birth_order, pid, cid) FROM '/csv_data/children.csv' CSV HEADER;