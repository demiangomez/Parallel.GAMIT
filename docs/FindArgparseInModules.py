import os
# run this from the root directory, otherwise the path names will not work
# Assume path is a directory
def readModules(path='.'):
    for entry in os.listdir(path):

        containsInit = False
        pathWithFile = path + '/__init__.py'
        # check if current directory contains __init__.py
        if os.path.isfile(pathWithFile):
            # indicate not to look any further in current directory for .py files
            containsInit = True


        fullPath = os.path.join(path, entry)
        
        # check if fullPath is directory 
        if os.path.isdir(fullPath):
            # ignore hidden files
            if not fullPath.startswith('./.'):
                # recursively read directory!
                readModules(fullPath)
        elif containsInit and fullPath.endswith('.py'):
            # do operations only if it's a python file
            
            # open file, search for "ArgumentParser"
            file = open(fullPath,'r')

            if "ArgumentParser" in file.read():
                # print(fullPath)
                name = fullPath[2:] # get rid of the ./
                name = name.replace("/", ".") # replace '/' with '.'

                pythonFileName =  ".".join(name.split(".")[-2:]) # split into list with "." as separator, then join last two
                rstName = name.removesuffix("." + pythonFileName)
                rstName = "./docs/" + rstName + ".rst"

                # print modules being cli documented to console
                print("##################")
                print("full path: " + fullPath)
                print("name: " + name)
                print("python file name: " + pythonFileName)
                print("rst file name: " + rstName)
                print("##################")


                # open corresponding sphinx rst file 
                lookFor = name[:-3] + " module"

                lines = []
                # add all lines to list
                with open(rstName, 'r+') as rstFile:
                    for line in rstFile:
                        lines.append(line)
                    # insert the sphinx_argparse_cli at the appropriate location
                    for i in range(len(lines)):
                        if(lookFor in lines[i]):
                            lines.insert(i+7, "")
                            lines.insert(i+8, "\n.. sphinx_argparse_cli::\n")
                            lines.insert(i+9, "\t:module: " + name[:-3] + "\n")
                            lines.insert(i+10, "\t:func: main\n")
                            lines.insert(i+11, "\t:hook:\n")
                            lines.insert(i+12, "\t:prog: " + pythonFileName + "\n")

                    # clear file
                    rstFile.seek(0)
                    rstFile.truncate()
                    print()
                    # write everything back into the file with new additions.
                    for i in range(len(lines)):
                        rstFile.write(lines[i])

                

directory_path = './' # path is current directory
readModules(directory_path) # call function