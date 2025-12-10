import mysql.connector

def get_connection():
    connection = mysql.connector.connect(
        host="aribert.helioho.st",
        port=3306,
        user="aribert_sistema",
        password="ale-61054342",
        database="aribert_hattucci",
        auth_plugin="mysql_native_password"
    )
    return connection
