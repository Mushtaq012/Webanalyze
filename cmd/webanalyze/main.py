import csv
import json
import os
import sys
import time
from queue import Queue
from threading import Thread
from urllib.parse import urlparse

import requests

import webanalyze

update = False
output_method = "stdout"
workers = 4
techs_filename = "technologies.json"
host = ""
hosts = ""
crawl_count = 0
search_subdomain = True
silent = False
redirect = False


def main():
    global output_method, update, workers, techs_filename, host, hosts, crawl_count, search_subdomain, silent, redirect

    parse_arguments()

    if update:
        update_apps_file()

    # Lookup technologies.json file
    techs_filename = lookup_folders(techs_filename)
    techs_file = open(techs_filename, "r")

    wa, err = webanalyze.NewWebAnalyzer(techs_file, None)
    if err:
        sys.exit(f"Initialization failed: {err}")

    if not silent:
        print_header()

    if output_method == "csv":
        out_writer = csv.writer(sys.stdout)
        out_writer.writerow(["Host", "Category", "App", "Version"])
    else:
        out_writer = None

    hosts_queue = Queue()

    # Start worker threads
    for _ in range(workers):
        worker = Thread(target=process_hosts, args=(wa, out_writer, hosts_queue))
        worker.daemon = True
        worker.start()

    # Read hosts from file or use single host
    if host:
        hosts_queue.put(host)
    else:
        with open(hosts, "r") as f:
            for line in f:
                hosts_queue.put(line.strip())

    hosts_queue.join()


def parse_arguments():
    global output_method, update, workers, techs_filename, host, hosts, crawl_count, search_subdomain, silent, redirect

    for arg in sys.argv[1:]:
        if arg == "-update":
            update = True
        elif arg.startswith("-output="):
            output_method = arg[len("-output="):]
        elif arg.startswith("-worker="):
            workers = int(arg[len("-worker="):])
        elif arg.startswith("-apps="):
            techs_filename = arg[len("-apps="):]
        elif arg.startswith("-host="):
            host = arg[len("-host="):]
        elif arg.startswith("-hosts="):
            hosts = arg[len("-hosts="):]
        elif arg.startswith("-crawl="):
            crawl_count = int(arg[len("-crawl="):])
        elif arg == "-search":
            search_subdomain = True
        elif arg == "-silent":
            silent = True
        elif arg == "-redirect":
            redirect = True
        else:
            print(f"Unknown argument: {arg}")
            sys.exit(1)


def update_apps_file():
    try:
        webanalyze.DownloadFile("technologies.json")
        if not silent:
            print("App definition file updated")
    except Exception as e:
        sys.exit(f"Error: Can not update apps file: {e}")


def print_header():
    print_option("webanalyze", "v" + webanalyze.VERSION)
    print_option("workers", workers)
    print_option("technologies", techs_filename)
    print_option("crawl count", crawl_count)
    print_option("search subdomains", search_subdomain)
    print_option("follow redirects", redirect)
    print()


def print_option(name, value):
    print(f" :: {name:<17} : {value}")


def process_hosts(wa, out_writer, hosts_queue):
    while True:
        host = hosts_queue.get()
        job = webanalyze.NewOnlineJob(host, "", None, crawl_count, search_subdomain, redirect)
        result, links = wa.Process(job)

        if search_subdomain:
            for link in links:
                crawl_job = webanalyze.NewOnlineJob(link, "", None, 0, False, redirect)
                result, _ = wa.Process(crawl_job)
                output(result, wa, out_writer)

        output(result, wa, out_writer)
        hosts_queue.task_done()


def output(result, wa, out_writer):
    if result.Error:
        sys.stderr.write(f"{result.Host} error: {result.Error}\n")
        return

    if output_method == "stdout":
        print(f"{result.Host} ({result.Duration:.1f}s):")
        for match in result.Matches:
            categories = [wa.CategoryById(cid) for cid in match.App.Cats]
            print(f"    {match.AppName}, {match.Version} ({', '.join(categories)})")
        if not result.Matches:
            print("    <no results>")
    elif output_method == "csv":
        for match in result.Matches:
            categories = ", ".join(match.CatNames)
            out_writer.writerow([result.Host, categories, match.AppName, match.Version])
    elif output_method == "json":
        output = {"hostname": result.Host, "matches": result.Matches}
        json_output = json.dumps(output)
        print(json_output)


def lookup_folders(filename):
    if os.path.isabs(filename):
        return filename

    executable = os.path.abspath(sys.argv[0])
    executable_dir = os.path.dirname(executable)

    home = os.path.expanduser("~")

    folders = ["./", executable_dir, home]

    for folder in folders:
        path = os.path.join(folder, filename)
        if os.path.exists(path):
            return path

    sys.exit(f"Could not find the technologies file: {filename}")


if __name__ == "__main__":
    main()
