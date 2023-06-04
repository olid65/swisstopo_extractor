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

        #TODO inclure les opérations GDAL/OGR dans le thread
        
        for url,fn_dst in self.lst :

            try:
                x = urllib.request.urlopen(url)
                with open(fn_dst,'wb') as saveFile:
                    saveFile.write(x.read())

                #si on a un fichier zippé on décompresse
                if fn_dst[-4:] =='.zip':
                    pth = os.path.dirname(fn_dst)
                    with ZipFile(fn_dst) as file:
                        #Pour les fichier gdb de swissbuildings v3 c'est un dossier donc il faut faire extractall
                        if fn_dst[-8:] =='.gdb.zip':
                            #DEZIPPAGE
                            with ZipFile(fn_dst, 'r') as zipObj:
                                # Extract all the contents of zip file in current directory
                                zipObj.extractall(pth)
                        else :
                            for filename in file.namelist():
                                temp_fn = file.extract(filename,pth)
                                #on renomme le fichier comme le fichier zip
                                os.rename(temp_fn, fn_dst[:-4])

                    os.remove(fn_dst)

            except Exception as e:
                print(str(e))