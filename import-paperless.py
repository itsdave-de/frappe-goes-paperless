import json

field_mapping = {
    'Belegdatum': 'BelegDatum',
    'Belegnummer': 'BelegNr',
    'Ausgeblendet': 'isHidden',
    'Richtung': 'Richtung',
    'Belegart': 'Belegart',
    'Konto': 'Erlöskonto',
    'Zahlstatus': 'ZahlStatus',
    'Zahlungsart': 'Zahlungsart',
    'Zahltage': 'Zahltage',
    'Steuer-Betrag': 'Ust',
    'Netto-Betrag': 'NettoBeleg',
    'Adress-Ort': 'AdressOrt',
    'Adress-PLZ': 'AdressPLZ',
    'Adress-Name': 'AdressName',
    'Inoxision UID': 'UID',
    'Inoxision Erstelldatum': 'CreationDate',
    'Inoxision Archivar': 'Username'
}

files = []
# load all json files on the array
#
# for now, read just one
with open('05142346_20190228.json', 'r') as f:
    files.append(json.load(f))

for data in files:
    paper = {}
    if data['Richtung'] == 'eingehend' and data['Belegart'] == 'Rechnung':
        paper['Type'] = 'Eingangsrechnung'
    elif data['Richtung'] == 'ausgehend' and data['Belegart'] == 'Rechnung':
        paper['Type'] = 'Ausgangsrechnung'
    # Mapping values
    for paperless, json_field in field_mapping.items():
        if json_field in data:
            paper[paperless] = data[json_field]

