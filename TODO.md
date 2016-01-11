# Flirble DNS Server - TODO

* Have each DNS server store some status and diagnostic data in the DB.
  This could report uptime, query counts, error counts, most recent
  errors etc.

* Track query stats/erors per zone. Maybe also track counts of which servers
  have been included in replies. Somehow track the reasons servers are not
  candidates and how often we fallback to default responses.

* Build a daemon variant of the load-updater. If we're doing it properly
  sophisticated then it would be quite flexible, so that for example
  it could be told to run local programs, probe HTTP servers and determine
  a value from these (query time, success/fail etc), or retrieve one
  directly from the target. These values would then be combined
  programmaticaly to form the final "load" value. Ideally this could be
  run either in daemon more or one-shot mode; the latter providing a decent
  way to test the configuration. Include a dry-run mode, too. Unlike
  `update-server-load` this would probably have a configuration file that
  has the directives of what to do in it.

* Really should write some tests for this thing now it has a fairly stable
  structure!

* DNSSEC? Is it possible with this Python DNS library?

* May want a way to cap the number of threads we'll spawn to handle
  requests. Similarly a way to limit the execution time of a thread would
  be good self-protection.

* Can we do runtime profiling of each handler thread?

* Introduce a non-geo method, but has the same other details (load limiting,
  maximum age etc). NAturally this would mean refactoring to break these
  candidate-list handling mechanisms into a common place.

* Optionally allow SOA serial number to be generated at runtime (eg, based
  on the current time)
