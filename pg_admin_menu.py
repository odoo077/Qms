#!/usr/bin/env python3
"""
Simple PostgreSQL admin menu to list/create/drop databases.

Requires: pip install psycopg2-binary
"""

import getpass
import sys
import psycopg2
import psycopg2.extras
from psycopg2 import sql

# ---------- Configuration helpers ----------

def prompt_connection():
    print("PostgreSQL connection (press Enter for defaults):")
    host = input("Host [localhost]: ").strip() or "localhost"
    port = input("Port [5432]: ").strip() or "5432"
    user = input("User [postgres]: ").strip() or "mugiwara"
    password = getpass.getpass("Password (hidden): ") or "Aj123456!@"
    # Always connect to the maintenance DB for admin ops
    return dict(host=host, port=port, user=user, password=password, dbname="postgres")

def get_conn(dsn):
    try:
        conn = psycopg2.connect(**dsn)
        # CREATE/DROP DATABASE must run outside transactions → autocommit
        conn.autocommit = True
        return conn
    except Exception as e:
        print(f"[!] Connection failed: {e}")
        sys.exit(1)

# ---------- Core actions ----------


def list_databases(conn):
    """List non-template databases with size, owner, encoding, and locale."""
    q = """
        SELECT
            d.datname AS name,
            pg_catalog.pg_get_userbyid(d.datdba) AS owner,
            pg_catalog.pg_size_pretty(pg_catalog.pg_database_size(d.datname)) AS size,
            pg_catalog.pg_encoding_to_char(d.encoding) AS encoding,
            d.datcollate AS collate,
            d.datctype AS ctype
        FROM pg_catalog.pg_database d
        WHERE d.datistemplate = false
        ORDER BY d.datname;
    """
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(q)
        rows = cur.fetchall()
    if not rows:
        print("No databases found.")
        return
    print("\nDatabases:")
    print("-" * 80)
    for r in rows:
        print(f"{r['name']:<24} owner={r['owner']:<12} size={r['size']:<10} "
              f"encoding={r['encoding']:<6}  collate={r['collate']}  ctype={r['ctype']}")
    print("-" * 80)


def create_database(conn):
    name = input("New database name: ").strip()
    if not name:
        print("[!] Database name cannot be empty.")
        return
    owner = input("Owner (blank = default): ").strip() or None
    template = input("Template [template1]: ").strip() or "template1"
    encoding = input("Encoding [UTF8]: ").strip() or "UTF8"
    lc_collate = input("LC_COLLATE (blank = server default): ").strip() or None
    lc_ctype = input("LC_CTYPE (blank = server default): ").strip() or None

    # Build CREATE DATABASE statement safely
    parts = [sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))]
    opts = []
    if owner:
        opts.append(sql.SQL("OWNER {}").format(sql.Identifier(owner)))
    if encoding:
        opts.append(sql.SQL("ENCODING {}").format(sql.Literal(encoding)))
    if template:
        opts.append(sql.SQL("TEMPLATE {}").format(sql.Identifier(template)))
    if lc_collate:
        opts.append(sql.SQL("LC_COLLATE {}").format(sql.Literal(lc_collate)))
    if lc_ctype:
        opts.append(sql.SQL("LC_CTYPE {}").format(sql.Literal(lc_ctype)))
    if opts:
        parts.append(sql.SQL(" WITH "))
        parts.append(sql.SQL(" ").join(opts))
    stmt = sql.SQL("").join(parts)

    try:
        with conn.cursor() as cur:
            cur.execute(stmt)
        print(f"[✓] Database '{name}' created.")
    except Exception as e:
        print(f"[!] Failed to create database: {e}")

def terminate_backends(conn, dbname):
    """Terminate other connections to a database (needed to drop it)."""
    q = sql.SQL("""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = {dbname}
          AND pid <> pg_backend_pid();
    """).format(dbname=sql.Literal(dbname))
    with conn.cursor() as cur:
        cur.execute(q)

def drop_database(conn):
    name = input("Database to drop: ").strip()
    if not name:
        print("[!] Database name cannot be empty.")
        return
    if name in ("postgres", "template0", "template1"):
        print("[!] Refusing to drop core/maintenance databases.")
        return

    force = input("Force terminate active connections? [y/N]: ").strip().lower() == "y"

    try:
        if force:
            terminate_backends(conn, name)
        with conn.cursor() as cur:
            cur.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
        print(f"[✓] Database '{name}' dropped.")
    except Exception as e:
        msg = str(e)
        if "being accessed by other users" in msg and not force:
            print("[!] Database is busy. Re-run and choose force=Y to terminate sessions.")
        else:
            print(f"[!] Failed to drop database: {e}")

# ---------- Menu loop ----------

def menu(conn):
    actions = {
        "1": ("List databases", list_databases),
        "2": ("Create database", create_database),
        "3": ("Drop database", drop_database),
        "q": ("Quit", None),
    }
    while True:
        print("\n=== PostgreSQL Admin ===")
        for k in ("1", "2", "3", "q"):
            print(f"[{k}] {actions[k][0]}")
        choice = input("Choose: ").strip().lower()
        if choice == "q":
            break
        action = actions.get(choice)
        if not action:
            print("Invalid choice.")
            continue
        try:
            action[1](conn)
        except KeyboardInterrupt:
            print("\n[!] Cancelled.")
        except Exception as e:
            print(f"[!] Error: {e}")


def main():
    dsn = prompt_connection()
    conn = get_conn(dsn)
    try:
        menu(conn)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
