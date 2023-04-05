# File Integrity Checker Script v1.0

Frank W. Zammetti

This script is used to validate the integrity of files.  This is accomplished by scanning a configured set
of directories (optionally including subdirectories) and for each file encountered, calculating a checksum (hash) for
it and storing that checksum, along with the last modified date/time on the file, in a database.  In subsequent runs,
the entries in the database are compared to the current state of the file on the file system.

This is useful for data archivists who want to ensure their data hasn't become corrupted ("bit rot").  If you have
an archive of files, you can scan it with this script periodically and ensure no problems are reported.

# File integrity rules

The rules applied that determine if a file as "maintained its integrity" are:

1. Any files in the database that are no longer found on the file system are removed from the database

2. If a file on the file system is not yet in the database, it is added to the database

3. For files in the database that are on the file system, the last modified date/time is compared.  If that of the
   file on the file system is newer, the database entry is updated.  If it's older, this is reported as a possible
   file system corruption (user will need to manually investigate).

4. If the last modified date/time match, then the checksum is recalculated.  If it matches what's in the database then
   the file is considered okay.  If they don't match then a mismatch is reported as probable bit rot.

# Configuring the script

The script depends on a configuration file named **config.json** being present in the same directory (it will abort
if the file isn't found).  The format of this file is:

    {
      "verbose_output": false,
      "directories_to_scan": [
        { "path": "C:\\test\\files", "scan_subdirectories": true }
      ],
      "output_to_file": true,
      "checksum_algorithm": "md5"
    }

The elements are:

* **verbose_output** (true|false): whether you want to see verbose output in the console

* **directories_to_scan** (array): each element of this array is an object that defines a directory you want to scan
files in.  Each object has two REQUIRED properties:
  * **path**, which is the full path to the directory, and
  * **scan_subdirectories**, which is either true or false and determines if scanning should recurse into
subdirectories (true) or not (false)

* **output_to_file** (true|false): whether you want the output to go to a file (true) or not (false) - the file will be
named output.txt and will be written into the same directory as the script (any existing file will be overwritten)

* **checksum_algorithm**: (md5|sha1|sha224|sha256|sha384|sha512): what checksum (hash) algorithm to use to calculate
file checksums (note that changing this after the database has been created will cause all files to register as bit rot,
so if you decide to change the algorithm then you should also delete the SQLite **database.db** file that was generated
and run the script again)

Note that **ALL** elements are **REQUIRED** in the config file (as they are in each element in the
**directories_to_scan** array).  Also note that there isn't much in the way of error checking done, aside from ensuring
the file exists, so make sure you get it right (you'll probably just get exceptions if you don't, but no explicit effort
is made to ensure the file is valid).

# Running the script

Running the script is simple:

    py FileIntegrityCheckerScript.py

There are no command line switches.

# Real-world usage

In general, you will likely want to run this script with **verbose_output** set to **false** and **output_to_file**
set to **true**.  Then, after running the script, simply search the **output.txt** file for **!!!!!** since any errors
are reported beginning with that sequence.  Any reported as bit rot are likely to be data corruption.  Any reported
as (possible) file system corruption should be investigated further to see if there is actually a problem.  Any other
errors are likely to be simple configuration issues that can be corrected and the script re-run.  I also suggest
only using the MD5 algorithm unless you have a specific reason not to, simply for performance reasons.

I have personally been using this script for some time on my home server to validate things like source code
repositories, home movies, photos, and more.  I've tweaked it over time, but for the most part it has always worked as
expected.  As for performance, it takes about 12 hours to scan around 120,000 files totaling around 9Tb in size.  So,
not super-fast, but not ridiculous in my mind either (files stored on not-exactly-top-of-the-line spinners).  Note
though that this is a Windows server and I have not yet tested this on \*nix machines.  I don't THINK there's anything
that would make it not work, but YMMV.

Of course, I have to put a disclaimer here: use at your own risk!  While I've made every effort to ensure this works...
and like I said, I trust my own data with it... I don't want death threats if your find your files rotting away and
this script didn't alert you to it.  You know how it goes: backups, backups, backups.  If you don't have it backed up
in a robust manner then you effectively didn't want to keep it, right?  That said, this script SHOULD be helpful to
catch any problems that can occur with long-term storage of data.  If nothing else, think of it as defense-in-depth:
you still want RAID and off-site backups and parity files and such, but one more layer generally can't hurt!

And I'm totally open to pull requests on this.  I'm not a Python expert first of all, so I have no doubt there are
better ways to do things here.  I'd love to accept some pulls that improve performance, for example, but I'm generally
open to anything that makes sense.  Fire away, if you feel like it!

*Last updated: April 5, 2023*
