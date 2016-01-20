# Flirble DNS Server - Installation

Outside the scope of this README at the moment: Setup a RethinkDB host or
cluster.

There are two sections here; one for pre-prepared Ubuntu packages and a second
group showing how to install the packages Ubuntu doesn't have from source or
Python pip.


## Ubuntu 14.04 (Trusty) pre-built dependencies

A Launchpad PPA is available with the required Python and binary dependencies
that are not available in the normal Trusty repository. Simply add the
`ppa:chrisy/fdns` PPA with `add-apt-repository ppa:chrisy/fdns` and
`apt-get update`.

Then:
```
sudo apt-get install -y git libpgm-5.1-0 \
    libmaxminddb0 libsodium13 libzmq3 geoip-bin geoipupdate mmdb-bin \
    python-daemon python-ipaddr python-dnslib python-maxminddb \
    python-geoip2 python-lockfile python-zmq
```

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

## Ubuntu 14.04 (Trusty) depdendencies - without prebuilt packages

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


