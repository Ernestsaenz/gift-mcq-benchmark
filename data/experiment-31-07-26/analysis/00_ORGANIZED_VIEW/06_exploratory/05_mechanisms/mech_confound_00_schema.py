import sqlite3, json, sys
DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"
c = sqlite3.connect(DB, uri=True)
for name, sql in c.execute("select name,sql from sqlite_master where type='table' order by name"):
    print("===", name)
    print(sql)
    try:
        n = c.execute(f"select count(*) from {name}").fetchone()[0]
        print("rows:", n)
    except Exception as e:
        print("count err", e)
    print()
