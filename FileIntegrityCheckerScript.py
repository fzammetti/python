#!/usr/bin/env python
"""
File Integrity Checker Script v1.0

This script is used to validating files to ensure their integrity.  This is accomplished by scanning a configured set
of directories (optionally including subdirectories) and for each file encountered, calculating a checksum (hash) for
it and storing that hash, along with the last modified date/time on the file, in a database.  In subsequent runs, the
entries in the database are compared to the current state of the file on the file system.  Thr rules applied are:

1. Any files in the database that are no longer found on the file system are removed from the database
2. If a file on the file system is not yet in the database, it is added to the database
3. For files in the database that are on the file system, the last modified date/time is compared.  If that of the
   file on the file system is newer, the database entry is updated.  If it's older, this is reported as a possible
   file system corruption (user will need to manually investigate).
4. If the last modified date/time match, then the checksum is recalculated.  If it matches what's in the database then
   the file is considered okay.  If they don't match then a mismatch is reported as probably bit rot.

Frank W. Zammetti, 3/18/2023
"""


import hashlib
import json
import os
import pathlib
import sqlite3
import sys
import time


# Global variables.
g_script_directory = os.path.dirname(os.path.realpath(sys.argv[0]))
g_conn = None
g_config_data = { }
g_output_file = None
g_num_added = 0
g_num_bitrot = 0
g_num_dirs = 0
g_num_error = 0
g_num_files = 0
g_num_okay = 0
g_num_removed = 0
g_num_updated = 0
g_num_files_since_last_report = 0


def log(message, no_newline = False):
    """
    Log a regular message (will always be seen)
        Parameters:
            message (str):     A message to log
            no_newline (bool): True to NOT print a newline after the log message
    """
    if no_newline:
        print(message, end='')
    else:
        print(message)
    if g_config_data["output_to_file"]:
        # noinspection PyUnresolvedReferences
        g_output_file.write(message + "\n")


def log_verbose(message):
    """
    Log a message that should only appear when verbose mode is enabled
        Parameters:
            message (string): A message to log when verbose_output is enabled
    """
    if g_config_data["verbose_output"]:
        print(message)
        if g_config_data["output_to_file"]:
            # noinspection PyUnresolvedReferences
            g_output_file.write(message + "\n")


def read_in_config_file():
    """
    Read in the config file, abort if it doesn't exist.

    The config file is required and is in the form of JSON:

    {
      "verbose_output": true|false,
      "dirs_to_scan": [
        "C:\\DIRECTORY\\SUBDIRECTORY", ...
      ],
      "scan_subdirectories": true|false,
      "output_to_file": true|false,
      "hash_algorithm": "md5|sha1|sha224|sha256|sha384|sha512"
    }

    All elements are required.
    """

    # Make sure the config file exists, quit if not.
    absolute_path_to_config_file = os.path.join(g_script_directory, "config.json")
    if not os.path.exists(absolute_path_to_config_file):
        print("config.json file does not exist, exiting")
        quit()

    # Read in the config file.
    config_file = open(absolute_path_to_config_file)
    global g_config_data
    g_config_data = json.load(config_file)

    # If configured to log to output file, open it now.
    if g_config_data["output_to_file"]:
        # Make sure we start with no output file.
        if os.path.exists(os.path.join(g_script_directory, "output.txt")):
            os.remove(os.path.join(g_script_directory, "output.txt"))
        global g_output_file
        g_output_file = open(os.path.join(g_script_directory, "output.txt"), "a")
        g_output_file.write("Logging to output file requested and started\n\n")

    # Log the config file values for reference.
    print("config_data ... " + str(g_config_data))

    log("Config file read and processed")


def open_create_database():
    """
    Open the SQLite database, creating it if it doesn't already exist.
    """

    log_verbose("open_create_database()")

    absolute_path_to_database_file = os.path.join(g_script_directory, "database.db")
    global g_conn
    g_conn = sqlite3.connect(absolute_path_to_database_file)
    g_conn.row_factory = sqlite3.Row
    g_conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            file TEXT NOT NULL PRIMARY KEY,
            checksum TEXT NOT NULL,
            last_modified REAL
        );
    """)
    log("Database opened (or created)")


def remove_nonexistent_files_from_database():
    """
    Removes any files from the database that are not on the file system.  This must be done otherwise later if we add
    a file with a name that's already in the database then, assuming it's contents are different, it will register
    as bitrot, but that would be a false result.
    """

    global g_num_removed

    log_verbose("remove_nonexistent_files_from_database()\n")

    # noinspection PyUnresolvedReferences
    cursor = g_conn.cursor()
    cursor.execute(f"""SELECT file FROM files""")
    rows = cursor.fetchall()
    for row in rows:
        if not os.path.exists(row[0]):
            print("File " + row[0] + " in database not found on file system, removing from database")
            # noinspection PyUnresolvedReferences
            g_conn.execute(f"""DELETE FROM files WHERE file=?""", (row[0],))
            # noinspection PyUnresolvedReferences
            g_conn.commit()
            g_num_removed += 1
    cursor.close()


def calculate_checksum(absolute_path_to_file):
    """
    Calculate a checksum (hash) of a file.
        Parameters:
            absolute_path_to_file (str): The complete, absolute path to the file
        Returns:
            A string that is a checksum (hash) of the file using the configured hash algorithm
    """

    log_verbose("calculate_checksum() absolute_path_to_file ............. " + absolute_path_to_file)

    # Calculate checksum (SHA256 hash).
    with open(absolute_path_to_file, "rb") as file:
        file_bytes = file.read()
        if g_config_data["hash_algorithm"] == "md5":
            checksum = hashlib.md5(file_bytes).hexdigest()
        elif g_config_data["hash_algorithm"] == "sha1":
            checksum = hashlib.sha1(file_bytes).hexdigest()
        elif g_config_data["hash_algorithm"] == "sha224":
            checksum = hashlib.sha224(file_bytes).hexdigest()
        elif g_config_data["hash_algorithm"] == "sha256":
            checksum = hashlib.sha256(file_bytes).hexdigest()
        elif g_config_data["hash_algorithm"] == "sha384":
            checksum = hashlib.sha384(file_bytes).hexdigest()
        elif g_config_data["hash_algorithm"] == "sha512":
            checksum = hashlib.sha512(file_bytes).hexdigest()
    log_verbose("calculate_checksum() calculated checksum ............... " + checksum)
    return checksum


def get_file_from_database(absolute_path_to_file):
    """
    See if a file is in the database, and if it is, return its checksum and last modified, otherwise return an
    empty string.
        Parameters:
            absolute_path_to_file (str): The complete, absolute path to the file
        Returns:
            The checksum and last modified timestamp for the file from the database
    """

    log_verbose("get_file_from_database() absolute_path_to_file ......... " + absolute_path_to_file)

    checksum = None
    last_modified = None
    with g_conn:
        # noinspection PyUnresolvedReferences
        result_set = g_conn.execute("SELECT * FROM files WHERE file=?", (absolute_path_to_file,))
        for file_data in result_set:
            checksum = file_data["checksum"]
            last_modified = file_data["last_modified"]
            log_verbose("get_file_from_database() checksum from database ........ " + checksum)
            log_verbose("get_file_from_database() last_modified from database ... " + str(last_modified))
        return checksum, last_modified


def add_file_to_database(absolute_path_to_file, checksum, last_modified):
    """
    Add a file to the database.
        Parameters:
            absolute_path_to_file (str): The complete, absolute path to the file
            checksum (str):              The checksum of the file
            last_modified (timestamp):   The last modified date/time of the file
    """

    global g_num_added

    log_verbose("add_file_to_database() absolute_path_to_file ........... " + absolute_path_to_file)
    log_verbose("add_file_to_database() checksum ........................ " + checksum)
    log_verbose("add_file_to_database() last_modified ................... " + str(last_modified))
    log("add_file_to_database() File " + absolute_path_to_file + " is NOT in database, adding")

    # Write to database.
    # noinspection PyUnresolvedReferences,SqlResolve
    g_conn.execute(f"""
        INSERT INTO files (file, checksum, last_modified) VALUES (
            "{absolute_path_to_file}", "{checksum}", "{last_modified}"
        )
    """)
    # noinspection PyUnresolvedReferences
    g_conn.commit()
    g_num_added += 1


def update_status():
    """
    Shows a status update periodically when not in verbose mode
    """
    global g_num_files_since_last_report
    g_num_files_since_last_report += 1
    if g_num_files_since_last_report == 10:
        g_num_files_since_last_report = 0
        log("Number of files processed so far ... " + str(g_num_files))


def scan_directory(current_dir):
    """
    Scans a directory and verifies all files in it, recursively calling this function again for subdirectories
        Parameters:
            current_dir (str): The complete, absolute path of the directory
    """

    global g_num_dirs
    global g_num_files

    log_verbose("==========================================================================================" +
                "==========")
    log_verbose("Current directory ...................................... " + current_dir)

    # Set working directory, log error if not valid.
    try:
        os.chdir(current_dir)
    except FileNotFoundError:
        log("!!!!! Invalid directory !!!!!")
        return

    g_num_dirs += 1

    # Scan files in directory.
    with os.scandir(os.getcwd()) as files_in_dir:

        # Iterate list of files in the directory.
        for entry in files_in_dir:

            # If we hit a subdirectory, and we're configured to scan subdirectories, then recursively call this
            # function for that subdirectory, otherwise for a file just process it.
            if not entry.is_file():
                if g_config_data["scan_subdirectories"]:
                    scan_directory(entry.path)
                else:
                    continue

            else:

                g_num_files += 1

                update_status()

                # Pull out just filename.
                filename = entry.name
                log_verbose("--------------------------------------------------------------------------------------" +
                            "--------------")
                log_verbose("filename ............................................... " + filename)

                # Generate absolute path to file.  This is the unique key in the database.
                absolute_path_to_file = os.path.join(current_dir, filename)

                # Calculate the checksum and last modified date of the file.
                checksum = calculate_checksum(absolute_path_to_file)
                last_modified = pathlib.Path(absolute_path_to_file).stat().st_mtime

                # Get the checksum and last modified date of the file from the database, if present.
                database_checksum, database_last_modified = get_file_from_database(absolute_path_to_file)

                # If the file is NOT in the database, add it.
                if database_checksum is None and database_last_modified is None:
                    add_file_to_database(absolute_path_to_file, checksum, last_modified)
                # If file is in the database, check it.
                else:
                    check_file(
                        absolute_path_to_file, database_checksum, database_last_modified, checksum, last_modified
                    )


def check_file(absolute_path_to_file, database_checksum, database_last_modified, checksum, last_modified):
    """
        Checks a file that is already in the database.  Determines if there is bit rot or possible file system
        corruption.
        Parameters:
            absolute_path_to_file (str):        The complete, absolute path to the file
            database_checksum (str):            The checksum previously calculated for the file from the database
            database_last_modified (timestamp): The last modified date/time of the file from the database
            checksum (str):                     The checksum calculated for the file just now
            last_modified (timestamp):          The last modified date/time of the file from the file system
    """

    global g_num_bitrot
    global g_num_error
    global g_num_okay
    global g_num_updated

    log_verbose("check_file() File is in database")

    # If the last modified date matches, compare the checksums.
    if last_modified == database_last_modified:
        log_verbose("check_file() Check 1: File system last modified matches database - PASS")
        # If the checksums match, we're good.
        if database_checksum == checksum:
            log_verbose("check_file() Check 2: Calculated checksum matches database - PASS - file is okay")
            g_num_okay += 1
        # If the checksums do NOT match, it's bitrot.
        else:
            log("!!!!! CHECK 2: CHECKSUM MISMATCH ERROR FOR FILE " + absolute_path_to_file + " - BITROT !!!!!")
            g_num_bitrot += 1

    # If last modified does NOT match, there's more work to do.
    else:
        log_verbose("check_file() Check 1: File system last modified does NOT match database, comparing further")
        if last_modified > database_last_modified:
            log_verbose("check_file() Check 1: File system last modified is newer than database, updating database")
            # noinspection PyUnresolvedReferences
            g_conn.execute(f"""
                UPDATE files SET checksum=?, last_modified=? WHERE file=?
            """, (checksum, last_modified, absolute_path_to_file))
            # noinspection PyUnresolvedReferences
            g_conn.commit()
            g_num_updated += 1
        else:
            log("!!!!! CHECK 1: FILE SYSTEM LAST MODIFIED IS OLDER THAN WDATABASE FOR FILE " +
                absolute_path_to_file + " - POSSIBLE FILE SYSTEM CORRUPTION !!!!!")
            g_num_error += 1


def completion_footer(total_elapsed_time):
    """
    Print the completion footer (notification that we're done and stats from the run).
        Parameters:
            total_elapsed_time (float): How long the entire run took
    """

    log("\n********************************************* All done *********************************************\n")
    log("Number of new files added to database .................. " + str(g_num_added))
    log("Number of files removed from database .................. " + str(g_num_removed))
    log("Number of files updated in database .................... " + str(g_num_updated))
    log("Total number of directories scanned .................... " + str(g_num_dirs))
    log("Total number of files checked .......................... " + str(g_num_files))
    log("Number of okay files ................................... " + str(g_num_okay))
    log("Number of files with bitrot ............................ " + str(g_num_bitrot))
    log("Number of files with possible file system corruption ... " + str(g_num_error))
    log("Total elapsed time ..................................... " + str(round(total_elapsed_time, 2)) + "s")
    avg_per_file = 0
    if g_num_files > 0:
      avg_per_file = round(total_elapsed_time / g_num_files, 2)
    log("Average time per file .................................. " + str(avg_per_file) + "s")


# ######################################################################################################################
# ######################################################################################################################


def main():
    """
    The main function.  It all starts here!
    """

    global g_num_dirs
    global g_num_files

    print("\nFile Integrity Checker Script v1.0 by Frank W. Zammetti\n")

    start_time = time.time()

    read_in_config_file()

    log("")

    open_create_database()

    log("\nBeginning work!\n")

# TODO: Checksum the DB file, compare against two copies stored in plain text file. This ensures the DB itself doesn't
# get corrupted. Also, copy DB file if good, plus checksum files, so there is always a Last Known Good copy.

    remove_nonexistent_files_from_database()

    for current_dir in g_config_data["dirs_to_scan"]:
        scan_directory(current_dir)

    total_elapsed_time = time.time() - start_time

    completion_footer(total_elapsed_time)

    if g_config_data["output_to_file"]:
        # noinspection PyUnresolvedReferences
        g_output_file.close()

if __name__ == "__main__":
    main()