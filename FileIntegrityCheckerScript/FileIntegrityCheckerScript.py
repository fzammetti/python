#!/usr/bin/env python


from datetime import timedelta
import hashlib
import json
import os
import pathlib
import shutil
import sqlite3
import sys
import time
import xxhash


# Global variables.
g_script_directory = os.path.dirname(os.path.realpath(sys.argv[0]))
g_absolute_path_to_database_file = os.path.join(g_script_directory, "database.db")
g_conn = None
g_config_data = {}
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
g_total_files_to_scan = 0


# ----------------------------------------------------------------------------------------------------------------------
# --------------------------------------------- Main Operational Functions ---------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


def read_in_config_file():
    """
    Read in the config file, abort if it doesn't exist.
    """

    # Make sure the config file exists, quit if not.
    absolute_path_to_config_file = os.path.join(g_script_directory, "config.json")
    if not os.path.exists(absolute_path_to_config_file):
        print("!!!!! CONFIG.JSON FILE DOES NOT EXIST, ABORTING")
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
        g_output_file.write("Logging to output file requested and started\n")

    # Log the config file values for reference.
    log_verbose("config_data ... " + str(g_config_data))


def open_create_database():
    """
    Open the SQLite database, creating it if it doesn't already exist.
    """

    global g_conn
    g_conn = sqlite3.connect(g_absolute_path_to_database_file)
    g_conn.row_factory = sqlite3.Row
    g_conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            file TEXT NOT NULL PRIMARY KEY,
            checksum TEXT NOT NULL,
            last_modified REAL
        );
    """)


def validate_database():
    """
    Validates the database, NASA space shuttle-style: two checksum files are compared to a real-time checksum
    calculation and if they don't match, we abort the whole show.  This function also handles the case where the
    database was just created, in which case there will be no checksum files yet, so they will be created.
    """
    absolute_path_to_db_checksum_1_file = os.path.join(g_script_directory, "db_checksum_1.md5")
    absolute_path_to_db_checksum_2_file = os.path.join(g_script_directory, "db_checksum_2.md5")
    # If both files do not exist, that should mean the database was just created, so checksum it now, which will
    # create the two checksum files.
    if not os.path.exists(absolute_path_to_db_checksum_1_file) and \
            not os.path.exists(absolute_path_to_db_checksum_2_file):
        checksum_database()
    # Read in the two checksum files.
    with open(absolute_path_to_db_checksum_1_file) as f:
        checksum_1 = f.readlines()[0]
        f.close()
    log_verbose("DB file checksum 1 ................... " + str(checksum_1))
    with open(absolute_path_to_db_checksum_2_file) as f:
        checksum_2 = f.readlines()[0]
        f.close()
    log_verbose("DB file checksum 2 ................... " + str(checksum_2))
    # Calculate the database file's current checksum and make sure they all match, abort if not.
    realtime_checksum = calculate_checksum(g_absolute_path_to_database_file)
    log_verbose("Realtime checksum .................... " + str(realtime_checksum))
    if realtime_checksum == checksum_1 and realtime_checksum == checksum_2:
        # Make a copy of the database file.
        shutil.copyfile(g_absolute_path_to_database_file, os.path.join(g_script_directory, "database.db.backup"))
    else:
        print("!!!!! DATABASE.DB IS CORRUPT, ABORTING")
        quit()


def checksum_database():
    """
    Calculates a checksum for the database file and writes two copies to two separate files for later validation.
    """
    db_checksum = calculate_checksum(g_absolute_path_to_database_file)
    with open(os.path.join(g_script_directory, "db_checksum_1.md5"), "w") as f:
        f.write(db_checksum)
        f.close()
    with open(os.path.join(g_script_directory, "db_checksum_2.md5"), "w") as f:
        f.write(db_checksum)
        f.close()


def remove_nonexistent_files_from_database():
    """
    Removes any files from the database that are not on the file system.  This must be done otherwise later if we add
    a file with a name that's already in the database then, assuming it's contents are different, it will register
    as bit rot, but that would be a false result.
    """

    global g_num_removed

    # noinspection PyUnresolvedReferences
    cursor = g_conn.cursor()
    cursor.execute(f"""SELECT file FROM files""")
    rows = cursor.fetchall()

    number_checked = 0
    for row in rows:
        number_checked += 1
        # Print a status update every 5,000 files checked.  This seems to be a good compromise on an average system
        # between updating too frequently and appearing to be stuck due to no update.
        if number_checked % 5000 == 0:
            log("Files checked so far: " + str(number_checked))
        if not os.path.exists(row[0]):
            log("File " + row[0] + " in DB not found on FS, removing from DB")
            # noinspection PyUnresolvedReferences
            g_conn.execute(f"""DELETE FROM files WHERE file=?""", (row[0],))
            # noinspection PyUnresolvedReferences
            g_conn.commit()
            g_num_removed += 1
    cursor.close()


def scan_directory(path, scan_subdirectories, allow_file_changes):
    """
    Scans a directory and verifies all files in it, recursively calling this function again for subdirectories.
        Parameters:
            path (str):                 The complete, absolute path of the directory.
            scan_subdirectories (bool): True to scan subdirectories, false to skip them.
            allow_file_changes (bool):  True if files are allowed to change, false if not.
    """

    global g_num_dirs
    global g_num_files

    log_verbose("\n==========================================================================================" +
                "==========")
    log_verbose("\nCurrent directory: " + path + "\n")

    # Set working directory, log error if not valid.
    try:
        os.chdir(path)
    except FileNotFoundError:
        log("!!!!! INVALID DIRECTORY")
        return

    g_num_dirs += 1

    # Scan files in directory.
    with os.scandir(os.getcwd()) as files_in_dir:

        # Iterate list of files in the directory.
        for entry in files_in_dir:

            # If we hit a subdirectory, and we're configured to scan subdirectories, then recursively call this
            # function for that subdirectory, otherwise for a file just process it.
            if not entry.is_file():
                if scan_subdirectories:
                    scan_directory(entry.path, scan_subdirectories, allow_file_changes)
                else:
                    continue

            else:

                file_start_time = time.time()

                g_num_files += 1

                update_status()

                # Pull out the filename and generate absolute path to file.  This is the unique key in the database.
                filename = entry.name
                absolute_path_to_file = os.path.join(path, filename)

                log_verbose("--------------------------------------------------------------------------------------" +
                            "--------------")
                log_verbose("File number .......................... " + str(g_num_files) + " of " +
                            str(g_total_files_to_scan))
                log_verbose("Filename ............................. " + filename)
                log_verbose("File size ............................ " +
                            str(convert_file_size_bytes(os.path.getsize(absolute_path_to_file))))

                # Calculate the checksum and last modified date of the file off the file system.  Note that the
                # last_modified value must be rounded or else we'll lose precision when saved to SQLite (since it
                # only guarantees 15 digits of precision), which results in false reports of possible file system
                # corruption.
                checksum = calculate_checksum(absolute_path_to_file)
                last_modified = round(pathlib.Path(absolute_path_to_file).stat().st_mtime, 5)
                log_verbose("Last modified from FS ................ " + str(last_modified))

                # Get the checksum and last modified date of the file from the database, if present.
                database_checksum, database_last_modified = get_file_from_database(absolute_path_to_file)

                # If the file is NOT in the database, add it.
                if database_checksum is None and database_last_modified is None:
                    add_file_to_database(absolute_path_to_file, checksum, last_modified)
                # If file is in the database, check it.
                else:
                    check_file(
                        absolute_path_to_file, database_checksum, database_last_modified, checksum, last_modified,
                        allow_file_changes
                    )

                log_verbose("Time taken for this file ............. " +
                            str(timedelta(seconds = time.time() - file_start_time)))


def check_file(absolute_path_to_file, database_checksum, database_last_modified, checksum, last_modified,
               allow_file_changes
               ):
    """
        Checks a file that is already in the database.  Determines if there is bit rot or possible file system
        corruption.
        Parameters:
            absolute_path_to_file (str):        The complete, absolute path to the file.
            database_checksum (str):            The checksum previously calculated for the file from the database.
            database_last_modified (timestamp): The last modified date/time of the file from the database.
            checksum (str):                     The checksum calculated for the file just now.
            last_modified (timestamp):          The last modified date/time of the file from the file system.
            allow_file_changes (bool):          True if files are allowed to change, false if not.
    """

    global g_num_bitrot
    global g_num_error
    global g_num_okay
    global g_num_updated

    # File changes ARE allowed, which means we have to do the full check procedure.
    if allow_file_changes:

        # If the last modified date matches, compare the checksums.
        if last_modified == database_last_modified:
            log_verbose("Chk 1: FS last modified matches DB ... PASS")
            # If the checksums match, we're good.
            if database_checksum == checksum:
                log_verbose("Chk 2: Checksum matches DB ........... PASS")
                log_verbose("File is okay")
                g_num_okay += 1
            # If the checksums do NOT match, it's bit rot.
            else:
                log("!!!!! CHECKSUM MISMATCH ERROR (BIT ROT): " + absolute_path_to_file)
                g_num_bitrot += 1

        # If last modified does NOT match, there's more work to do.
        else:
            log_verbose("FS last modified does NOT match database, comparing further")
            if last_modified > database_last_modified:
                log_verbose("FS last modified is newer than database, updating database")
                # noinspection PyUnresolvedReferences
                g_conn.execute(f"""
                    UPDATE files SET checksum=?, last_modified=? WHERE file=?
                """, (checksum, last_modified, absolute_path_to_file))
                # noinspection PyUnresolvedReferences
                g_conn.commit()
                g_num_updated += 1
            else:
                log("!!!!! FS LAST MODIFIED IS OLDER THAN DB (POSSIBLE FS CORRUPTION): " + absolute_path_to_file)
                g_num_error += 1

    # Files changes are NOT allowed, which means we really only care about the checksum: if the file system matches
    # the database then we're good to go (but we still need to check for possible file system corruption and update the
    # last modified time in the database), otherwise it's bit rot (and we DO NOT update the database at all in
    # that case).
    else:

        if database_checksum == checksum:
            log_verbose("Chk 1: Checksum matches DB ........... PASS")
            if last_modified == database_last_modified:
                log_verbose("Chk 2: FS last modified matches DB ... PASS")
                log_verbose("File is okay")
                g_num_okay += 1
            else:
                log("!!!!! FS LAST MODIFIED DIFFERS FROM DB (POSSIBLE FS CORRUPTION): " + absolute_path_to_file)
                g_num_error += 1
        # If the checksums do NOT match, it's bit rot.
        else:
            log("!!!!! CHECKSUM MISMATCH ERROR (BIT ROT): " + absolute_path_to_file)
            g_num_bitrot += 1


def get_file_from_database(absolute_path_to_file):
    """
    See if a file is in the database, and if it is, return its checksum and last modified, otherwise return an
    empty string.
        Parameters:
            absolute_path_to_file (str): The complete, absolute path to the file.
        Returns:
            The checksum and last modified timestamp for the file from the database.
    """

    checksum = None
    last_modified = None
    with g_conn:
        # noinspection PyUnresolvedReferences
        result_set = g_conn.execute("SELECT * FROM files WHERE file=?", (absolute_path_to_file,))
        for file_data in result_set:
            checksum = file_data["checksum"]
            last_modified = file_data["last_modified"]
            log_verbose("Checksum from DB ..................... " + checksum)
            log_verbose("Last modified from DB ................ " + str(last_modified))
        return checksum, last_modified


def add_file_to_database(absolute_path_to_file, checksum, last_modified):
    """
    Add a file to the database.
        Parameters:
            absolute_path_to_file (str): The complete, absolute path to the file.
            checksum (str):              The checksum of the file.
            last_modified (timestamp):   The last modified date/time of the file.
    """

    global g_num_added

    log("File " + absolute_path_to_file + " is NOT in DB, adding")

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
    Shows a status update periodically when not in verbose mode.
    """
    global g_num_files_since_last_report
    g_num_files_since_last_report += 1
    if g_num_files_since_last_report == 10:
        g_num_files_since_last_report = 0
        log("Number of files processed so far: " + str(g_num_files) + " of " + str(g_total_files_to_scan))


def override_statuses():
    """
    This function is called when the override_status element is present in the config file.  The purpose is to
    recalculate the checksum for a file and update it in the database (along with the last modified information).
    This is used when the user determines that a file that had previously registered as having bit rot either hasn't,
    in fact, become corrupt, or else it was restored to a good state, in which case the database needs to be updated
    or else it'll continue to register as bit rot.
    """
    for file_to_update in g_config_data["override_status"]:
        checksum = calculate_checksum(file_to_update)
        last_modified = round(pathlib.Path(file_to_update).stat().st_mtime, 5)
        log("Updating " + file_to_update + " with checksum " + checksum + " and last modified " + str(last_modified))
        # noinspection PyUnresolvedReferences
        g_conn.execute(f"""
            UPDATE files SET checksum=?, last_modified=? WHERE file=?
        """, (checksum, last_modified, file_to_update))
        # noinspection PyUnresolvedReferences
        g_conn.commit()


def completion_footer(total_elapsed_time):
    """
    Print the completion footer (notification that we're done and stats from the run).
        Parameters:
            total_elapsed_time (float): How long the entire run took.
    """

    log("\n********************************************* All done *********************************************\n")
    if "override_status" not in g_config_data:
        log("End time ...................................... " + time.ctime())
        log("Number of new files added to DB ............... " + str(g_num_added))
        log("Number of files removed from DB ............... " + str(g_num_removed))
        log("Number of files updated in DB ................. " + str(g_num_updated))
        log("Total number of directories scanned ........... " + str(g_num_dirs))
        log("Total number of files checked ................. " + str(g_num_files))
        log("Number of okay files .......................... " + str(g_num_okay))
        log("Number of files with bit rot .................. " + str(g_num_bitrot))
        log("Number of files with possible FS corruption ... " + str(g_num_error))
        log("Total elapsed time ............................ " + str(timedelta(seconds = total_elapsed_time)))
        avg_per_file = 0
        if g_num_files > 0:
            avg_per_file = round(total_elapsed_time / g_num_files, 2)
        log("Average time per file ......................... " + str(timedelta(seconds = avg_per_file)))


# ----------------------------------------------------------------------------------------------------------------------
# -------------------------------------------------- Utility Functions -------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


def log(message, no_newline = False):
    """
    Log a regular message (will always be seen).
        Parameters:
            message (str):     A message to log.
            no_newline (bool): True to NOT print a newline after the log message.
    """
    if no_newline:
        print(message, end = '')
    else:
        print(message)
    if g_config_data["output_to_file"]:
        # noinspection PyUnresolvedReferences
        g_output_file.write(message + "\n")


def log_verbose(message):
    """
    Log a message that should only appear when verbose mode is enabled.
        Parameters:
            message (string): A message to log when verbose_output is enabled.
    """
    if g_config_data["verbose_output"]:
        print(message)
        if g_config_data["output_to_file"]:
            # noinspection PyUnresolvedReferences
            g_output_file.write(message + "\n")


def calculate_checksum(absolute_path_to_file):
    """
    Calculate a checksum (hash) of a file.
        Parameters:
            absolute_path_to_file (str): The complete, absolute path to the file.
        Returns:
            A string that is a checksum (hash) of the file using the configured checksum (hash) algorithm.
    """

    with open(absolute_path_to_file, "rb") as file:
        file_bytes = file.read()
        if g_config_data["checksum_algorithm"] == "md5":
            checksum = hashlib.md5(file_bytes).hexdigest()
        elif g_config_data["checksum_algorithm"] == "sha1":
            checksum = hashlib.sha1(file_bytes).hexdigest()
        elif g_config_data["checksum_algorithm"] == "sha224":
            checksum = hashlib.sha224(file_bytes).hexdigest()
        elif g_config_data["checksum_algorithm"] == "sha256":
            checksum = hashlib.sha256(file_bytes).hexdigest()
        elif g_config_data["checksum_algorithm"] == "sha384":
            checksum = hashlib.sha384(file_bytes).hexdigest()
        elif g_config_data["checksum_algorithm"] == "sha512":
            checksum = hashlib.sha512(file_bytes).hexdigest()
        elif g_config_data["checksum_algorithm"] == "xxhash":
            checksum = xxhash.xxh64(file_bytes).hexdigest()
    log_verbose("Calculated checksum .................. " + checksum)
    return checksum


def convert_file_size_bytes(size):
    """
    Convert the length of a file in bytes to KB, MB, GB or TB (or bytes if not more than 1KB).
        Parameters:
            size (int): The file size in bytes.
        Returns:
            The file size expressed in bytes, KB, MB, GB or TB.
    """
    for unit in ["bytes", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return "%3.1f %s" % (size, unit)
        size /= 1024.0


def count_files_in_directory(directory, scan_subdirectories):
    """
    Counts the number of files in a directory, and optionally all of its subdirectories too.
        Parameters:
            directory (string)            The directory to scan.
            scan_subdirectories (boolean) True to scan subdirectories as well, false if not.
        Returns:
            The number of files.
    """
    count = 0
    if scan_subdirectories:
        for root_dir, cur_dir, files in os.walk(directory):
            count += len(files)
    else:
        for path in os.listdir(directory):
            if os.path.isfile(os.path.join(directory, path)):
                count += 1
    return count


# ######################################################################################################################
# ######################################################################################################################
# ######################################################################################################################


def main():
    """
    The main function.  It all starts here!
    """

    global g_num_dirs
    global g_num_files
    global g_total_files_to_scan

    print("\nFile Integrity Checker Script v1.0 by Frank W. Zammetti")
    print("\nStart time: " + time.ctime())

    print("\nReading config file...")
    read_in_config_file()
    log("...Done")

    log("\nOpening (or creating) DB...")
    open_create_database()
    log("...Done")

    log("\nValidating DB...")
    validate_database()
    log("...Done")

    log("\n****************************************** Beginning Work ******************************************")

    start_time = time.time()

    # If there's an override_status key in the config file then we're just going to update the specified files.
    if "override_status" in g_config_data:

        log("\nOverriding statuses...")
        override_statuses()
        log("...Done")

    else:

        log("\nRemoving non-existent files from DB...")
        remove_nonexistent_files_from_database()
        log("...Done")

        log("\nCounting files to verify...")
        for current_dir in g_config_data["directories_to_scan"]:
            g_total_files_to_scan += count_files_in_directory(current_dir["path"], current_dir["scan_subdirectories"])
        log("...Done (" + str(g_total_files_to_scan) + ")")

        log("\nVerifying files...")
        for current_dir in g_config_data["directories_to_scan"]:
            scan_directory(current_dir["path"], current_dir["scan_subdirectories"], current_dir["allow_file_changes"])
        log("...Done")

    # Recalculate and record the checksum for the database file to account for any changes during this run.
    log("\nChecksumming database...")
    checksum_database()
    log("...Done")

    # We're all done, calculate how long the whole thing took.
    total_elapsed_time = time.time() - start_time

    # Display completion footer.
    completion_footer(total_elapsed_time)

    # Cleanup.
    if g_config_data["output_to_file"]:
        # noinspection PyUnresolvedReferences
        g_output_file.close()


if __name__ == "__main__":
    main()
