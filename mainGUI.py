"""
Changelog
v0.2b
* Progressbar added
* Logs and prompt text format optimized

v0.1b
* First version of the tool
"""

import Tkinter
import os
import tkFileDialog
import threading
import shutil
import logging
import xml.etree.ElementTree as ET
from subprocess import call


XML_NAME_SPACE = "http://maven.apache.org/POM/4.0.0"
ET.register_namespace('', XML_NAME_SPACE)

VALID_POM_FILE = "pom.xml"
PROGRESS_BAR_WIDTH = 560


class MainGUI(Tkinter.Frame):

    def __init__(self, root):
        Tkinter.Frame.__init__(self, root, padx=20, pady=5)

        #Unable to create log file on GUI version
        #logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s', filename='branching.log', level=logging.DEBUG)

        self.continueTag = True
        self.workingDir = os.getcwd()
        self.dirList = []
        self.workerThread = None

        self.grid()

        self.chooseBtn = Tkinter.Button(self, text="Choose Dir", command=self.ask_open_dir, width=13)
        self.chooseBtn.grid(column=1, row=0)
        self.execBtn = Tkinter.Button(self, text="Start Branching", command=self.exe_branching, state=Tkinter.DISABLED, width=13)
        self.execBtn.grid(column=1, row=1)
        self.cancelBtn = Tkinter.Button(self, text="Cancel", command=self.cancel, state=Tkinter.DISABLED, width=13)
        self.cancelBtn.grid(column=1, row=2)

        self.dirListBox = Tkinter.Listbox(self, selectmode=Tkinter.EXTENDED, width=48, height=10)
        dirlistb_yscroll = Tkinter.Scrollbar(self, orient=Tkinter.VERTICAL)
        self.dirListBox['yscrollcommand'] = dirlistb_yscroll.set
        self.dirListBox.grid(column=0, row=0, rowspan=3, sticky=Tkinter.W, pady=5)
        dirlistb_yscroll.grid(row=0, column=0, sticky=Tkinter.E+Tkinter.N+Tkinter.S, rowspan=3, padx=23, pady=6)
        self.dirListBox.insert(Tkinter.END, "  To start, please use 'Choose Dir' to select the")
        self.dirListBox.insert(Tkinter.END, "  directory which contains all of the projects =====>")

        self.releaseVersionLabel = Tkinter.Label(self, text="Release version")
        self.releaseVersionLabel.grid(column=0, row=3, columnspan=2, sticky=Tkinter.W)
        self.releaseVersionEntry = Tkinter.Entry(self, width=10)
        self.releaseVersionEntry.place(x=100, y=180)

        self.releaseSuffixLable = Tkinter.Label(self, text="Version suffix")
        self.releaseSuffixLable.place(x=195, y=182)
        self.releaseSuffixEntry = Tkinter.Entry(self, width=15)
        self.releaseSuffixEntry.place(x=280, y=180)
        self.releaseSuffixEntry.insert(0, "-SNAPSHOT")

        self.logListBox = Tkinter.Listbox(self, selectmode=Tkinter.BROWSE, width=70, height=10)
        dirlogb_yscroll = Tkinter.Scrollbar(self, orient=Tkinter.VERTICAL)
        self.logListBox['yscrollcommand'] = dirlogb_yscroll.set
        self.logListBox.grid(column=0, row=4, columnspan=2, pady=5)
        dirlogb_yscroll.grid(column=1, row=4, sticky=Tkinter.E+Tkinter.N+Tkinter.S, padx=1, pady=6)

        self.progressBar = Tkinter.Canvas(width=PROGRESS_BAR_WIDTH, height=30, bd=0)
        self.progressBar.grid(column=0, row=5, padx=17, sticky=Tkinter.W)

        self.dir_opt = options = {}
        options['initialdir'] = os.getcwd()
        options['title'] = 'Select the working directory'

    def ask_open_dir(self):
        self.workingDir = tkFileDialog.askdirectory(**self.dir_opt)

        self.dirList = []
        for dir in os.listdir(self.workingDir):
            if not dir.startswith('.') and os.path.isdir(os.path.join(self.workingDir, dir)):
                self.dirList.append(dir)

        self.dirListBox.delete(0, Tkinter.END)

        if len(self.dirList) > 0:
            found_pom = False
            for item in self.dirList:
                for fil in os.listdir(os.path.join(self.workingDir, item)):
                    if fil.endswith(VALID_POM_FILE):
                        found_pom = True
                        break

                if found_pom:
                    self.dirListBox.insert(Tkinter.END, item)

        if self.dirListBox.size() == 0:
            self.dirListBox.insert(Tkinter.END, "Can't find any valid Maven project!")
            self.execBtn['state'] = Tkinter.DISABLED
        else:
            self.execBtn['state'] = Tkinter.ACTIVE

    def exe_branching(self):
        selected_idx = self.dirListBox.curselection()
        if not selected_idx:
            self.logListBox.insert(0, "Please select at least one directory to move on!")
            return

        release_version = self.releaseVersionEntry.get()
        if not release_version:
            self.logListBox.insert(0, "Please fill in the release version!")
            return

        rpm_version = release_version + self.releaseSuffixEntry.get()

        self.chooseBtn['state'] = Tkinter.DISABLED
        self.execBtn['state'] = Tkinter.DISABLED
        self.cancelBtn['state'] = Tkinter.ACTIVE

        self.workerThread = WorkerThread(self.workingDir, selected_idx, self.dirList, self.logListBox, self.chooseBtn,
                                         self.execBtn, self.cancelBtn, self.progressBar, release_version, rpm_version)
        self.workerThread.start()

    def cancel(self):
        self.workerThread.cancel_task()


class CommentParser(ET.TreeBuilder):
    def comment(self, data):
        self.start(ET.Comment, {})
        self.data(data)
        self.end(ET.Comment)


class WorkerThread(threading.Thread):

    def __init__(self, working_dir=os.getcwd(), selected_idx=[], available_dirs=[], log_list_box=None,
                 choose_dir_btn=None, exec_btn=None, cancel_btn=None, progress_bar=None, release_version='', rpm_version=''):
        threading.Thread.__init__(self)

        self.workingDir = working_dir
        self.selectedIdx = selected_idx
        self.availableDirs = available_dirs
        self.logListBox = log_list_box
        self.continueTag = True
        self.chooseDirBtn = choose_dir_btn
        self.execBtn = exec_btn
        self.cancelBtn = cancel_btn
        self.progress_bar = progress_bar
        self.releaseVersion = release_version
        self.rpmVersion = rpm_version

    def run(self):
        total_files = 0
        current_progress = 0
        tmp_bar = None
        self.progress_bar.delete(Tkinter.ALL)

        for idx in self.selectedIdx:
            project = os.path.join(self.workingDir, self.availableDirs[idx])
            for currentDir, subDirs, files in os.walk(project):
                for fil in files:
                    if (fil == "pom.xml" or fil == "reporting-aggregator-pom.xml") and ("bin" not in currentDir and "target" not in currentDir):
                        total_files += 1

        self.logListBox.insert(0, "Found {} pom files in {} projects!".format(total_files, len(self.selectedIdx)))

        for idx in self.selectedIdx:
            if self.continueTag:
                project = os.path.join(self.workingDir, self.availableDirs[idx])

                try:
                    for currentDir, subDirs, files in os.walk(project):
                        for fil in files:
                            if (fil == "pom.xml" or fil == "reporting-aggregator-pom.xml") and ("bin" not in currentDir and "target" not in currentDir):
                                current_progress += PROGRESS_BAR_WIDTH * float(1) / total_files
                                self.progress_bar.delete(tmp_bar)
                                tmp_bar = self.progress_bar.create_rectangle(0, 0, current_progress, 25, fill="blue", outline="blue")

                                pom_file = os.path.join(currentDir, fil)

                                logging.info("Processing {} ...".format(pom_file))

                                # backup original files
                                shutil.copyfile(pom_file, pom_file + '.branchbak')

                                tree = ET.parse(pom_file, parser=ET.XMLParser(target=CommentParser()))

                                root_xml = tree.getroot()

                                parent_tag = root_xml.find("{" + XML_NAME_SPACE + "}parent")
                                parent_artifact_tag = parent_tag.find("{" + XML_NAME_SPACE + "}artifactId")
                                if parent_artifact_tag.text != "angel-parent-pom":
                                    parent_version_tag = parent_tag.find("{" + XML_NAME_SPACE + "}version")
                                    parent_version_tag.text = self.rpmVersion

                                version_tag = root_xml.find("{" + XML_NAME_SPACE + "}version")
                                if version_tag is not None:
                                    version_tag.text = self.rpmVersion

                                if version_tag is None and parent_version_tag is None:
                                    logging.error("ERROR: Can't find <version> tag on pom.xml, please double check the file! Skipping...")
                                else:
                                    tree.write(pom_file, encoding="UTF-8")
                                    logging.info("Done!")

                    os.chdir(project)
                    call(["/usr/local/bin/hg", "branch", self.releaseVersion])
                except OSError as e:
                    if e.errno == 2:
                        logging.error(e)
                    else:
                        logging.error("Error processing project {}, error code {}. Skipping...".format(project, e.errno))
                except Exception as e:
                    logging.error(e)
                finally:
                    os.chdir(self.workingDir)

                self.logListBox.insert(0, "")
                self.logListBox.insert(0, "Branch {} cut with RPM version {}. Please verify the changes on the local before check in!".format(self.releaseVersion, self.rpmVersion))
                self.logListBox.insert(0, "{}:".format(project))
            else:
                break

        self.chooseDirBtn['state'] = Tkinter.ACTIVE
        self.execBtn['state'] = Tkinter.ACTIVE
        self.cancelBtn['state'] = Tkinter.DISABLED

        if not self.continueTag:
            self.logListBox.insert(0, "User abort!")

    def cancel_task(self):
        self.continueTag = False

if __name__ == '__main__':
    root = Tkinter.Tk()
    root.title("Branching Tool v0.2b")
    root.resizable(0, 0)
    MainGUI(root)
    root.mainloop()
