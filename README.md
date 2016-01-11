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
reliability concerns.


# Installation

See INSTALL.md for installation details.


# Setup and running the DNS server

## JSON files

Two example source files, `zones.json` and `servers.json`, provide a
reference to the contents of the database. You can load these sample
files, or other initial data, using `setup-rethinkdb`. See below.

JSON files are only a starting point. The database is part of a dynamic
system and the JSON files are just the initial dataset. Both zones and
server data can be updated in the database at run-time and in real-time.
It is naturally expected that server data will receive more updates than
zone data.


## Zone data

Refer to the file `zones.json` for a complete example. Zone data refers to
the naming of DNS resource records and specifying what information to respond
with whenthat name is queried.

DNS resource records are indicated with a straightforward JSON structure:

```json
[
	{
		"name": "ns0.l.flirble.org.",
		"type": "static",
		"ttl": 3600,
		"rr": [
			{
				"type": "A",
				"value": "192.168.10.10"
			},
	}
]
```

Aany familiarity with DNS should render these entries should be quite obvious.

* `name` _(string)_ is the RR name and must be fully qualified and include the
  final "`.`". The
* `type` (_string)_ field indicates how the DNS server will interpret the
  zone. Valid types currently include `static` for fixed entries and
  `geo-dist` for entries that will respond dynamically based on server load,
  distance, etc.
* `ttl` (_int_) is optional and provides the time-to-live integer value for
  DNS responses. The system default is 3600 seconds.
* `rr` _(list)_ contains the DNS resource records itself. This is a list of
  dictionaries, each containg one record for the name. Each entry typically
  has both a `type` field and a `value` field. The values are always strings
  unless otherwise noted.
  * `type` _(string)_ specifies the DNS record type. Valid values include
    `A`, `AAAA`, `CNAME`, `NS`, `MX` `PTR`, `SOA` `TXT` and `PTR`
  * `value` _(string)_ is required for types `A`, `AAAA`, `CNAME`, `NS`, `MX`,
    `PTR`, `TXT` and `PTR`.
  * `pref` _(int)_ is required for type `MX`.
  * `mname` _(string)_ is required for type `SOA`.
  * `rname` _(string)_ is required for type `SOA`.
  * `times` _(list)_ is required for type `SOA` and must be a list numbers
    for the zone time values.

There are some additional values required for a `geo-dist` zone, for example:

```json
[
	{
		"name": "g.l.flirble.org.",
		"type": "geo-dist",
		"groups": "flirble",
		"ttl": 5,
		"params": {
			"maxreplies": 2,
			"maxload": 10,
			"maxage": 120,
			"maxdist": 10000,
			"precision": 50
		},
		"rr": [
			...
		]
	}
]
```

* `groups` _(string or list)_ provides a list of server groups this zone will
  use for responses. These groups and their servers are defined in the
  _Server Data_ section. The list can be either a JSON list (e.g.
  `["one", "two"]`) or a comma-delimited list (e.g. `"one,two"`) inside a
  string.
* `params` _(dict)_ gives a set of operational parameters that are used when
  evaluating whether a server should be included in a DNS response.
  * `maxreplies` _(int)_ specifies the maximum number of servers to include
    in a response (assuming they all qualify for being in the response at
    all!) If not given, the default is `1`.
  * `maxload` _(float)_ signals the maximum reported server load to remain a
    candidate. Server loads can be reported in real-time and this value sets
    a cap on what is acceptable. This value is optional; if absent then no
    such load checking is performed for this zone.
  * `maxage` _(float)_ gives a maximum age of an update to be considered
    relevant. The updates that provide server load can contain a timestamp;
    if `maxage` is given then the age of the data can be checked and if too
    old the entry is ignored. This is optional; if not provided then no
    staleness checking is done.
  * `maxdist` _(float)_ indicates a maximum geographic distance to be allowed
    in the response. If not specified here then there is no limit. Currently
    distance is measured as approximately miles.
  * `precision` _(float)_ optionally governs how precise distance comparisons
    are. Distance calculations are rounded down to the nearest multiple of
    this value. If not specified the default value is `50.0` which will round
    values to the nearest 50 miles-ish.
* `rr` _(list)_ is optional for this zone type; if provided then its contents
  are used as a fallback should the `geo-dist` method fail to produce any
  results either because of some processing error or because no servers
  qualified.


## Server data

Refer to the file `servers.json` for a complete example. Server data is the
information use to determine candidate servers whose details may be included
in a DNS response. These details include the geographic location of the
server, its current "load" and so on.

The structure is straightforward. Servers are clustered into "groups" which
a zone file may reference to include that group of servers in the candidate
list. Each group contains a list of the servers it contains, and each server
is defined by a dictionary of key/values.  To maintain efficiency when
updates are distributed by the database the "group" and server "name" are
joined to form a compound key; group "`flirble`" and server "`castaway`"
becomes the key "`flirble!castaway`".

For example:

```json
[
    {
        "name": "default",
        "city": "none",
        "lat": 0,
        "lon": 0,
        "ipv4": "10.0.0.1",
        "ipv6": "2001:db8::1",
        "load": 0.0,
        "ts": -1.0
    },
    {
        "name": "flirble!castaway",
        "city": "nyc",
        "lat": 40.7127,
        "lon": -74.0059,
        "ipv4": "207.162.195.200",
        "ipv6": "2001:6f8:0:102::1000:1",
        "load": -1.0,
        "ts": 0.0
    }
]
```

The attributes here are:

* `name` _(string)_ is the name of this entry; it is usually a compound of
  the group name and the server name with a delimiting "`!`". A "`default`"
  entry may be provided and is used only when none of the other servers
  qualify as candidates.
* `city` _(string)_ is an informational field indicating the location of the
  server. This is not currently used other than in diagnostic `TXT` records.
* `lat` _(float)_ gives the latitude of the server location. Depending on
  the precision you are attempting to use, the `lat` and `lon` do not normally
  need to be especially accurate.
* `lon` _(float)_ gives the longitude of the server location.
* `ipv4` _(float)_ indicates the IPv4 address to use in an `A` record for
  this server.
* `ipv6` _(float)_ indicates the IPv6 address to use in an `AAAA` record for
  this server.
* `load` _(float)_ indicates the current load of the server. It is expected
  this value will be updated periodically (and possibly often). If the value
  given is a negative number then the server is assume unavailable.
* `ts` _(float)_ is the timestamp of this entry. If the zone provides the
  `maxage` parameter then the age of the update (current time subtract `ts`)
  is checked and if considered stale this entry will not be considered in the
  response. If the value of this field is negative then the entry is
  considered static and this overrides the staleness check. For an initial
  load this value should be `0.0` to prevent the server becoming a candidate
  until a runtime update is provided or `-1.0` if this is not a dynamic system
  and the entry should always be considered regardless of age. The `ts`
  value is a count of the number of seconds since `1970-01-01T00:00:00`,
  otherwise known as the UNIX epoch.


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
your query to that address; though caution is advised since this will cut
your computer off from reaching the real host of those addresses.


## Loading initial data

Several options to this program govern what JSON files it will load and
where it will try to store them.

`./setup-rethinkdb --help`
`./setup-rethinkdb --debug`

By default it will try to connect to a RethinkDB on `localhost` at the usual
port `28015` and will load `zones.json` and `servers.json` from the current
directory and load them into the `zones` and `servers` tables respectively.


## Updating server load

The load value is a floating point number and can be any valid such value.
Zones can indicate a maximum load threshold in order to keep a host in
consideration as a target.

`./update-server-load --help`
`./update-server-load --group flirble --name castaway --load $(date +%M.%S)`
`./update-server-load -g flirble -n castaway -l $(date +%M.%S) --rethinkdb-port 28016`

This program also provides a timestamp for the update; you can indicate this
is a static entry with `--static`; otherwise the timestamp is compared to the
`maxage` value of the zone, if present. If the update is stale (older than
allowed by `maxage`) then it's not a candidate for DNS responses.
