= Flirble DNS Server

== Ubuntu depdendencies

```
sudo apt-get install -y build-essential git autoconf automake libtool python-dev python-pip zlib1g-dev libcurl4-openssl-dev python-daemon python-lockfile

sudo pip install dnslib
```

== Setup GeoIP2 database

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
sudo adduser --system --no-create-home --gecos GeoIP --home /usr/local/share/GeoIP --group geoip geoip

sudo chown geoip:geoip /usr/local/share/GeoIP

echo "13 1 * * 1 geoip /usr/local/bin/geoipupdate" > /etc/cron.d/geoipupdate

git clone --recursive https://github.com/maxmind/libmaxminddb.git
cd libmaxminddb
./bootstrap && ./configure && make && sudo make install

sudo pip install maxminddb
sudo pip install geoip2
```

