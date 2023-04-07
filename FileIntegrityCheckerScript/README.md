# File Integrity Checker Script v1.0

Frank W. Zammetti

This script is used to validate the integrity of files.  This is accomplished by scanning a configured set
of directories (optionally including subdirectories) and for each file encountered, calculating a checksum (hash) for
it and storing that checksum, along with the last modified date/time on the file, in a database.  In subsequent runs,
the entries in the database are compared to the current state of the file on the file system.

This is useful for data archivists who want to ensure their data hasn't become corrupted ("bit rot").  If you have
an archive of files, you can scan it with this script periodically and ensure no problems are reported.

# File integrity rules

The rules applied that determine if a file has "maintained its integrity" are:

1. Any files in the database that are no longer found on the file system are removed from the database.

2. If a file on the file system is not yet in the database, it is added to the database.

3. For files in the database that are on the file system, the last modified date/time is compared.  If that of the
   file on the file system is newer, the database entry is updated (if the script is configured to do so - see the
   **allow_file_changes** config option below).  If it's older, this is reported as a possible file system corruption
   (user will need to manually investigate).

4. If the last modified date/time match, then the checksum is recalculated (again, subject to the **allow_file_changes**
   setting).  If it matches what's in the database, then the file is considered okay.  If they don't match then a
   mismatch is reported as probable bit rot.

# Configuring the script

The script depends on a configuration file named **config.json** being present in the same directory (it will abort
if the file isn't found).  The format of this file is:

    {
      "verbose_output": <true|false>,
      "directories_to_scan": [
        { "path": "<string>", "scan_subdirectories": <true|false>, "allow_file_changes": <true|false> }
      ],
      "output_to_file": <true|false>,
      "checksum_algorithm": "md5|sha1|sha224|sha256|sha384|sha512",
      "override_status": [
      ]
    }

The elements are:

* **verbose_output**: (REQUIRED) whether you want to see verbose output in the console (and the output file, if
configured to write to an output file.

* **directories_to_scan**: (REQUIRED each element in this array is an object that defines a directory you want to scan
files in.  Each object has three REQUIRED properties:
  * **path**: (REQUIRED) the full path to the directory.
  * **scan_subdirectories**: (REQUIRED) determines if scanning should recurse into subdirectories (true) or
not (false).
  * **allow_file_changes**: (REQUIRED) determines if files are allowed to change (true) - meaning their checksum can
change and the script will just silently update the checksum and last modified info in the database (good for files like
documents that you expect may sometimes change) - or not (false), which is good for actual archived files that
you expect to never change.

* **output_to_file**: (REQUIRED) whether you want the output to go to a file (true) or not (false).  The file will be
named output.txt and will be written into the same directory as the script (any existing file will be overwritten).

* **checksum_algorithm**: (REQUIRED) what checksum (hash) algorithm to use to calculate
file checksums (note that changing this after the database has been created will cause all files to register as bit rot,
so if you decide to change the algorithm then you should also delete the SQLite **database.db** file that was generated
and run the script again).

* **override_status**: (OPTIONAL) each element in this array is a plain string where each is a key in the database
of a file that you want to force recalculation of the checksum for.  See the "How to deal with bit rot"
section below for more details on this element.

Note that there isn't much in the way of error checking done, aside from ensuring the file exists, or that it is
valid, so make sure you get it right (you'll probably just get exceptions if you don't, but no explicit effort
is made to ensure the file is correct).

Here is a complete, valid config file for reference and to serve as a starting point (for use on a Windows
system only):

    {
      "verbose_output": false,
      "directories_to_scan": [
        { "path": "C:\\Windows", "scan_subdirectories": true, "allow_file_changes" : false }
      ],
      "output_to_file": true,
      "checksum_algorithm": "md5",
      "override_status" : [
        "C:\\Windows\\notepad.exe"
      ]
    }

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

# How to deal with bit rot

So, let's say the script reports that a file has bit rot.  If you re-run the script at
that point, it will continue to be reported as such.  If you investigate and discover the file indeed got corrupted
somehow, and you then restore it from a backup, there are several possible outcomes:

* If **allow_file_changes** is set to true, and the last modified date/time doesn't indicate a possible file system
corruption, then the checksum of the file will be updated and it will be deemed okay again

* If **allow_file_changes** is set to false, and the last modified date/time doesn't indicate a possible file system
corruption, then the file will be deemed okay again as long as the checksum in the database matches, which would be
true if it was recorded before the corruption occurred.

But, what happens if you get into a situation where a file is "stuck" as being seen as corrupted because the checksum
in the database was actually recorded from the corrupt copy of the file?  You can handle this by adding the
**override_status** element to the config file.  Each element in this array is a string that is the key of the file
to update in the database.  What's the key, you ask?  It's simply the full path to the file.  The script will display
this when it reports bit rot, so you can just copy it from the console or the output file (though note that you'll need
to change \ to \\\ in them on Windows).  Then, re-run the script, and it will re-calculate the checksum and record the
last modified date without checking anything.  Essentially, this is a way to force the script to tell the sceipt
"this file is good as-is, just update its information in the database immediately".  After that, you're in the correct
state and the file will be seen as okay again.  You will have to remove **override_status** at that point for the
script to run in its normal mode.

Basically, in MOST cases, you SHOULDN'T need **override_status**.  The whole point of the script is that you run it
to record the checksum of all the files you want to monitor - WHICH ARE ASSUMED TO BE VALID AT THE TIME YOU RUN THE
SCRIPT THE FIRST TIME - so if bit rot shows up, restoring the file SHOULD then get the checksum of the file to match
what's in the database again without you doing anything else.  But, this additional capability could come into play
under some circumstances, hence the reason I added it.

# Gotchas

1. If a filename has non-ASCII characters in it, the script will blow up.  This is a known issue that I'm looking into.
I'm not sure how to deal with it yet, so for now just be aware of that.

# Pull Requests

I'm totally open to pull requests on this.  I'm not a Python expert first of all, so I have no doubt there are
better ways to do things here.  I'd love to accept some pulls that improve performance, for example, but I'm generally
open to anything that makes sense.  Fire away, if you feel like it!

*Last updated: April 5, 2023*
