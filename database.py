import psycopg2
from psycopg2 import Error
import pandas as pd
from typing import Self


class Database:
    def __init__(
        self,
        db_name: str,
        db_user: str,
        db_pass: str,
        table_name: str,
        db_host: str = "127.0.0.1",
        db_port: str = "5432",
    ):
        self._db_name = db_name
        self._db_user = db_user
        self._db_pass = db_pass
        self._db_host = db_host
        self._db_port = db_port
        self._table_name = table_name
        self._conn = None
        self._cursor = None
        self._db_size = 0

    def __len__(self):
        return self._db_size

    def _safe_query(
        self,
        query: str,
        params: tuple | list | None = None,
        bulk_data: list | None = None,
    ) -> bool:
        """
        Safe DB query, verifies if database is connected before
        """
        if self._cursor is None:
            print("Error: Database connection not established.")
            return False

        try:
            if bulk_data is not None:
                self._cursor.executemany(query, bulk_data)

            elif params is not None:
                self._cursor.execute(query, params)

            else:
                self._cursor.execute(query)

            return True
        except Exception as e:
            print(f"Query execution error: {e}")
            return False

    def check_size(self) -> None:
        # Check for new data added
        old_size = self._db_size
        self._safe_query(f"SELECT COUNT(*) FROM {self._table_name};")
        if self._cursor:
            count_tup = self._cursor.fetchone()
            if count_tup:
                new_size = count_tup[0]
                if new_size > old_size:
                    print(f"{new_size - old_size} new rows added")
                    self._db_size = new_size
                else:
                    print("No new data was added")

    def connect(self):
        try:
            self._conn = psycopg2.connect(
                user=self._db_user,
                password=self._db_pass,
                host=self._db_host,
                port=self._db_port,
                database=self._db_name,
            )

            self._cursor = self._conn.cursor()

            # Set the db size attribute after connection
            res = self._safe_query(f"SELECT COUNT(*) FROM {self._table_name};")

            if res is not None and self._cursor is not None:
                count_tup = self._cursor.fetchone()
                if count_tup is not None:
                    self._db_size = count_tup[0]

            print("Successfully connected to database.")

        except (Exception, Error) as error:
            print(f"Error while connecting to PostgreSQL: {error}")

    def insert(self, data_list: list[dict]) -> None:
        if not data_list:
            print("Data list is empty, nothing to insert.")
            return

        # Assumes all dicts in list have the same keys
        columns = data_list[0].keys()
        columns_str = ", ".join(columns)
        values_placeholder = ", ".join(["%s"] * len(columns))

        sql_insert = f"""
        INSERT INTO {self._table_name} ({columns_str})
        VALUES ({values_placeholder})
        """

        # Convert list of dicts to list of tuples
        insert_data = [[item[col] for col in columns] for item in data_list]

        try:
            res = self._safe_query(sql_insert, bulk_data=insert_data)

            if res and self._conn is not None:
                self._conn.commit()
                print("Data inserted successfully.")

        except (Exception, Error) as error:
            print(f"Error while inserting data: {error}")

            if self._conn is not None:
                self._conn.rollback()

    def read(self, batch_size=None) -> pd.DataFrame | None:
        res = self._safe_query(f"SELECT * FROM {self._table_name}")

        if not res or self._cursor is None:
            return None

        try:
            if self._cursor.description is None:
                raise Error("Did not find any column names in the accessed table.")

            colnames = [desc[0].upper() for desc in self._cursor.description]

            if batch_size is not None:
                rows = self._cursor.fetchmany(batch_size)
            else:
                rows = self._cursor.fetchall()

            return pd.DataFrame(rows, columns=colnames)

        except (Exception, Error) as error:
            print(f"Error while reading data: {error}")
            return None

    def close(self):
        if self._conn is None or self._cursor is None:
            print("Did not find a database connection to close.")
            return

        if self._cursor:
            self._cursor.close()
        if self._conn:
            self._conn.close()
            print("PostgreSQL connection is closed.")


# Database connection factory
def create_db_connection(
    db_name: str,
    db_user: str,
    db_pass: str,
    table_name: str,
    db_host: str = "127.0.0.1",
    db_port: str = "5432"
):
    return Database(
        db_name,
        db_user,
        db_pass,
        table_name,
        db_host,
        db_port
    )
