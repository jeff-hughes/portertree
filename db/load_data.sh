#!/bin/bash

# only populate database if it is currently empty
DATABASE_ROWS=$(cypher-shell --format plain "MATCH (n) RETURN count(n)" | sed -n 2p)

if [ "$DATABASE_ROWS" == 0 ]
then
    cypher-shell "LOAD CSV WITH HEADERS FROM 'file:///people.csv' AS row \
        CREATE (:Person {id: row.id, print_id: row.print_id, in_tree: toBoolean(row.in_tree), first_name: row.first_name, nickname: row.nickname, \
        middle_name1: row.middle_name1, middle_name2: row.middle_name2, last_name: row.last_name, pref_name: row.pref_name, \
        gender: row.gender, birth_month: row.birth_month, birth_day: row.birth_day, birth_year: row.birth_year, \
        birth_place: row.birth_place, death_month: row.death_month, death_day: row.death_day, death_year: row.death_year, \
        death_place: row.death_place, buried: row.buried, additional_notes: row.additional_notes, birth_order: toInteger(row.birth_order)});"
    
    cypher-shell "LOAD CSV WITH HEADERS FROM 'file:///marriages.csv' AS row \
        MATCH (p1:Person {id: row.person1_id}) \
        MATCH (p2:Person {id: row.person2_id}) \
        MERGE (p1)-[m:MARRIED_TO]->(p2) \
        ON CREATE SET m.id = row.id, m.order = row.marriage_order, m.month = row.month, m.day = row.day, m.year = row.year, \
        m.place = row.place, m.divorced = toBoolean(row.divorced), m.divorced_month = row.divorced_month, \
        m.divorced_day = row.divorced_day, m.divorced_year = row.divorced_year;"

    cypher-shell "LOAD CSV WITH HEADERS FROM 'file:///children.csv' AS row \
        MATCH (p:Person {id: row.parent_id}) \
        MATCH (c:Person {id: row.child_id}) \
        MERGE (p)-[r:PARENT_OF]->(c) \
        ON CREATE SET r.id = row.id, r.birth_order = row.birth_order;"
fi
