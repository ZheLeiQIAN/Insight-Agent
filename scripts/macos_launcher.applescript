set appPath to POSIX path of (path to me)
set quotedAppPath to quoted form of appPath
set projectPath to do shell script "dirname " & quotedAppPath
set quotedProjectPath to quoted form of projectPath
do shell script "cd " & quotedProjectPath & " && /usr/bin/python3 launcher_gui.py > /tmp/insight-agent-launcher.log 2>&1 &"
