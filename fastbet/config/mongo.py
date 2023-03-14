# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/Config/001_mongo.ipynb.

# %% auto 0
__all__ = ['db_connect', 'mongo_init']

# %% ../../nbs/Config/001_mongo.ipynb 3
import mongoengine
from typing import Optional, Dict
from .localconfig import CONFIG, DB_HOSTS

# %% ../../nbs/Config/001_mongo.ipynb 4
def db_connect(
    db_hosts: Dict,  # All DB hosts.
    config: Dict,  # Database config.
    db_host: str,  # Host name as defined in `DB_HOSTS`.
    db_name: str,  # Name of the database to connect to.
    db_alias: Optional[
        str
    ] = None,  # Alias of the database we are connecting to. If not provided, we will use `db_name`.
):
    "Connect to the apprpriate mongo database."
    # check that the host name provided is valid
    if db_host not in db_hosts:
        raise ValueError(
            "db-host provided {db_host} should be one of {hosts}:".format(
                db_host=db_host, hosts=db_hosts
            )
        )

    # decide on the alias to apply
    db_alias = db_name if not db_name else db_alias

    # read config for the appropriate database
    db_config = config["databases"][db_host]

    # form the mongo-url i.e check if we need the port
    db_url = (
        db_config["url"]
        if not db_config["port"]
        else db_config["url"] + ":" + db_config["port"]
    )

    db_uri = "{base_url}{user}:{password}@{url}/{db}".format(
        base_url=db_config["mongo_base"],
        user=db_config["user"],
        password=db_config["password"],
        url=db_url,
        db=db_name,
    )
    # add optional argument
    optional_uri = []
    if db_config["majority"]:
        optional_uri.append("w={majority}".format(majority="majority"))
    if db_config["retry_writes"]:
        optional_uri.append(
            "retryWrites={majority}".format(
                majority=str(db_config["retry_writes"]).lower()
            )
        )
    if db_config["authSource"]:
        optional_uri.append(
            "authSource={auth_db}".format(auth_db=db_config["authSource"])
        )

    if optional_uri:
        db_uri += "?" + "&".join(optional_uri)

    mongoengine.register_connection(host=db_uri, alias=db_alias, name=db_name)

# %% ../../nbs/Config/001_mongo.ipynb 8
def mongo_init(
    db_host: str,  # Host name as defined in `DB_HOSTS`.
    db_hosts: Dict = DB_HOSTS,  # All DB hosts.
    config: Dict = CONFIG,  # Database config.
    db_alias: str = "features", # db-alias
):
    "Register all the required mongo connections."
    # check that the host name provided is valid
    if db_host not in db_hosts:
        raise ValueError(
            "db-host provided {db_host} should be one of {hosts}:".format(
                db_host=db_host, hosts=db_hosts
            )
        )

    ## features db
    db_connect(
        db_hosts=db_hosts,
        config=config,
        db_host=db_host,
        db_name=config["connections"]["features"]["db"],
        db_alias=db_alias,
    )
