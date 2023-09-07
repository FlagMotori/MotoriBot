# config_vars.py
import os
from pymongo import MongoClient


def parse_variable(variable, default=None, valid=None):
    value = os.getenv(variable, None)
    if default and valid and variable not in valid:
        return default
    elif isinstance(default, bool):
        return True if value.lower() in ["true", "1", "t", "y", "yes"] else False
    elif isinstance(default, int):
        return int(value) if value and value.isdigit() else default
    else:
        return value if value and value != "" else default


def parse_int_list(variable):
    return [
        int(item)
        for item in parse_variable(variable, "").replace(" ", "").split(",")
        if item.isdigit()
    ]

discord_token = parse_variable("DISCORD_TOKEN")
mongodb_connection = parse_variable("MONGODB_URI", "mongodb://mongo:27017")

client = MongoClient(mongodb_connection)

ctfdb = client['ctftime'] # Create ctftime database
ctfs = ctfdb['ctfs'] # Create ctfs collection

teamdb = client['ctfteams'] # Create ctf teams database

serverdb = client['serverinfo'] # configuration db
