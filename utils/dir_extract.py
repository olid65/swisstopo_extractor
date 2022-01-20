import c4d
import os


# Script state in the menu or the command palette
# Return True or c4d.CMD_ENABLED to enable, False or 0 to disable
# Alternatively return c4d.CMD_ENABLED|c4d.CMD_VALUE to enable and check/mark
#def state():
#    return True

NAME_DIR = 'swisstopo_extraction'

NOT_SAVED_TXT = (f"Le document doit être enregistré pour pouvoir créer un dossier {NAME_DIR}, "
                 "vous pourrez le faire à la prochaine étape\n"
                 "Voulez-vous continuer ?")


TXT_NO_WRITE_PERMISSION = ( "Vous n'avez pas les droits en écriture dans le dossier "
                            "vous pourrez choisir un dossier à la prochaine étape\n"
                            "Voulez-vous continuer ?")
                            

# Main function
def create(doc):
    
    pth = doc.GetDocumentPath()
    if not pth:
        rep = c4d.gui.QuestionDialog(NOT_SAVED_TXT)
        if not rep : return None
        #c4d.documents.SaveDocument(doc, "", c4d.SAVEDOCUMENTFLAGS_DIALOGSALLOWED, c4d.FORMAT_C4DEXPORT)
        c4d.CallCommand(12098) # Enregistrer le projet
    pth = doc.GetDocumentPath()
    if not pth : return None

    pth_dir_extract = None
    
    #On check si on a les droits en écriture dans le dossier
    if not os.access(pth, os.W_OK):
        rep = c4d.gui.QuestionDialog(TXT_NO_WRITE_PERMISSION)
        if not rep : return None
        
        pth_dir_extract = c4d.storage.LoadDialog(flags=c4d.FILESELECT_DIRECTORY)
        if not pth_dir_extract : return None
        
        # quand l'utilisateur a choisi un dossier 
        # on vérifiie les droits en écriture'
        while not os.access(pth_dir_extract, os.W_OK):
            rep = c4d.gui.QuestionDialog(TXT_NO_WRITE_PERMISSION)
            if not rep : return
            pth_dir_extract = c4d.storage.LoadDialog(flags=c4d.FILESELECT_DIRECTORY)
            if not pth_dir_extract : return None            
        
    if not pth_dir_extract:
        pth_dir_extract = os.path.join(pth,NAME_DIR)
    
    if not os.path.isdir(pth_dir_extract):
        os.mkdir(pth_dir_extract)
        
    return pth_dir_extract
    
    

# Execute main()
if __name__=='__main__':
    main(doc)