import c4d
import os
import json
from sys import float_info 


# Script state in the menu or the command palette
# Return True or c4d.CMD_ENABLED to enable, False or 0 to disable
# Alternatively return c4d.CMD_ENABLED|c4d.CMD_VALUE to enable and check/mark
#def state():
#    return True


CONTAINER_ORIGIN =1026473
LOCATIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),'noms_lieux.json')

# Main function
def get(doc):
    """renvoie un tuple avec le nom de la localité la plus proche 
       et la distance par rapport à l'origine
       Si le doc n'est pas géoréférencé, renvoie None
       Si le fichier json {noms_lieux : pos.x,pos.y} n'est pas trouvé
       ou pas pu ^être ouvert renvoie None"""
       
    origine = doc[CONTAINER_ORIGIN]
    if not origine : return None
    
    #lecture du fichier des lieux
    if os.path.isfile(LOCATIONS_FILE):
        with open(LOCATIONS_FILE, encoding = 'utf-8') as f:
            dico_lieux = json.load(f)
            
            dist = float_info.max
            location = None
            
            for lieu,(x,z) in dico_lieux.items():
                
                temp_dist = (c4d.Vector(x,0,z)-origine).GetLength()
                
                if dist>temp_dist:
                    location = lieu
                    dist = temp_dist
                    
            return location,dist
        
    return None
                    
                
        
            

# Execute main()
if __name__=='__main__':
    print(get(doc))