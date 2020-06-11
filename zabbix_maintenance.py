#!/usr/bin/env python3

import argparse
import configparser
import datetime
import json
import os.path
import urllib.parse
import urllib.request
import socket
import sys


class ZabbixCliConfig:
    def __init__(self):
        zabbix_config = "~/.zabbix-cli/zabbix-cli.conf"
        zabbix_auth = "~/.zabbix-cli_auth_token"

        # find URL
        try:
            config = configparser.ConfigParser()
            config.read(os.path.expanduser(zabbix_config))
            self.url = config["zabbix_api"]["zabbix_api_url"]
        except KeyError:
            self.url = None

        # find auth token
        try:
            with open(os.path.expanduser(zabbix_auth), "r") as f:
                content = f.read()
                if len(content) == 37 and content.startswith("cli::"):
                    self.auth = content[5:]
        except FileNotFoundError:
            self.auth = None


class ZabbixSession:
    def __init__(self, url, user=None, password=None, auth=None):
        if auth:
            self.user = None
            self.password = None
            self.auth = auth
        else:
            self.user = user
            self.password = password
            self.auth = None

        self.logged_in = False
        self.url = url
        self._request_id = 0

    def _request(self, data):
        data["jsonrpc"] = "2.0"
        data["auth"] = self.auth
        data["id"] = self.get_request_id()
        encoded = json.dumps(data).encode("utf-8")
        r = urllib.request.Request(self.url,
                                   data=encoded,
                                   headers={"Content-Type": "application/json-rpc"},
                                   method="POST")
        return json.load(urllib.request.urlopen(r))

    def get_request_id(self):
        self._request_id += 1
        return self._request_id

    def login(self):
        # login by username and password
        data = {
            "method": "user.login",
            "params": {
                "user": self.user,
                "password": self.password
            }
        }
        response = self._request(data)
        self.auth = response["result"]
        self.logged_in = True

    def logout(self):
        data = {
            "method": "user.logout",
            "params": []
        }
        self._request(data)

    def __enter__(self):
        if not self.auth:
            self.login()
        return self

    def __exit__(self, type, value, traceback):
        if self.logged_in:
            # logged in by username and password
            self.logout()

    def get_host_id(self, host_name):
        data = {
            "method": "host.get",
            "params": {
                "output": ["hostid"],
                "selectGroups": "extend",
                "filter": {
                    "host": [host_name]
                }
            }
        }
        response = self._request(data)
        try:
            return response["result"][0]["hostid"]
        except IndexError:
            return None
        except KeyError:
            return None

    def maintenance_create(self, host_name, duration_minutes):
        duration_seconds = duration_minutes * 60
        host_id = self.get_host_id(host_name)
        if not host_id:
            raise ValueError("Unknown host: " + str(host_name))
        dt = datetime.datetime.now()
        time_start = int(dt.timestamp())
        time_stop = time_start + duration_seconds
        maintenance_name = dt.strftime("Automatic {} min (since %Y-%m-%d %H:%M:%S)".format(duration_minutes))
        data = {
            "method": "maintenance.create",
            "params": {
                "name": maintenance_name,
                "description": "Host: {}".format(host_name),
                "active_since": time_start,
                "active_till": time_stop,
                "hostids": [host_id],
                "groupids": [],
                "timeperiods": [
                    {
                        "period": duration_seconds
                    }
                ],
                "tags": []
            }
        }
        result = self._request(data)
        if "error" in result:
            raise ValueError("API error:\n{} {}".format(result["error"].get("message", ""),
                                                        result["error"].get("data", "")))

    def maintenance_delete_expired(self):
        now = int(datetime.datetime.now().timestamp())
        data = {
            "method": "maintenance.get",
            "params": {
                "output": "extend",
                "selectGroups": "extend",
                "selectTimeperiods": "extend",
                "selectTags": "extend"
            }
        }
        response = self._request(data)
        expired = [elem["maintenanceid"] for elem in response["result"]
                   if elem["name"].startswith("Automatic ") and int(elem["active_till"]) < now]
        data = {
            "method": "maintenance.delete",
            "params": expired
        }
        self._request(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sets the host into Zabbix maintenance mode. \
Config of zabbix-cli is used if user, password or URL are undefined.")
    parser.add_argument("--url", help="Zabbix API URL")
    parser.add_argument("--user", help="API user name")
    parser.add_argument("--password", help="API password")
    parser.add_argument("minutes", type=int, help="Length of the maintenance window")
    args = parser.parse_args()

    config = ZabbixCliConfig()

    if args.url:
        api_url = args.url
    elif config.url:
        api_url = config.url
    else:
        print("URL undefined.", file=sys.stderr)
        sys.exit(1)

    if args.user:
        user = args.user
        password = args.password
        auth = None
    elif config.auth:
        user = None
        password = None
        auth = config.auth
    else:
        user = None
        password = None
        auth = None

    host = socket.gethostname()

    with ZabbixSession(url=api_url, user=user, password=password, auth=auth) as zabbix:
        try:
            zabbix.maintenance_create(host, args.minutes)
            zabbix.maintenance_delete_expired()
        except ValueError as e:
            print(e, file=sys.stderr)
            sys.exit(2)
