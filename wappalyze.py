import json
import re
import requests
from typing import List, Dict, Optional
from urllib.parse import urlparse

WappazlyerRoot = "https://raw.githubusercontent.com/enthec/webappanalyzer/main/src"

# StringArray type is a wrapper for list of strings for use in unmarshalling the technologies.json
class StringArray(list):
    pass

# App type encapsulates all the data about an App from technologies.json
class App:
    def __init__(self):
        self.Cats = StringArray()
        self.CatNames = []
        self.Cookies = {}
        self.Headers = {}
        self.Meta = {}
        self.HTML = StringArray()
        self.Script = StringArray()
        self.URL = StringArray()
        self.Website = ""
        self.Implies = StringArray()

        self.HTMLRegex = []
        self.ScriptRegex = []
        self.URLRegex = []
        self.HeaderRegex = []
        self.MetaRegex = []
        self.CookieRegex = []

# Category names defined by wappalyzer
class Category:
    def __init__(self):
        self.Name = ""

# AppRegexp type encapsulates regular expression data for an App
class AppRegexp:
    def __init__(self, name: str, regex: Optional[re.Pattern] = None, version: str = ""):
        self.Name = name
        self.Regexp = regex
        self.Version = version

# AppsDefinition type encapsulates the json encoding of the whole technologies.json file
class AppsDefinition:
    def __init__(self):
        self.Apps = {}  # type: Dict[str, App]
        self.Cats = {}  # type: Dict[str, Category]

# Download technologies.json file
def download_file(to: str) -> None:
    # Download categories
    categories, _ = download_categories()

    # Download technologies from _, a-z
    app_defs, _ = download_technologies()

    # Create technologies file
    technologies_file = AppsDefinition()
    technologies_file.Apps = app_defs
    technologies_file.Cats = categories

    # Write to file
    with open(to, "w") as f:
        json.dump(technologies_file.__dict__, f, indent=4)

# Download categories from Wappalyzer repository
def download_categories() -> Tuple[Dict[str, Category], Optional[Exception]]:
    try:
        url = f"{WappazlyerRoot}/categories.json"
        resp = requests.get(url)
        resp.raise_for_status()
        return resp.json(), None
    except Exception as e:
        return {}, e

# Download technologies from Wappalyzer repository
def download_technologies() -> Tuple[Dict[str, App], Optional[Exception]]:
    apps = {}
    files = [chr(i) for i in range(ord('a'), ord('z') + 1)]
    
    for f in files:
        try:
            url = f"{WappazlyerRoot}/technologies/{f}.json"
            resp = requests.get(url)
            resp.raise_for_status()
            m = resp.json()
            for key, value in m.items():
                apps[key] = value
        except Exception as e:
            return {}, e

    return apps, None

# Load apps from JSON data
def load_apps(data: Dict, app_defs: AppsDefinition) -> None:
    app_defs.Apps = {}
    app_defs.Cats = {}

    for key, value in data["technologies"].items():
        app = App()

        app.Cats = StringArray(value["cats"])
        app.CatNames = value.get("category_names", [])
        app.Cookies = value.get("cookies", {})
        app.Headers = value.get("headers", {})
        app.Meta = value.get("meta", {})
        app.HTML = StringArray(value.get("html", []))
        app.Script = StringArray(value.get("scripts", []))
        app.URL = StringArray(value.get("url", []))
        app.Website = value.get("website", "")
        app.Implies = StringArray(value.get("implies", []))

        app.HTMLRegex = compile_regexes(value.get("html", []))
        app.ScriptRegex = compile_regexes(value.get("scripts", []))
        app.URLRegex = compile_regexes(value.get("url", []))
        app.HeaderRegex = compile_named_regexes(value.get("headers", {}))
        app.CookieRegex = compile_named_regexes(value.get("cookies", {}))

        meta_regex = {}
        for k, v in value.get("meta", {}).items():
            meta_regex[k] = "|".join(v)
        app.MetaRegex = compile_named_regexes(meta_regex)

        app.CatNames = [app_defs.Cats[str(cid)].Name for cid in app.Cats if str(cid) in app_defs.Cats]

        app_defs.Apps[key] = app

# Compile regular expressions from a list of strings
def compile_regexes(s: List[str]) -> List[AppRegexp]:
    regex_list = []

    for regex_string in s:
        if not regex_string:
            continue
        # Split version detection
        splitted = regex_string.split("\\;")

        regex = re.compile("(?i)" + splitted[0])
        rv = AppRegexp(regex=regex)

        if len(splitted) > 1 and splitted[0].startswith("version"):
            rv.Version = splitted[1][8:]

        regex_list.append(rv)

    return regex_list

# Compile named regular expressions from a dictionary
def compile_named_regexes(from_dict: Dict[str, str]) -> List[AppRegexp]:
    regex_list = []

    for key, value in from_dict.items():
        if not value:
            value = ".*"

        # Filter out webapplyzer attributes from regular expression
        splitted = value.split("\\;")

        r = re.compile("(?i)" + splitted[0])

        rv = AppRegexp(name=key, regex=r)

        if len(splitted) > 1 and splitted[1].startswith("version:"):
            rv.Version = splitted[1][8:]

        regex_list.append(rv)

    return regex_list
