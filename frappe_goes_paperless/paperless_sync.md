
# Paperless Consumption Process

Ref: https://paperless.readthedocs.io/en/latest/consumption.html#hooking-into-the-consumption-process

### Paperless automatic sync script
`/usr/local/sbin/sync_docs.sh`

```bash
#!/bin/sh

DOCUMENT_ID=${1}

FRAPPE_URL="http://10.251.0.54:8000"
API_KEY="xxxxxxxxxxxxx"
API_SECRET="xxxxxxxxxxx"

curl ${FRAPPE_URL}/api/method/frappe_goes_paperless.frappe_goes_paperless.tools.sync_documents \
    -H "Authorization: token ${API_KEY}:${API_SECRET}" \
    -d "{\"paperless_document\": \"${DOCUMENT_ID}\"}"
exit 0
```

### Docker compose configuration

Add this line on the `docker-compose.yaml` file on the `webserver` container configuration volume:
```
- /usr/local/sbin/sync_docs.sh:/usr/local/sbin/sync_docs.sh:ro
```

Add this line on the `docker-compose.env` file at end:
```
PAPERLESS_POST_CONSUME_SCRIPT='/usr/local/sbin/sync_docs.sh'
```

