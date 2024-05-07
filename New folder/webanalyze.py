import re
import requests
import time
from typing import List, Dict, Tuple, Optional
from bs4 import BeautifulSoup

VERSION = "0.3.9"
timeout = 8

# Result type encapsulates the result information from a given host
class Result:
    def __init__(self, host: str, matches: List[dict], duration: float, error: Optional[Exception]):
        self.host = host
        self.matches = matches
        self.duration = duration
        self.error = error

# Match type encapsulates the App information from a match on a document
class Match:
    def __init__(self, app: dict, app_name: str, matches: List[List[str]], version: str):
        self.app = app
        self.app_name = app_name
        self.matches = matches
        self.version = version

    def update_version(self, version: str):
        if version:
            self.version = version

# WebAnalyzer types holds an analyzation job
class WebAnalyzer:
    def __init__(self, apps_definition: dict, client: Optional[requests.Session] = None):
        self.app_defs = apps_definition
        self.client = client or requests.Session()

    def process(self, job: dict) -> Tuple[Result, List[str]]:
        url = job['url']
        force_not_download = job.get('force_not_download', False)
        follow_redirect = job.get('follow_redirect', False)
        search_subdomain = job.get('search_subdomain', False)
        crawl = job.get('crawl', 0)

        if not url.startswith("http://") and not url.startswith("https://"):
            url = "http://" + url

        t0 = time.time()

        try:
            response, body, headers, cookies = self.fetch_host(url)
            links = []
            if follow_redirect:
                links = self.parse_links(response, url, search_subdomain)
            apps, _ = self.analyze(response, body, headers, cookies)
            t1 = time.time()
            duration = t1 - t0
            return Result(url, apps, duration, None), links
        except Exception as e:
            t1 = time.time()
            duration = t1 - t0
            return Result(url, [], duration, e), []

    def category_by_id(self, cid: str) -> str:
        return self.app_defs['Cats'].get(cid, {}).get('Name', '')

    def fetch_host(self, url: str) -> Tuple[requests.Response, bytes, dict, List[requests.cookies.Cookie]]:
        resp = self.client.get(url, timeout=timeout, allow_redirects=True, verify=False)
        body = resp.content
        headers = resp.headers
        cookies = resp.cookies
        return resp, body, headers, cookies

    def parse_links(self, response: requests.Response, base_url: str, search_subdomain: bool) -> List[str]:
        links = []
        soup = BeautifulSoup(response.content, 'html.parser')
        for a in soup.find_all('a', href=True):
            val = a['href']
            resolved_link = self.resolve_link(base_url, val, search_subdomain)
            if resolved_link:
                links.append(resolved_link)
        return list(set(links))

    def resolve_link(self, base_url: str, val: str, search_subdomain: bool) -> Optional[str]:
        parsed_base = urlparse(base_url)
        parsed_link = urlparse(val)
        
        if not parsed_link.scheme:
            parsed_link = parsed_link._replace(scheme='http')
            
        url_resolved = urljoin(parsed_base.geturl(), parsed_link.geturl())

        if not search_subdomain and not is_subdomain(parsed_base, parsed_link):
            return None

        if search_subdomain and not is_subdomain(parsed_base, parsed_link):
            return None

        if url_resolved.path == "":
            url_resolved = url_resolved._replace(path="/")

        if parsed_base.netloc == parsed_link.netloc and parsed_base.path == parsed_link.path:
            return None

        if url_resolved.scheme not in ["http", "https"]:
            return None

        return url_resolved.geturl()

    def analyze(self, response: requests.Response, body: bytes, headers: dict, cookies: List[requests.cookies.Cookie]) -> Tuple[List[Match], List[str]]:
        apps = []
        scripts = re.findall(r'<script[^>]*src=["\'](.*?)["\']', body.decode("utf-8"), re.IGNORECASE)

        for app_name, app in self.app_defs['Apps'].items():
            findings = Match(app, app_name, [], '')
            findings.matches.extend(self.find_matches(body.decode("utf-8"), app['HTMLRegex']))
            header_findings, version = app['FindInHeaders'](headers)
            findings.matches.extend(header_findings)
            findings.update_version(version)
            findings.matches.extend(self.find_matches(response.url, app['URLRegex']))

            for script in scripts:
                script_matches, version = self.find_matches(script, app['ScriptRegex'])
                findings.matches.extend(script_matches)
                findings.update_version(version)

            for meta in app['MetaRegex']:
                meta_matches, version = self.find_matches(headers.get(meta['Name'], ''), [meta])
                findings.matches.extend(meta_matches)
                findings.update_version(version)

            for cookie in app['CookieRegex']:
                if cookie['Name'] in cookies:
                    if cookie['Regexp']:
                        cookie_matches, version = self.find_matches(cookies[cookie['Name']], [cookie])
                        findings.matches.extend(cookie_matches)
                        findings.update_version(version)
                    else:
                        findings.matches.append([cookie['Name']])

            if findings.matches:
                apps.append(findings)

                for implies in app['Implies']:
                    if implies in self.app_defs['Apps']:
                        imply_app = self.app_defs['Apps'][implies]
                        f2 = Match(imply_app, implies, [], '')
                        apps.append(f2)

        return apps, []

    def find_matches(self, content: str, regexes: List[dict]) -> Tuple[List[List[str]], str]:
        matches = []
        version = ''

        for regex in regexes:
            for match in regex['Regexp'].findall(content):
                matches.append(match)

                if regex['Version']:
                    version = self.find_version(matches, regex['Version'])

        return matches, version

    def find_version(self, matches: List[List[str]], version: str) -> str:
        v = ''
        for match_pair in matches:
            for i in range(1, 4):
                bt = "\\" + str(i)
                if bt in version and len(match_pair) >= i:
                    v = version.replace(bt, match_pair[i-1], 1)
            if v:
                return v
        return ''

def is_subdomain(base_url, url):
    return domainutil.Domain(base_url.netloc) == domainutil.Domain(url.netloc)


# Example usage
if __name__ == "__main__":
    url = "https://example.com"
    apps_definition = {"Cats": {}, "Apps": {}}
    client = requests.Session()
    web_analyzer = WebAnalyzer(apps_definition, client)
    job = {"url": url}
    result, links = web_analyzer.process(job)
    print(result.matches)
    print(links)
