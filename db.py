import mysql.connector
from mysql.connector import Error

def get_db():
    try:
        # We add 'reconnect=True' to handle the "Broken Connection" issue
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="IronmanHulk@7621", # <-- CHANGE THIS to your actual MySQL password
            database="waste3", # <-- CHANGE THIS to your actual database name
            raise_on_warnings=True,
            autocommit=True
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return None