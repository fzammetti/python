# Randomly renames all files in the current directory and produces a map output file.

# Module imports.
from pathlib import Path
import easygui # pip install easygui
import os
import random


def main():
    # Startup message.
    print("Randomly Rename Files Script")

    prefix = easygui.enterbox("Prefix to append to beginning of filenames?")
    if prefix is None:
        print("No prefix entered, exiting")
        exit()
    print(f"prefix: {prefix}")

    # Get current working directory
    current_working_directory = os.getcwd()
    print(f"Current Working Directory: {current_working_directory}")

    # Get list of files in current working directory
    files = os.listdir(current_working_directory)

    # Iterate the entries (of type os.DirEntry) in the current working directory
    fileCount = 0
    file_string_out = ""
    with os.scandir(current_working_directory) as it:
        for entry in it:
            # noinspection PyUnresolvedReferences
            # Only process files.
            if not entry.name.startswith(".") and entry.is_file():
                # noinspection PyUnresolvedReferences
                # Get the filename.
                filename = entry.name
                # Skip this script file.
                if filename.count("Randomly Name All Files In Directory And Generate Index File Fragment.py") == 0:
                    # Ok, not the script file, let's process this file.
                    print(f"Processing file: {filename}")
                    # Generate a random filename.
                    new_filename = get_random_name(prefix, current_working_directory)
                    # Do the actual rename.
                    os.rename(
                      os.path.join(current_working_directory, filename),
                      os.path.join(current_working_directory, new_filename)
                    )
                    # Add on to output file content.
                    file_string_out += "xxxxx" + "~~" + new_filename + "~~" + filename + "\n"
                    fileCount += 1
                else:
                    print("Hit this script file, skipping")

    # Write the output file.
    print(file_string_out)
    output_file = open(os.path.join(current_working_directory, "index.txt"), "w")
    output_file.write(file_string_out)
    output_file.close()

    easygui.msgbox(f"Done, processed {fileCount} file(s)")


# Function called to get a random name.  It deals with ensuring the name is unique (in a very, very, stupid way,
# but it has the virtue of working and of being dirt-simple despite it's stupidity).  Note that the files are presumed
# to be .7z archive files, so change the code appropriately if that's not the case (it's what I needed, so it is what
# it is).
def get_random_name(in_prefix, in_current_working_directory):
    fn_len = 8 - len(in_prefix)
    codespace = "0123456789abcdefghijklmnopqrstuvwxyz"
    while True:
        random_filename = in_prefix + get_random_string(fn_len, codespace) + ".7z"
        if Path(os.path.join(in_current_working_directory, random_filename)).is_file() is False:
            return random_filename


# Function called to get a random string.  Accepts the desired length and the codespace to draw from.
def get_random_string(in_string_len, in_codespace):
    generated_name = ""
    codespace_len = len(in_codespace)
    for i in range(0, in_string_len):
        which_char = random.randint(0, codespace_len - 1)
        generated_name += in_codespace[which_char]
    return generated_name


# Kick off the festivities!
if __name__ == "__main__":
    main()
