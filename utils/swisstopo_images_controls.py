"""Interface pour les collections et la recherche des couches."""
import json
import threading
import urllib.parse
import c4d
from utils.swisstopo_images_catalogue import (CACHE, COLLECTIONS, fetch_catalogue, load_collections,
                                     parse_url, save_json, search)


class LayerRow(c4d.gui.GeUserArea):
    """Ligne dessinée explicitement pour un surlignage indépendant du thème."""
    def __init__(self, owner, index, row):
        super().__init__()
        self.owner, self.index, self.row = owner, index, row

    def GetMinSize(self):
        return 280, 24

    def DrawMsg(self, x1, y1, x2, y2, msg):
        self.OffScreenOn()
        self.SetClippingRegion(x1, y1, x2, y2)
        selected = self.owner.preview_layer == self.row['layer']
        background = c4d.Vector(1.0, 0.43, 0.06) if selected else c4d.COLOR_BG
        foreground = c4d.Vector(0.08) if selected else c4d.COLOR_TEXT
        self.DrawSetPen(background)
        self.DrawRectangle(0, 0, self.GetWidth()-1, self.GetHeight()-1)
        self.DrawSetTextCol(foreground, background)
        self.DrawText(self.row['name'], 8, 4)

    def InputEvent(self, msg):
        if msg[c4d.BFM_INPUT_DEVICE] == c4d.BFM_INPUT_MOUSE and msg[c4d.BFM_INPUT_CHANNEL] == c4d.BFM_INPUT_MOUSELEFT:
            self.owner.handle_command(50000+self.index, msg)
            return True
        return False


class LayerPicker(c4d.gui.GeDialog):
    PAGE_SIZE = 25

    def __init__(self, owner, mode):
        super().__init__()
        self.owner, self.mode = owner, mode
        self.rows = owner.catalogue
        self.selected = set()
        self.page = 0
        self.visible = []
        self.job = None
        self.result = None

    def CreateLayout(self):
        self.SetTitle('Rechercher des couches swisstopo')
        self.GroupBegin(1, c4d.BFH_SCALEFIT, cols=1)
        self.GroupBorderSpace(12, 12, 12, 12)
        self.AddStaticText(0, c4d.BFH_LEFT, name='Recherche : nom, identifiant ou organisme')
        self.AddEditText(10, c4d.BFH_SCALEFIT, initw=650)
        self.GroupBegin(2, c4d.BFH_SCALEFIT, cols=2)
        self.AddComboBox(11, c4d.BFH_SCALEFIT)
        for i, label in enumerate(('Nom A–Z', 'Identifiant', 'Organisme'), 1):
            self.AddChild(11, i, label)
        self.AddButton(12, c4d.BFH_LEFT, name='Actualiser le catalogue')
        self.GroupEnd()
        self.AddStaticText(13, c4d.BFH_SCALEFIT, name=' ')
        self.ScrollGroupBegin(14, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
                              c4d.SCROLLGROUP_VERT, initw=700, inith=350)
        self.GroupBegin(15, c4d.BFH_SCALEFIT | c4d.BFV_TOP, cols=1)
        self.GroupEnd()
        self.GroupEnd()
        self.GroupBegin(16, c4d.BFH_CENTER, cols=4)
        for i, label in ((17, 'Précédent'), (18, 'Suivant'), (19, 'Cocher la page'), (20, 'Tout décocher')):
            self.AddButton(i, c4d.BFH_LEFT, name=label)
        self.GroupEnd()
        self.AddButton(21, c4d.BFH_CENTER, name='Ajouter les couches sélectionnées')
        self.GroupEnd()
        return True

    def InitValues(self):
        self.SetInt32(11, 1)
        self.update_rows()
        self.SetTimer(200)
        if not self.rows:
            self.reload()
        return True

    def update_rows(self):
        rows = search(self.rows, self.GetString(10), ('name', 'layer', 'owner')[max(0, self.GetInt32(11)-1)])
        self.page = min(self.page, max(0, (len(rows)-1)//self.PAGE_SIZE))
        start = self.page*self.PAGE_SIZE
        self.visible = rows[start:start+self.PAGE_SIZE]
        self.LayoutFlushGroup(15)
        for i, row in enumerate(self.visible):
            label = row['name'] + '  —  ' + row['layer']
            self.AddCheckbox(30000+i, c4d.BFH_LEFT, initw=0, inith=0, name=label)
            self.SetBool(30000+i, row['layer'] in self.selected)
        self.LayoutChanged(15)
        self.SetString(13, f'{len(rows)} couches WMS · page {self.page+1}/{max(1, (len(rows)+24)//25)} · {len(self.selected)} sélectionnées')
        self.Enable(17, self.page > 0)
        self.Enable(18, start+self.PAGE_SIZE < len(rows))
        self.Enable(21, bool(self.selected))

    def reload(self):
        if self.job and self.job.is_alive():
            return
        self.result = None
        self.Enable(12, False)
        self.SetString(13, 'Chargement du catalogue swisstopo…')
        def worker():
            try:
                self.result = (fetch_catalogue(), None)
            except Exception as error:
                self.result = (None, str(error))
        self.job = threading.Thread(target=worker, daemon=True)
        self.job.start()

    def Timer(self, msg):
        if not self.IsOpen():
            return
        if self.result is not None:
            rows, error = self.result
            self.result = None
            self.Enable(12, True)
            if rows is not None:
                self.rows = self.owner.catalogue = rows
                self.update_rows()
            else:
                self.SetString(13, 'Catalogue conservé — chargement impossible : ' + error)

    def DestroyWindow(self):
        self.SetTimer(0)
        return True

    def Command(self, id, msg):
        if id in (10, 11):
            self.page = 0
        elif id == 12:
            self.reload()
            return True
        elif id == 17:
            self.page -= 1
        elif id == 18:
            self.page += 1
        elif id == 19:
            self.selected.update(row['layer'] for row in self.visible)
        elif id == 20:
            self.selected.clear()
        elif 30000 <= id < 30000+len(self.visible):
            key = self.visible[id-30000]['layer']
            if self.GetBool(id):
                self.selected.add(key)
            else:
                self.selected.discard(key)
        elif id == 21:
            self.owner.add_layers([dict(r) for r in self.rows if r['layer'] in self.selected], self.mode)
            self.Close()
            return True
        self.update_rows()
        return True


class LayerControls:
    SAVE_MULTI, OUTPUT = 2260, 2261
    TABS, MONO, MULTI = 2200, 2201, 2202
    COLLECTION, SAVE, NEW, REMOVE, RELOAD = 2210, 2211, 2212, 2213, 2214
    FIND_MONO, URL_MONO, FIND_MULTI, URL_MULTI = 2220, 2221, 2222, 2223
    MULTI_GROUP, CLEAR, STATUS = 2230, 2231, 2232
    MULTI_COLLECTION, ADD_COLLECTION, REPLACE_COLLECTION = 2250, 2251, 2252

    def __init__(self):
        super().__init__()
        default = [dict(r) for r in self.LIST_WEB_SERVICES if r['short_name'] != 'atlas_geol']
        self.collections = load_collections(default)
        self.collection_name = 'défaut' if 'défaut' in self.collections else next(iter(self.collections))
        self.mono = [dict(r) for r in self.collections[self.collection_name]]
        self.multi = self.unique_layers(self.collections[self.collection_name])
        self.preview_layer = None
        self.mode = self.MONO
        self.catalogue = []
        if CACHE.exists():
            try:
                self.catalogue = json.loads(CACHE.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                pass
        known = {r['layer']: r for r in default}
        for row in self.catalogue:
            if row['layer'] in known:
                row.update(known[row['layer']])
        self.url_result = None
        self.url_job = None
        self.picker = None
        self.extracting_service = None

    @staticmethod
    def unique_layers(rows):
        result, seen = [], set()
        for row in rows:
            if row['layer'] not in seen:
                result.append(dict(row, checked=row.get('checked', True)))
                seen.add(row['layer'])
        return result

    def add_layer_controls(self):
        self.TabGroupBegin(self.TABS, c4d.BFH_SCALEFIT, tabtype=c4d.TAB_TABS)
        self.GroupBegin(self.MONO, c4d.BFH_SCALEFIT, cols=1, title='Monocouche')
        self.GroupBorderSpace(10, 10, 10, 10)
        self.GroupBegin(2240, c4d.BFH_SCALEFIT, cols=4)
        self.AddStaticText(0, c4d.BFH_LEFT, name='Collection')
        self.AddComboBox(self.COLLECTION, c4d.BFH_SCALEFIT, initw=200)
        self.AddButton(self.NEW, c4d.BFH_LEFT, name='Enregistrer sous…')
        self.AddButton(self.RELOAD, c4d.BFH_LEFT, name='Relire le JSON')
        self.GroupEnd()
        self.AddComboBox(self.ID_LST_CHOIX_IMG, c4d.BFH_SCALEFIT)
        self.GroupBegin(2241, c4d.BFH_SCALEFIT, cols=3)
        self.GroupBorderSpace(0, 10, 0, 0)
        self.AddButton(self.FIND_MONO, c4d.BFH_LEFT, name='Ajouter des couches…')
        self.AddButton(self.URL_MONO, c4d.BFH_LEFT, name='URL map.geo.admin.ch')
        self.AddButton(self.REMOVE, c4d.BFH_LEFT, name='Retirer la couche')
        self.GroupEnd()
        self.GroupBegin(0, c4d.BFH_SCALEFIT, cols=1)
        self.GroupBorderSpace(0, 5, 0, 10)
        self.AddStaticText(0, c4d.BFH_LEFT, name='Depuis map.geo.admin.ch : sélectionner les couches, puis')
        self.AddStaticText(0, c4d.BFH_LEFT, name='Partager → Lien de partage → Copier le lien, puis cliquer sur « URL map.geo.admin.ch ».')
        self.GroupEnd()
        self.AddButton(self.SAVE, c4d.BFH_CENTER, name='Enregistrer la collection')
        self.GroupEnd()
        self.GroupBegin(self.MULTI, c4d.BFH_SCALEFIT, cols=1, title='Multicouches')
        self.GroupBorderSpace(10, 10, 10, 10)
        self.GroupBegin(2253, c4d.BFH_SCALEFIT, cols=4)
        self.AddStaticText(0, c4d.BFH_LEFT, name='Collection')
        self.AddComboBox(self.MULTI_COLLECTION, c4d.BFH_SCALEFIT, initw=160)
        self.AddButton(self.ADD_COLLECTION, c4d.BFH_LEFT, name='Ajouter')
        self.AddButton(self.REPLACE_COLLECTION, c4d.BFH_LEFT, name='Remplacer')
        self.GroupEnd()
        self.GroupBegin(2242, c4d.BFH_SCALEFIT, cols=3)
        self.GroupBorderSpace(0, 10, 0, 0)
        self.AddButton(self.FIND_MULTI, c4d.BFH_LEFT, name='Ajouter des couches…')
        self.AddButton(self.URL_MULTI, c4d.BFH_LEFT, name='URL map.geo.admin.ch')
        self.AddButton(self.CLEAR, c4d.BFH_LEFT, name='Retirer les couches décochées')
        self.GroupEnd()
        self.GroupBegin(0, c4d.BFH_SCALEFIT, cols=1)
        self.GroupBorderSpace(0, 5, 0, 10)
        self.AddStaticText(0, c4d.BFH_LEFT, name='Depuis map.geo.admin.ch : sélectionner les couches, puis')
        self.AddStaticText(0, c4d.BFH_LEFT, name='Partager → Lien de partage → Copier le lien, puis cliquer sur « URL map.geo.admin.ch ».')
        self.GroupEnd()
        self.ScrollGroupBegin(2243, c4d.BFH_SCALEFIT, c4d.SCROLLGROUP_VERT, initw=500, inith=120)
        self.GroupBegin(self.MULTI_GROUP, c4d.BFH_SCALEFIT | c4d.BFV_TOP, cols=1)
        self.GroupEnd()
        self.GroupEnd()
        self.AddButton(self.SAVE_MULTI, c4d.BFH_CENTER, name='Enregistrer la liste comme collection…')
        self.GroupEnd()
        self.GroupEnd()
        self.GroupBegin(2265, c4d.BFH_SCALEFIT, cols=1)
        self.GroupBorderSpace(0, 10, 0, 0)
        self.AddStaticText(0, c4d.BFH_LEFT, name='Destination des textures')
        self.AddComboBox(self.OUTPUT, c4d.BFH_SCALEFIT)
        self.AddStaticText(0, c4d.BFH_LEFT, name='Composition : ordre de la liste, dernière couche au-dessus.')
        self.GroupEnd()
        self.AddStaticText(self.STATUS, c4d.BFH_SCALEFIT, initw=500, name=' ')
        self.AddButton(self.ID_BTON_WEB, c4d.BFH_CENTER, initw=300, inith=25, name='Ouvrir map.geo.admin.ch')
        self.AddRadioButton(self.ID_BTON_DISPLAY, c4d.BFH_CENTER, name='Afficher la couche dans la vue de haut')

    def InitValues(self):
        self.SetInt32(self.TABS, self.MONO)
        self.fill_collections()
        self.fill_mono()
        self.fill_multi()
        self.refresh_output()
        return super().InitValues()

    def refresh_output(self):
        selected = bool(c4d.documents.GetActiveDocument().GetActiveObjects(0))
        state = (self.mode, selected)
        if getattr(self, '_output_state', None) == state:
            return
        choice = self.GetInt32(self.OUTPUT) or 1
        self.FreeChildren(self.OUTPUT)
        self.AddChild(self.OUTPUT, 1, 'Un plan par couche' if self.mode == self.MULTI else 'Créer un plan')
        if self.mode == self.MULTI:
            self.AddChild(self.OUTPUT, 2, 'Un seul plan avec toutes les couches')
        if selected:
            self.AddChild(self.OUTPUT, 3, 'Appliquer aux objets sélectionnés')
        if (choice == 3 and not selected) or (choice == 2 and self.mode != self.MULTI):
            choice = 1
        self.SetInt32(self.OUTPUT, choice)
        self._output_state = state

    def fill_collections(self):
        previous_multi = self.GetInt32(self.MULTI_COLLECTION) or 1
        self.FreeChildren(self.MULTI_COLLECTION)
        self.FreeChildren(self.COLLECTION)
        for i, name in enumerate(self.collections, 1):
            self.AddChild(self.COLLECTION, i, name)
            self.AddChild(self.MULTI_COLLECTION, i, name)
            if name == self.collection_name:
                self.SetInt32(self.COLLECTION, i)

        self.SetInt32(self.MULTI_COLLECTION, min(previous_multi, len(self.collections)))

    def fill_mono(self):
        current = self.GetInt32(self.ID_LST_CHOIX_IMG)
        self.FreeChildren(self.ID_LST_CHOIX_IMG)
        for i, row in enumerate(self.mono, 1):
            self.AddChild(self.ID_LST_CHOIX_IMG, i, row['name'])
        self.SetInt32(self.ID_LST_CHOIX_IMG, min(max(current, 1), len(self.mono)))

    def fill_multi(self):
        if not any(r['layer'] == self.preview_layer for r in self.multi):
            self.preview_layer = self.multi[0]['layer'] if self.multi else None
        self.LayoutFlushGroup(self.MULTI_GROUP)
        self.layer_areas = []
        if not self.multi:
            self.AddStaticText(0, c4d.BFH_LEFT, name='Ajoutez des couches avec la recherche ou une URL.')
        for i, row in enumerate(self.multi):
            self.GroupBegin(60000+i, c4d.BFH_SCALEFIT, cols=2)
            self.AddCheckbox(40000+i, c4d.BFH_LEFT, initw=0, inith=0, name='')
            self.SetBool(40000+i, row.get('checked', True))
            area = LayerRow(self, i, row)
            self.layer_areas.append(area)
            self.AddUserArea(50000+i, c4d.BFH_SCALEFIT, initw=280, inith=24)
            self.AttachUserArea(area, 50000+i)
            self.GroupEnd()
        self.LayoutChanged(self.MULTI_GROUP)

    def preview_service(self):
        if self.mode == self.MULTI:
            return next((r for r in self.multi if r['layer'] == self.preview_layer), None)
        rows = self.selected_services()
        return rows[0] if rows else None

    def selected_services(self):
        if self.mode == self.MULTI:
            return [r for r in self.multi if r.get('checked', True)]
        i = self.GetInt32(self.ID_LST_CHOIX_IMG)-1
        return self.mono[i:i+1] if i >= 0 else []

    def service(self):
        if self.extracting_service is not None:
            return self.extracting_service
        rows = self.selected_services()
        if rows:
            row = dict(rows[0])
            row['min_cm'] = min(r['min_cm'] for r in rows)
            return row
        return {'name': '', 'layer': '', 'min_cm': 10, 'short_name': ''}

    def extent_changed(self, edited=False):
        super().extent_changed(edited)
        active = bool(self.selected_services())
        self.Enable(self.ID_BTON_REQUEST, active and bool(self.grid))
        self.Enable(self.ID_BTON_DISPLAY, self.preview_service() is not None)
        self.SetString(self.ID_BTON_REQUEST, 'Importer les couches cochées' if self.mode == self.MULTI else 'Importer l’image')

    def refresh_background_choice(self):
        # Ne pas changer la sélection utilisateur quand le fond de vue est actualisé.
        from utils.geo_extent_dialog import GeoExtentDialog
        GeoExtentDialog.refresh_background_choice(self)
        preview = self.preview_service()
        self.SetBool(self.ID_BTON_DISPLAY, preview is not None and self.active_background() == preview['layer'])

    def add_layers(self, rows, mode):
        target = self.multi if mode == self.MULTI else self.mono
        existing = {r['layer'] for r in target}
        count = 0
        for row in rows:
            if row['layer'] not in existing:
                target.append(dict(row))
                existing.add(row['layer'])
                count += 1
        self.fill_mono()
        self.fill_multi()
        self.extent_changed()
        self.SetString(self.STATUS, f'{count} couche(s) ajoutée(s).' + (' Enregistrez la collection pour la conserver.' if mode == self.MONO else ''))

    def import_url(self, mode):
        if self.url_job and self.url_job.is_alive():
            return
        text = c4d.GetStringFromClipboard() or ''
        self.SetString(self.STATUS, 'Lecture des couches du presse-papiers…')
        def worker():
            try:
                entries = parse_url(text)
                catalogue = self.catalogue or fetch_catalogue()
                by_id = {r['layer']: r for r in catalogue}
                rows, skipped = [], []
                settings = False
                for entry in entries:
                    if entry['layer'] in by_id:
                        row = dict(by_id[entry['layer']])
                        row['checked'] = entry['checked']
                        rows.append(row)
                        settings |= bool(entry['attributes'] or entry['opacity'])
                    else:
                        skipped.append(entry['layer'])
                self.url_result = (mode, rows, skipped, settings, None)
            except Exception as error:
                self.url_result = (mode, [], [], False, str(error))
        self.url_job = threading.Thread(target=worker, daemon=True)
        self.url_job.start()

    def Timer(self, msg):
        if not self.IsOpen():
            return
        super().Timer(msg)
        self.refresh_output()
        if self.url_result is not None:
            mode, rows, skipped, settings, error = self.url_result
            self.url_result = None
            if error:
                c4d.gui.MessageDialog(error)
            else:
                self.add_layers(rows, mode)
                if skipped or settings:
                    details = []
                    if skipped:
                        details.append('Couches absentes du WMS swisstopo (non ajoutées) :\n' + '\n'.join(skipped))
                    if settings:
                        details.append('Seule la liste des couches est reprise. Dates, styles et opacités de l’URL ne sont pas appliqués.')
                    c4d.gui.MessageDialog('\n\n'.join(details))

    def CoreMessage(self, id, msg):
        if not self.IsOpen():
            return True
        return super().CoreMessage(id, msg)

    def DestroyWindow(self):
        self.SetTimer(0)
        if self.picker is not None:
            self.picker.SetTimer(0)
            self.picker.Close()
        return True

    def handle_command(self, id, msg):
        from utils import swisstopo_background as bg
        if id == self.TABS:
            self.mode = self.GetInt32(self.TABS)
            self.refresh_output()
            self.extent_changed()
            self.refresh_background_choice()
        elif id in (self.ADD_COLLECTION, self.REPLACE_COLLECTION):
            names = list(self.collections)
            index = self.GetInt32(self.MULTI_COLLECTION)-1
            if 0 <= index < len(names):
                rows = self.unique_layers(self.collections[names[index]])
                if id == self.REPLACE_COLLECTION:
                    self.multi = rows
                    self.fill_multi()
                    self.extent_changed()
                    self.SetString(self.STATUS, 'Collection chargée : ' + names[index])
                else:
                    self.add_layers(rows, self.MULTI)
        elif id == self.MULTI_COLLECTION:
            pass
        elif id == self.COLLECTION:
            self.collections[self.collection_name] = [dict(r) for r in self.mono]
            self.collection_name = list(self.collections)[self.GetInt32(id)-1]
            self.mono = [dict(r) for r in self.collections[self.collection_name]]
            self.fill_mono()
            self.extent_changed()
        elif id == self.OUTPUT:
            pass
        elif id == self.SAVE_MULTI:
            name = c4d.gui.InputDialog('Nom de la collection multicouches', 'Ma collection')
            if name and name.strip():
                name = name.strip()
                if name in self.collections and not c4d.gui.QuestionDialog('Remplacer la collection « ' + name + ' » ?'):
                    return True
                collections = dict(self.collections)
                collections[name] = [dict(r) for r in self.multi]
                try:
                    save_json(COLLECTIONS, {'version': 1, 'collections': collections})
                except OSError as error:
                    c4d.gui.MessageDialog(str(error))
                    return True
                self.collections = collections
                self.fill_collections()
                self.SetInt32(self.MULTI_COLLECTION, list(collections).index(name)+1)
                self.SetString(self.STATUS, 'Collection enregistrée : ' + name)
        elif id in (self.SAVE, self.NEW):
            name = self.collection_name if id == self.SAVE else c4d.gui.InputDialog('Nom de la collection', self.collection_name)
            if name and name.strip():
                name = name.strip()
                if id == self.NEW and name in self.collections and not c4d.gui.QuestionDialog('Remplacer la collection « ' + name + ' » ?'):
                    return True
                collections = dict(self.collections)
                collections[name] = [dict(r) for r in self.mono]
                try:
                    save_json(COLLECTIONS, {'version': 1, 'collections': collections})
                except OSError as error:
                    c4d.gui.MessageDialog(str(error))
                    return True
                self.collections, self.collection_name = collections, name
                self.fill_collections()
                self.SetString(self.STATUS, 'Collection enregistrée : ' + name)
        elif id == self.RELOAD:
            try:
                self.collections = load_collections([])
                if self.collection_name not in self.collections:
                    self.collection_name = next(iter(self.collections))
                self.mono = [dict(r) for r in self.collections[self.collection_name]]
                self.fill_collections()
                self.fill_mono()
                self.extent_changed()
            except (OSError, ValueError, KeyError, TypeError) as error:
                c4d.gui.MessageDialog('JSON non chargé : ' + str(error))
        elif id == self.REMOVE:
            i = self.GetInt32(self.ID_LST_CHOIX_IMG)-1
            if 0 <= i < len(self.mono):
                self.mono.pop(i)
                self.fill_mono()
                self.extent_changed()
        elif id == self.CLEAR:
            self.multi = self.selected_services() if self.mode == self.MULTI else self.multi
            self.fill_multi()
            self.extent_changed()
        elif id in (self.FIND_MONO, self.FIND_MULTI):
            if self.picker:
                self.picker.Close()
            self.picker = LayerPicker(self, self.MONO if id == self.FIND_MONO else self.MULTI)
            self.picker.Open(c4d.DLG_TYPE_ASYNC, defaultw=750, defaulth=550)
        elif id in (self.URL_MONO, self.URL_MULTI):
            self.import_url(self.MONO if id == self.URL_MONO else self.MULTI)
        elif 50000 <= id < 50000+len(self.multi):
            previous = self.preview_service()
            displaying = previous is not None and self.active_background() == previous['layer']
            self.preview_layer = self.multi[id-50000]['layer']
            for area in self.layer_areas:
                area.Redraw()
            if displaying:
                bg.select(self.preview_layer)
            self.extent_changed()
            self.refresh_background_choice()
        elif id == self.ID_BTON_DISPLAY:
            preview = self.preview_service()
            if preview:
                bg.toggle(preview['layer'])
                self.refresh_background_choice()
        elif 40000 <= id < 40000+len(self.multi):
            self.multi[id-40000]['checked'] = self.GetBool(id)
            self.extent_changed()
        elif id == self.ID_LST_CHOIX_IMG:
            if self.service()['layer'] and isinstance(self.active_background(), str):
                bg.select(self.service()['layer'])
            self.extent_changed()
        elif id == self.ID_BTON_REQUEST:
            rows = list(self.selected_services())
            if not self.grid or not rows:
                return True
            if not c4d.documents.GetActiveDocument().GetDocumentPath():
                c4d.gui.MessageDialog('Enregistrez le document avant d’importer les images.')
                return True
            output = self.GetInt32(self.OUTPUT) or 1
            self.import_targets = list(c4d.documents.GetActiveDocument().GetActiveObjects(0)) if output == 3 else []
            if output == 3 and not self.import_targets:
                c4d.gui.MessageDialog('Sélectionnez au moins un objet.')
                return True
            if output in (2, 3) and len(rows) > 1:
                import hashlib
                ids = ','.join(r['layer'] for r in rows)
                rows = [dict(name='Composition swisstopo', layer=ids,
                             short_name='composition_' + hashlib.sha256(ids.encode()).hexdigest()[:12],
                             min_cm=min(r['min_cm'] for r in rows))]
            failed = []
            try:
                for index, row in enumerate(rows, 1):
                    c4d.StatusSetText(f'{index}/{len(rows)} — {row["name"]}')
                    c4d.StatusSetBar(int(100*(index-1)/len(rows)))
                    self.extracting_service = row
                    try:
                        if not self.extract_IMG():
                            failed.append(row['name'])
                    except Exception as error:
                        failed.append(row['name'] + ' : ' + str(error))
            finally:
                self.extracting_service = None
                self.import_targets = []
                c4d.StatusClear()
            self.SetString(self.STATUS, f'{len(rows)-len(failed)}/{len(rows)} couche(s) importée(s).')
            if failed:
                c4d.gui.MessageDialog('Couches non importées :\n' + '\n'.join(failed))
        else:
            return super().handle_command(id, msg)
        return True
