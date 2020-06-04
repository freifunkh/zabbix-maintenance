#!/usr/bin/env python3

# import argparse
import datetime
import json
import os.path
import urllib.parse
import urllib.request
# import sys


class ZabbixSession:
    def __init__(self, url, user=None, password=None):
        self.url = url
        self.user = user
        self.password = password
        self.auth = None
        self._request_id = 0

        if user:
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
        else:
            # try to read auth token from file
            with open(os.path.expanduser("~/.zabbix-cli_auth_token"), "r") as f:
                content = f.read().decode()
                if len(content) == 37 and content.startswith("cli::"):
                    self.auth = content[5:]

        if not self.auth:
            raise ValueError("No credentials given and no valid token file found.")

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

    def logout(self):
        # print("logout")
        data = {
            "method": "user.logout",
            "params": []
        }
        self._request(data)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if self.user:
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
        except KeyError:
            return None

    def maintenance_create(self, host_name, duration_minutes):
        # print("maintenance_create")
        duration_seconds = duration_minutes * 60
        host_id = self.get_host_id(host_name)
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
        self._request(data)

    def maintenance_delete_expired(self):
        # print("maintenance_delete_expired")
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
    # TODO: Proper interface
    # parser = argparse.ArgumentParser(description="")
    # parser.add_argument("url")
    # parser.add_argument("username")
    # parser.add_argument("password")
    # args = parser.parse_args()

    # if args.username and not args.password:
    #     print("Password missing.", file=sys.stderr)
    #     sys.exit(1)

    api_url = ""
    username = ""
    password = ""
    minutes = 30
    host = ""

    with ZabbixSession(api_url, username, password) as zabbix:
        zabbix.maintenance_create(host, minutes)
        zabbix.maintenance_delete_expired()
