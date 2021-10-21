import c4d,os
import urllib.request
from zipfile import ZipFile
import csv


# Script state in the menu or the command palette
# Return True or c4d.CMD_ENABLED to enable, False or 0 to disable
# Alternatively return c4d.CMD_ENABLED|c4d.CMD_VALUE to enable and check/mark
#def state():
#    return True

class ThreadDownload(c4d.threading.C4DThread):

    def __init__(self,lst):
        self.lst = lst

    def Main(self):

        for url,fn_dst in self.lst :

            try:
                x = urllib.request.urlopen(url)

                #print(x.read())

                with open(fn_dst,'wb') as saveFile:
                    saveFile.write(x.read())

                #si on a un fichier zippé on décompresse
                if fn_dst[-4:] =='.zip':
                    zfobj = ZipFile(fn_dst)
                    for name in zfobj.namelist():
                        uncompressed = zfobj.read(name)
                        # save uncompressed data to disk
                        outputFilename = fn_dst[:-4]
                        with open(outputFilename,'wb') as output:
                            output.write(uncompressed)
                    os.remove(fn_dst)

            except Exception as e:
                print(str(e))