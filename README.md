# Flirble DNS Server

This project provides a simple authoritative DNS server with a dynamic
backend. Whilst it can also serve some static content its primary role is to
respond to queries with records that reflect the result of an algorithm.

In the initial version the program offers a simple distance comparison between
a requesting DNS client and a set of target servers. The location of the
client is discovered using the Maxmind GeoIP database; the location of the
servers is provided in the server definition.

Future versions will be even more dynamic by allowing servers to register
themselves and continuously provide their health state.

This system is not meant to be a replacement for a more robust commercial
solution, such as from a content delivery network.


# Installation

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

TODO: find rethinkb

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

## zones.json

## servers.json

