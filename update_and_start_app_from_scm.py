# This was a script I wrote for a project I was working on that executed this script from a GitLab CI/CD pipeline on
# every commit to start the app on my test server so the latest code was always available for testing.  This particular
# project had a Node-based back-end and a React-based client, so the basic flow is that the code was checked out from
# Subversion (a script pushed it from GitLab to SVN which, yes, I still primarily use SVN for my personal stuff, so
# shoot me!), the dependencies for the client and server would then be installed via NPM, and then each was started up
# (the client was built with Webpack, then served via the server, hence why both needed to be "started").  It's nothing
# elegant, but it served its purpose, and I learned a few Python tricks in the process (dealing with running system
processes primarily).

import os
import shutil
import subprocess
import sys
import time
import wmi

projectBaseDir = "C:\my_project"

# Clear console
os.system("cls")

# Termine ALL running Node.js processes
print ("Stopping ALL running Node.js processes (if any)...")
wmiWMI = wmi.WMI()
for process in wmiWMI.Win32_Process():
    if process.name == "node.exe":
        process.Terminate()
print("...done!");

# Update from SVN (use run() since we want to wait for the command to complete) - not sure why we can just run
# svn here but can't do the same for npm later
print("\nUpdating from SVN...")
os.chdir(f"{projectBaseDir}")
subprocess.run(["svn", "update"])
print("...done!");

# Install dependencies for client
print("\nInstalling client dependencies...")
os.chdir(f"{projectBaseDir}\client")
subprocess.run([shutil.which("npm"), "install"])
print("...done!");

# Run client (use Popen() so we don't wait for the command to complete, and need to use shutil.which() because Popen()
# doesn't look in path unless you pass shell=True, which we can't do here)
print("\nStarting client...");
os.chdir(f"{projectBaseDir}\client")
subprocess.Popen([shutil.which("npm"), "run", "build"], \
    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
print("...done!");

# Pause 30 seconds to give the build enough time to complete before we start the server
time.sleep(60)

# Install dependencies for server
print("\nInstalling server dependencies...")
os.chdir(f"{projectBaseDir}\server")
subprocess.run([shutil.which("npm"), "install"])
print("...done!");

# Run server
print("\nStarting server...");
os.chdir(f"{projectBaseDir}\server")
subprocess.Popen([shutil.which("npm"), "run", "build"], \
    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
print("...done!");

print("\nApp should now be running and available to users")

sys.exit(0)
