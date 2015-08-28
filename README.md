# Flirble DNS Server

## Ubuntu depdendencies

```
sudo apt-get install -y build-essential git autoconf automake libtool \
    python-dev python-pip zlib1g-dev libcurl4-openssl-dev \
    python-daemon python-lockfile

sudo pip install dnslib
```

If the Ubuntu `python-lockfile` package is too old, you may also need to
`sudo pip install lockfile` to make the pidlockfile method available.

## Setup GeoIP2 database

```
cd
mkdir -p dev
cd dev
git clone https://github.com/maxmind/geoipupdate.git
cd geoipupdate
./bootstrap && ./configure && make && sudo make install
cd ..

sudo tee /usr/local/etc/GeoIP.conf <<EOT
# The following UserId and LicenseKey are required placeholders:
UserId 999999
LicenseKey 000000000000

# Include one or more of the following ProductIds:
# * GeoLite2-City - GeoLite 2 City
# * GeoLite2-Country - GeoLite2 Country
# * GeoLite-Legacy-IPv6-City - GeoLite Legacy IPv6 City
# * GeoLite-Legacy-IPv6-Country - GeoLite Legacy IPv6 Country
# * 506 - GeoLite Legacy Country
# * 517 - GeoLite Legacy ASN
# * 533 - GeoLite Legacy City
ProductIds GeoLite2-City GeoLite2-Country GeoLite-Legacy-IPv6-City GeoLite-Legacy-IPv6-Country 506 517 533
EOT
sudo mkdir -p /usr/local/share/GeoIP

sudo addgroup --system geoip
sudo adduser --system --no-create-home --gecos GeoIP --home /usr/local/share/GeoIP --group geoip

sudo chown geoip:geoip /usr/local/share/GeoIP

echo "13 1 * * 3 geoip /usr/local/bin/geoipupdate" | sudo tee /etc/cron.d/geoipupdate

sudo -u geoip /usr/local/bin/geoipupdate
```

## Install the Python bindings for GeoIP2

```
git clone --recursive https://github.com/maxmind/libmaxminddb.git
cd libmaxminddb
./bootstrap && ./configure && make && sudo make install

sudo pip install maxminddb
sudo pip install geoip2
```

