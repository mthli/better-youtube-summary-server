import sqlite3

from os import path
from typing import Any

# https://stackoverflow.com/a/9613153
#
# What if I don't close the database connection in Python SQLite?
#
# In answer to the specific question of what happens if you do not close a SQLite database,
# the answer is quite simple and applies to using SQLite in any programming language.
# When the connection is closed explicitly by code or implicitly by program exit then any outstanding transaction is rolled back.
# (The rollback is actually done by the next program to open the database.)
# If there is no outstanding transaction open then nothing happens.
#
# This means you do not need to worry too much about always closing the database before process exit,
# and that you should pay attention to transactions making sure to start them and commit at appropriate points.
db_connection = sqlite3.connect(path.join(path.dirname(__file__), 'bys.db'))


def commit(sql: str):
    cursor = db_connection.cursor()
    try:
        cursor.execute(sql)
        db_connection.commit()
    finally:
        cursor.close()


def fetchall(sql: str) -> list[Any]:
    cursor = db_connection.cursor()
    try:
        cursor.execute(sql)
        res = cursor.fetchall()
    finally:
        cursor.close()
    return res


# https://cs.android.com/android/platform/superproject/+/refs/heads/master:frameworks/base/core/java/android/database/DatabaseUtils.java;drc=7346c436e5a11ce08f6a80dcfeb8ef941ca30176;l=512?q=sqlEscapeString
def sqlescape(string: str) -> str:
    res = ''
    for c in string:
        if c == '\'':
            res += '\''
        res += c
    return res


commit('PRAGMA journal_mode=WAL')
