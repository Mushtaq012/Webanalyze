import requests

class Job:
    def __init__(self, url, body=None, headers=None, crawl=0, search_subdomain=False, force_not_download=False, follow_redirect=False):
        self.URL = url
        self.Body = body
        self.Headers = headers or {}
        self.Cookies = []
        self.Crawl = crawl
        self.SearchSubdomain = search_subdomain
        self.ForceNotDownload = force_not_download
        self.FollowRedirect = follow_redirect

    @classmethod
    def new_offline_job(cls, url, body, headers):
        return cls(url, body, headers, force_not_download=True)

    @classmethod
    def new_online_job(cls, url, body=None, headers=None, crawl_count=0, search_subdomain=False, redirect=False):
        return cls(url, body, headers, crawl_count, search_subdomain, redirect)


# Example Usage:

# Constructing an offline job
offline_job = Job.new_offline_job(
    url="https://example.com",
    body="<html><body>Hello, World!</body></html>",
    headers={"Content-Type": "text/html"}
)

# Constructing an online job
online_job = Job.new_online_job(
    url="https://example.com",
    body="<html><body>Hello, World!</body></html>",
    headers={"Content-Type": "text/html"},
    crawl_count=10,
    search_subdomain=True,
    redirect=True
)
