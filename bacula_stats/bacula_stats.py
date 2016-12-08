import argparse
import sys
from six import iteritems

from tabulate import tabulate
from termcolor import colored, cprint

from .functions import gb_to_tb, client_fileset_size
from .views import all_backups, recent


def _all_backups():
    """Print all backups."""
    r = all_backups()
    jobs = r["jobs"]
    hosts = r["hosts"]
    totalsize = gb_to_tb(r["total_size"])
    print("Total size (TB): %s" % totalsize)
    for jck, jcv in iteritems(jobs):
        print(colored(jck, "white", attrs=["bold"]))
        for jfk, jfv in iteritems(jcv):
            for ck, cv in iteritems(hosts):
                if jck == ck:
                    if hosts[ck]["status"] == 1:
                        print(colored("%s - %s - %s TB" % (jck, jfk, client_fileset_size(jfv)), "grey", "on_green"))
                    elif hosts[ck]["status"] == 0:
                        print(colored("%s - %s - %s TB" % (jck, jfk, client_fileset_size(jfv)), "grey", "on_red"))
            li = list()
            for jpk, jpv in iteritems(jfv):
                for x in jpv:
                    li.append(x)
            print(tabulate(li, headers=["Pool", "JobId", "Size", "Ended", "Duration", "Files (#)", "Volume name"]))
            print("\n")
        print(". . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .")
        print("\n")


def _recent():
    """Print all recent backups."""
    r = recent()
    jobs = r["jobs"]
    hosts = r["hosts"]
    print("Recent jobs:\n\n")
    for jck, jcv in iteritems(jobs):
        print(colored(jck, "white", attrs=["bold"]))
        print("\n")
        for jfk, jfv in iteritems(jcv):
            for ck, cv in iteritems(hosts):
                if jck == ck:
                    if hosts[ck]["status"] == 1:
                        print(colored("%s - %s" % (jck, jfk), "grey", "on_green"))
                    elif hosts[ck]["status"] == 0:
                        print(colored("%s - %s" % (jck, jfk), "grey", "on_red"))
            li = list()
            for jpk, jpv in iteritems(jfv):
                if jpv == 0:
                    pool = colored(jpk, "red")
                    li.append([pool] + ["" for x in range(3)])
                    while len(pool) <= 34:
                        pool += " "  # Fill up whitespace to have tables same aligned.
                else:
                    if jpv[4] == 1:
                        pool = colored(jpk, "yellow")
                    elif jpv[4] == 0:
                        pool = colored(jpk, "green")
                    while len(pool) <= 34:
                        pool += " "  # Fill up whitespace to have tables same aligned.
                    pool += "."
                    li.append([pool] + [x for i, x in enumerate(jpv) if not i == 4])
            print(tabulate(li, headers=["Pool", "Size", "Ended", "Duration", "Files (#)"]))
            print("\n")
        print(". . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .")
        print("\n")


def clidoor():
    parser = argparse.ArgumentParser(description="bacula_stats - Display recent and all backups.")
    parser.add_argument("-a", "--all", action="store_true", help="Return all backups.", required=False)
    parser.add_argument("-r", "--recent", action="store_true", help="Return recent backups", required=False)
    args = vars(parser.parse_args())
    if args["recent"]:
        _recent()
    elif args["all"]:
        _all_backups()
