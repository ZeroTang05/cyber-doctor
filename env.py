import os
from dotenv import load_dotenv

load_dotenv(".env", override=False)


def get_app_root():
    return os.getcwd()


def get_env_value(key):
    return os.environ.get(key)
