# Archives all files in the current directory.  Produced archives are maximally compressed and password-encrypted.
# Resultant archives are placed in an archives folder.  This requires 7-zip be installed in the default location on
# a Windows system (sorry, *nix bois!)

# Module imports.
import easygui # pip install easygui
import os
import subprocess

# Startup message.
print("Archive Processing Script")

password = easygui.enterbox("Password?")
if password is None:
    print("No password entered, exiting")
    exit()
print(f"Password: {password}")

# Get current working directory
currentWorkingDirectory = os.getcwd()
print(f"Current Working Directory: {currentWorkingDirectory}")

# Create the archives directory
archivesDirectory = os.path.join(currentWorkingDirectory, "archives")
try:
    os.mkdir(archivesDirectory)
    print("archives directory created")
except OSError as error:
    print("archives directory already exists")

# Get list of files in current working directory
files = os.listdir(currentWorkingDirectory)

print("------------------------------------------------------------------------------")

# Iterate the entries (of type os.DirEntry) in the current working directory
fileCount = 0
with os.scandir(currentWorkingDirectory) as it:
    for entry in it:
        # noinspection PyUnresolvedReferences
        # Only process files.
        if not entry.name.startswith(".") and entry.is_file():
            # noinspection PyUnresolvedReferences
            # Get the filename.
            filename = entry.name
            # Get the filename without the extension.
            filenameSansExtension = os.path.splitext(filename)[0]
            # Skip this script file.
            if filename.count("Archive Processing Script.py") == 0:
                # Ok, not the script file, let's process this file.
                print(f"Processing file: {filename}")
                # Construct command to execute.
                cmd = "C:\\Program Files\\7-Zip\\7z.exe "
                cmd += "a -t7z -r -m0=lzma2 -mx9 -mfb=64 -md=64m -ms=on -mmt=2 -mhe=on "
                cmd += f"-p{password} \"archives\\{filenameSansExtension}.7z\" \"{filename}\""
                print(f"cmd: {cmd}")
                # Call out to 7-zip to archive the file.
                subprocess.call(cmd)
                fileCount += 1
            else:
                print("Hit this script file, skipping")

easygui.msgbox(f"Done, processed {fileCount} file(s)")
