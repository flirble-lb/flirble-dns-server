# Flirble DNS Server

This project provides an authoritative DNS server with a dynamic backend.
Whilst it can also serve some static content its primary role is to respond
to queries with records that reflect the result of some computation.

Current backends:
* Static.
* GeoIP.

The GeoIP backend supports these concepts for building a response:
* A list of "servers".
* Each server has coordinates (lat/lon) and its distance from the querying
  DNS server is computed.
* Servers are ranked (sorted) by this distance.
* If both a server and a zone that uses it reports a "load" value then the
  zone value indicates the maximum such value a server can report and still
  be considered in the response.
* If for whatever reason a GeoIP lookup is not possible, or no candidate
  hosts survive the above steps, then fallback to a static response is
  possible.

Using RethinkDB as a backend datastore this DNS server we can maintain
consistent state across a cluster of hosts. It similarly uses RethinkDB to
maintain the "server" list, and the load values. Programs are provided to
load initial data into RethinkDB as well as to maintain the "load" value
for each server.

This system is not meant to be a replacement for a more robust commercial
solution, such as from a content delivery network. In particular there may
be performance issues with this implmenetation and certainly long term
relibability concerns.


# Installation

Outside the scope of this README at the moment: Setup a RethinkDB host or
cluster.

There are two sections here; one for Ubuntu hosts installing a bunch of
Python packages by hand, and a second group showing how to install these
same things from backported packages (which I may make available somewhere
someday.)


## Ubuntu 14.02 depdendencies

```
sudo apt-get install -y build-essential git autoconf automake libtool \
    python-dev python-pip zlib1g-dev libcurl4-openssl-dev \
    python-daemon python-lockfile

sudo pip install dnslib
sudo pip install rethinkdb
```

If the Ubuntu `python-lockfile` package is too old, you may also need to
`sudo pip install lockfile` to make the pidlockfile method available.


### Setup GeoIP2 database

```
cd
mkdir -p dev
cd dev
git clone https://github.com/maxmind/geoipupdate.git
cd geoipupdate
./bootstrap && ./configure && make && sudo make install
cd ..

sudo tee /usr/local/etc/GeoIP.conf <<EOT
UserId 999999
LicenseKey 000000000000
ProductIds GeoLite2-City GeoLite2-Country GeoLite-Legacy-IPv6-City GeoLite-Legacy-IPv6-Country 506 517 533
EOT

sudo mkdir -p /usr/local/share/GeoIP

sudo addgroup --system geoip
sudo adduser --system --no-create-home --gecos GeoIP --home /usr/local/share/GeoIP --group geoip

sudo chown geoip:geoip /usr/local/share/GeoIP

echo "13 1 * * 3 geoip /usr/local/bin/geoipupdate" | sudo tee /etc/cron.d/geoipupdate

sudo -u geoip /usr/local/bin/geoipupdate
```

### Install the Python bindings for GeoIP2

```
git clone --recursive https://github.com/maxmind/libmaxminddb.git
cd libmaxminddb
./bootstrap && ./configure && make && sudo make install

sudo pip install maxminddb
sudo pip install geoip2
```


## Ubuntu 14.02 dependencies with backported packages

This assumes availability of a directory of backported (from Vivid)
or otherwise built-for-trusty packages for GeoIP, ZeroMQ and dnslib.

```
sudo apt-get install -y git python-daemon python-ipaddr libpgm-5.1-0
sudo dpkg -i \
	libmaxminddb0_1.0.4-2_amd64.deb \
	libsodium13_1.0.3-1_amd64.deb \
	libzmq3_4.0.5+dfsg-3ubuntu1~gcc5.1_amd64.deb \
	geoip-bin_1.6.6-1_amd64.deb \
	geoipupdate_2.2.1-1_amd64.deb \
	mmdb-bin_1.0.4-2_amd64.deb \
	python-dnslib_0.9.4-1_all.deb \
	python-maxminddb_1.2.0-1_amd64.deb \
	python-geoip2_2.2.0-1_all.deb \
	python-lockfile_0.10.2-2ubuntu1_all.deb \
	python-zmq_14.4.1-0ubuntu5_amd64.deb
```

TODO: find/build rethinkb client .deb


### Setup and fetch GeoIP data

```
sudo tee /etc/GeoIP.conf <<EOT
DatabaseDirectory /usr/local/share/GeoIP
UserId 999999
LicenseKey 000000000000
ProductIds GeoLite2-City GeoLite2-Country GeoLite-Legacy-IPv6-City GeoLite-Legacy-IPv6-Country 506 517 533
EOT

sudo mkdir -p /usr/local/share/GeoIP

sudo addgroup --system geoip
sudo adduser --system --no-create-home --gecos GeoIP --home /usr/local/share/GeoIP --group geoip

sudo chown geoip:geoip /usr/local/share/GeoIP

echo "13 1 * * 3 geoip /usr/bin/geoipupdate" | sudo tee /etc/cron.d/geoipupdate

sudo -u geoip /usr/bin/geoipupdate
```


# Setup

## JSON files

Two example source files, `zones.json` and `servers.json`, provide a
reference to the contents of the database. You can load these sample
files, or other initial data, using `setup-rethinkdb`. See below.

## Running `dns-server`

`./dns-server --help`
`./dns-server --debug`

By default the DNS server will try to bind to port `8053` meaning that it
will happily run as an unprivileged user, but won't respond to DNS queries
on the standard port `53`.

There are several ways around this. You could run the process as `root`
on Unix-like systems; however this is strongly not recommended. More
favorable is to run it as an unprivileged user and use some system
firewall function to provide port translation from `53` to, for example,
`8053`.

Also, for testing purposes, programs like `dig` do allow you to specify the
port number to use; for example:

```
$ dig @localhost -p 8053 -t any g.l.flirble.org.

; <<>> DiG 9.8.3-P1 <<>> @localhost -p 8053 -t any g.l.flirble.org.
; (3 servers found)
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 2691
;; flags: qr aa rd; QUERY: 1, ANSWER: 4, AUTHORITY: 2, ADDITIONAL: 4
;; WARNING: recursion requested but not available

;; QUESTION SECTION:
;g.l.flirble.org.		IN	ANY

;; ANSWER SECTION:
g.l.flirble.org.	5	IN	A	10.20.30.40
g.l.flirble.org.	5	IN	AAAA	2001:dba:10::10:20:30:40
g.l.flirble.org.	5	IN	TXT	"name:flirble!fallback"
g.l.flirble.org.	5	IN	TXT	"city:somewhere"

;; AUTHORITY SECTION:
l.flirble.org.		1800	IN	NS	ns0.l.flirble.org.
l.flirble.org.		1800	IN	NS	ns1.l.flirble.org.

;; ADDITIONAL SECTION:
ns0.l.flirble.org.	1800	IN	A	192.168.10.10
ns0.l.flirble.org.	1800	IN	AAAA	2001:dba:0:10::10:10
ns1.l.flirble.org.	1800	IN	A	192.168.11.11
ns1.l.flirble.org.	1800	IN	AAAA	2001:dba:0:11::11:11

;; Query time: 20 msec
;; SERVER: ::1#8053(::1)
;; WHEN: Wed Dec 30 15:27:33 2015
;; MSG SIZE  rcvd: 262
```

Note however that when using `localhost` it is usually impossible to
perform a GeoIP lookup. To test GeoIP and dynamic responses the use of
IP aliases on the loopback interface will help. Strategically choosing
addresses in different parts of the world and binding them to the loopback
interface will mean you can test each of those regions by simply directing
your query to that address; though note it will cut your computer off from
reaching the real host of those addresses.


## Loading data

Several options to this program govern what JSON files it will load and
where it will try to store them.

`./setup-rethinkdb --help`
`./setup-rethinkdb --debug`


## Updating server load

The load value is a floating point number and can be any valid such value.
Zones can indicate a maximum load threshold in order to keep a host in
consideration as a target.

`./update-server-load --help`
`./update-server-load --group flirble --name castaway --load $(date +%M.%S)`
`./update-server-load -g flirble -n castaway -l $(date +%M.%S) --rethinkdb-port 28016`
