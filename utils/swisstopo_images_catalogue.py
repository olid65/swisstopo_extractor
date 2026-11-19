"""Catalogue WMS et liens map.geo.admin.ch, indépendant de Cinema 4D."""
import json
import re
import tempfile
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import c4d

DATA = Path(c4d.storage.GeGetC4DPath(c4d.C4D_PATH_PREFS)) / 'swisstopo_images'
DATA.mkdir(parents=True, exist_ok=True)
DEFAULT_COLLECTIONS = Path(__file__).resolve().parent.parent / 'res' / 'swisstopo_images_collections.json'
COLLECTIONS = DATA / 'collections.json'
CACHE = DATA / 'catalogue_cache.json'


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.casefold())
                   if not unicodedata.combining(c))


def save_json(path, value):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     suffix='.tmp', delete=False) as output:
        temp = Path(output.name)
        json.dump(value, output, ensure_ascii=False, indent=2)
    try:
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def load_collections(default):
    if not COLLECTIONS.exists():
        initial = json.loads(DEFAULT_COLLECTIONS.read_text(encoding='utf-8')) if DEFAULT_COLLECTIONS.exists() else {'version': 1, 'collections': {'défaut': default}}
        save_json(COLLECTIONS, initial)
    data = json.loads(COLLECTIONS.read_text(encoding='utf-8'))
    collections = data['collections']
    if not isinstance(collections, dict) or not collections:
        raise ValueError('Le JSON doit contenir au moins une collection.')
    for name, layers in collections.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(layers, list):
            raise ValueError('Collection invalide : ' + str(name))
        for layer in layers:
            if not isinstance(layer, dict) or not all(isinstance(layer.get(k), str) and layer[k] for k in ('name', 'layer', 'short_name')):
                raise ValueError('Couche invalide dans la collection ' + name)
            if not isinstance(layer.get('min_cm'), (int, float)) or layer['min_cm'] <= 0:
                raise ValueError('Résolution invalide dans la collection ' + name)
    return collections


def fetch_catalogue():
    with urllib.request.urlopen('https://api3.geo.admin.ch/rest/services/api/MapServer?lang=fr', timeout=25) as response:
        metadata = json.load(response)
    with urllib.request.urlopen('https://wms.geo.admin.ch/?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities', timeout=25) as response:
        root = ET.fromstring(response.read())
    layers = {}
    for element in root.findall('.//{*}Layer'):
        name = element.findtext('{*}Name')
        if name:
            layers[name] = {'layer': name, 'name': element.findtext('{*}Title') or name,
                            'short_name': re.sub(r'[^\w-]', '_', name), 'min_cm': 10,
                            'owner': '', 'wms': True}
    for item in metadata['layers']:
        key = item['layerBodId']
        if key in layers:
            layers[key].update(name=item.get('name') or key,
                               owner=item.get('attributes', {}).get('dataOwner', ''),
                               description=item.get('fullName', ''))
    result = sorted(layers.values(), key=lambda row: normalized(row['name']))
    if not result:
        raise ValueError('Le catalogue WMS est vide.')
    save_json(CACHE, result)
    return result


def parse_url(text):
    url = urllib.parse.urlsplit(text.strip())
    if url.scheme not in ('http', 'https') or url.hostname not in ('map.geo.admin.ch', 's.geo.admin.ch'):
        raise ValueError('Copiez une URL de map.geo.admin.ch ou s.geo.admin.ch.')
    if url.hostname == 's.geo.admin.ch':
        with urllib.request.urlopen(url.geturl(), timeout=20) as response:
            url = urllib.parse.urlsplit(response.geturl())
        if url.hostname != 'map.geo.admin.ch':
            raise ValueError('Ce lien court ne renvoie pas vers map.geo.admin.ch.')
    modern = '?' in url.fragment
    params = urllib.parse.parse_qs(url.fragment.split('?', 1)[1] if modern else url.query,
                                  keep_blank_values=True)
    value = params.get('layers', [''])[0]
    result = []
    hidden = params.get('layers_visibility', [''])[0].split(',')
    entries = value.split(';') if modern else value.split(',')
    for index, entry in enumerate(entries):
        if not entry:
            continue
        parts = entry.split(',') if modern else [entry]
        identifier, *attributes = parts[0].split('@')
        visible = (len(parts) < 2 or parts[1] != 'f') if modern else (index >= len(hidden) or hidden[index] != 'false')
        result.append({'layer': urllib.parse.unquote(identifier), 'checked': visible,
                       'attributes': attributes,
                       'opacity': parts[2] if modern and len(parts) > 2 else None})
    if not result:
        raise ValueError('Cette URL ne contient aucune couche ajoutée (paramètre layers).')
    return result


def search(rows, query='', sort='name'):
    terms = normalized(query).split()
    return sorted((r for r in rows if all(t in normalized(' '.join(str(r.get(k, '')) for k in
                  ('name', 'layer', 'owner', 'description'))) for t in terms)),
                  key=lambda r: normalized(str(r.get(sort, ''))))
