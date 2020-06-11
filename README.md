# zabbix-maintenance
A tool to move a host to Zabbix maintenance mode for the next n minutes.

I built this as a quick fix because [I don't understand zabbix-cli](https://github.com/unioslo/zabbix-cli/issues/125) yet.
```
usage: zabbix_maintenance.py [-h] [--url URL] [--user USER] [--password PASSWORD] minutes

Sets the host into Zabbix maintenance mode. Config of zabbix-cli is used if user, password or URL are undefined.

positional arguments:
  minutes              Length of the maintenance window

optional arguments:
  -h, --help           show this help message and exit
  --url URL            Zabbix API URL
  --user USER          API user name
  --password PASSWORD  API password
```
